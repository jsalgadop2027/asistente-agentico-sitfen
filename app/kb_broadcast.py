"""Difusión por WhatsApp del resumen de contenido nuevo ingestado.

Al incorporarse un documento nuevo a la base de conocimiento (desde la Admin UI),
este módulo genera un resumen breve y lo envía por WhatsApp a los usuarios que
optaron por recibir novedades (`send_kb_summary=True`, ver `app.user_registry`).

Es un complemento del canal web (avatar), que anuncia las novedades por polling
de `app.kb_events`. Aquí, en cambio, se hace un *push* directo a los suscriptores.

Consideraciones operativas (Twilio WhatsApp):
  - El destinatario debe haber iniciado sesión con el número (en Sandbox, haber
    enviado el "join ..."); si no, Twilio no entrega el mensaje.
  - Se respeta la preferencia del usuario y su estado (solo activos + opt-in).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.observability import get_logger

logger = get_logger(__name__)

# Firma de autoría al pie de cada mensaje de difusión, salvo que el llamador la
# desactive explícitamente pasando footer=None. Fuente única compartida con
# app.main (que la reexporta) para no duplicar el texto.
SIGNATURE = "Desarrollado por el Ing. Julio Salgado"

_SUMMARY_PROMPT = (
    "Eres un asistente de inteligencia comercial del arándano peruano. Resume el "
    "siguiente documento en 2 o 3 frases claras, en español, para avisar por "
    "WhatsApp a usuarios de que se incorporó a la base de conocimiento. No uses "
    "viñetas ni encabezados; devuelve solo el resumen.\n\n"
    "Título: {title}\n\nContenido:\n{content}"
)


@dataclass
class BroadcastResult:
    source: str
    recipients: int = 0
    sent: int = 0
    failed: int = 0
    summary: str = ""
    skipped_reason: str | None = None
    failures: list[str] = field(default_factory=list)


def build_summary(source: str, title: str | None = None, *,
                  max_chars: int = 3000) -> tuple[str, str]:
    """Devuelve (título, resumen) del documento a partir de sus chunks.

    Intenta un resumen con el LLM; si no es posible (sin GCP, sin chunks, error),
    cae a una plantilla mínima para no bloquear la difusión.
    """
    from app.firestore_store import FirestoreVectorStore

    chunks = FirestoreVectorStore().get_document_chunks(source, limit=12)
    resolved_title = title or (chunks[0].title if chunks else "") or source
    if not chunks:
        return resolved_title, f"Se incorporó «{resolved_title}» a la base de conocimiento."

    content = "\n".join(c.text for c in chunks)[:max_chars]
    try:
        from app.agent.models import invoke_with_failover

        resp = invoke_with_failover(
            _SUMMARY_PROMPT.format(title=resolved_title, content=content),
            temperature=0.2)
        text = getattr(resp, "content", "") or ""
        summary = text.strip() if isinstance(text, str) else str(text).strip()
        if summary:
            return resolved_title, summary
    except Exception as exc:  # noqa: BLE001
        logger.warning("kb_summary_generation_failed", source=source, error=str(exc))
    return resolved_title, f"Se incorporó «{resolved_title}» a la base de conocimiento."


def _compose(nombre: str, title: str, summary: str, footer: str | None) -> str:
    saludo = f"Hola {nombre}, " if nombre else ""
    body = (
        f"📚 {saludo}se agregó información nueva a la base de conocimiento.\n\n"
        f"*{title}*\n{summary}\n\n"
        f"Puedes preguntarme sobre este contenido cuando quieras."
    )
    return f"{body}\n\n{footer}" if footer else body


def broadcast_new_document(source: str, title: str | None = None, *,
                           footer: str | None = SIGNATURE,
                           generate_summary: bool = True) -> BroadcastResult:
    """Envía por WhatsApp el resumen de un documento a los usuarios suscritos.

    - Destinatarios: usuarios activos con `send_kb_summary=True`.
    - El mensaje se personaliza con el nombre de cada usuario.
    - Nunca lanza: los errores por destinatario se acumulan en el resultado.
    """
    from app.channels.twilio_whatsapp import (send_whatsapp_message,
                                              send_whatsapp_template)
    from app.config import settings
    from app.user_registry import get_user_registry

    result = BroadcastResult(source=source)
    template_sid = settings.whatsapp_kb_template_sid
    try:
        recipients = get_user_registry().kb_summary_recipients()
    except Exception as exc:  # noqa: BLE001
        logger.warning("kb_broadcast_recipients_failed", source=source, error=str(exc))
        result.skipped_reason = f"no se pudo obtener destinatarios: {exc}"
        return result

    result.recipients = len(recipients)
    if not recipients:
        result.skipped_reason = "no hay usuarios suscritos activos"
        return result

    if generate_summary:
        resolved_title, summary = build_summary(source, title)
    else:
        resolved_title, summary = (title or source), \
            f"Se incorporó «{title or source}» a la base de conocimiento."
    result.summary = summary

    for u in recipients:
        to = u.whatsapp if u.whatsapp.startswith("whatsapp:") else f"whatsapp:{u.whatsapp}"
        try:
            if template_sid:
                # Plantilla aprobada: entrega push fuera de la ventana de 24 h.
                ok = send_whatsapp_template(to, template_sid, {
                    "1": u.nombre or "usuario",
                    "2": resolved_title,
                    "3": summary,
                })
            else:
                # Texto libre: solo entrega en Sandbox o dentro de la ventana 24 h.
                body = _compose(u.nombre, resolved_title, summary, footer)
                ok = send_whatsapp_message(to, body)
        except Exception as exc:  # noqa: BLE001
            ok = False
            logger.warning("kb_broadcast_send_error", code=u.code, error=str(exc))
        if ok:
            result.sent += 1
        else:
            result.failed += 1
            result.failures.append(u.code)

    logger.info("kb_broadcast_done", source=source, sent=result.sent,
                failed=result.failed, recipients=result.recipients)
    return result


def broadcast_event(doc_id: str, *, footer: str | None = SIGNATURE) -> BroadcastResult | None:
    """Difunde el resumen de un evento de `kb_events` de forma idempotente.

    Pensado para el trigger de Firestore/Eventarc y para el envío manual desde la
    Admin UI: reclama atómicamente el evento (marca `broadcast_at`). Si ya se
    difundió para esta ingesta, no hace nada y devuelve None. Así el trigger y el
    checkbox de la interfaz no pueden duplicar el mensaje.
    """
    from app.kb_events import KBEventStore

    data = KBEventStore().claim_broadcast(doc_id)
    if data is None:
        logger.info("kb_broadcast_skipped_already_sent", doc_id=doc_id)
        return None
    return broadcast_new_document(data["source"], data.get("title"), footer=footer)


def broadcast_source(source: str, *, footer: str | None = SIGNATURE) -> BroadcastResult | None:
    """Como `broadcast_event`, identificando el evento por el nombre de la fuente."""
    from app.kb_events import KBEventStore

    return broadcast_event(KBEventStore.doc_id_for(source), footer=footer)
