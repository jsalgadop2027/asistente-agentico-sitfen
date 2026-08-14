"""Escalamiento a un humano (#C de la Fase 3).

Cuando el usuario pide explícitamente hablar con una persona, o el agente detecta
angustia real / insatisfacción que no puede resolver, la tool `escalar_a_humano`
llama aquí: se registra el caso en Firestore y se avisa al equipo por correo
(SendGrid, reutilizando `email_sender`). El humano retoma la conversación por la
consola en vivo (`app.agent.live_console`).

No pausa el bot globalmente: la consola en vivo es de un solo usuario y un flag
global cortaría el servicio a los demás. El registro + aviso son suficientes para
que una persona intervenga; la pausa la decide el operador desde la consola.

Fail-open: registro y correo son independientes y no lanzan; se informa `ok` según
el envío del aviso (la parte accionable para el equipo).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from google.cloud import firestore

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


@dataclass
class HandoffResult:
    ok: bool
    motivo: str


def _lima_day() -> str:
    local = datetime.now(timezone.utc) + timedelta(hours=settings.lima_utc_offset_hours)
    return local.date().isoformat()


class HandoffStore:
    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        self._client = client or firestore.Client(project=settings.gcp_project_id)
        self._collection = settings.firestore_handoffs_collection

    def add(self, *, user_id: str, motivo: str, resumen: str, nombre: str,
            whatsapp: str, email: str) -> None:
        self._client.collection(self._collection).add({
            "user_id": user_id,
            "motivo": motivo,
            "resumen": resumen,
            "nombre": nombre,
            "whatsapp": whatsapp,
            "email": email,
            "day": _lima_day(),
            "created_at": firestore.SERVER_TIMESTAMP,
        })


def _render(motivo: str, resumen: str, *, nombre: str, whatsapp: str,
            email: str) -> tuple[str, str]:
    contacto = " · ".join(p for p in [
        f"Nombre: {nombre}" if nombre else "",
        f"WhatsApp: {whatsapp}" if whatsapp else "",
        f"Correo: {email}" if email else "",
    ] if p) or "No disponible"
    html = (
        "<div style=\"font-family:Arial,Helvetica,sans-serif;color:#1a1a1a\">"
        "<p><strong>ESCALAMIENTO A HUMANO</strong> — un usuario necesita atención "
        "de una persona del equipo.</p>"
        f"<p><strong>Motivo:</strong> {escape(motivo)}</p>"
        "<p><strong>Resumen de la conversación:</strong></p>"
        f"<blockquote style=\"border-left:3px solid #c53030;padding-left:12px;"
        f"color:#333\">{escape(resumen or 'No disponible')}</blockquote>"
        f"<p><strong>Contacto del usuario:</strong> {escape(contacto)}</p>"
        "<p style=\"color:#888;font-size:12px\">Puedes retomar la conversación "
        "desde la consola en vivo del asistente.</p></div>"
    )
    text = (
        "ESCALAMIENTO A HUMANO\n\n"
        f"Motivo: {motivo}\n\n"
        f"Resumen de la conversación:\n{resumen or 'No disponible'}\n\n"
        f"Contacto del usuario: {contacto}\n\n"
        "Retoma la conversación desde la consola en vivo del asistente."
    )
    return html, text


def send_handoff(motivo: str, resumen: str, *, user_id: str = "", nombre: str = "",
                 whatsapp: str = "", email: str = "",
                 store: Optional[HandoffStore] = None) -> HandoffResult:
    """Registra el caso y avisa al equipo por correo. Fail-open (no lanza)."""
    from app.channels.email_sender import send_email

    try:
        (store or HandoffStore()).add(
            user_id=user_id, motivo=motivo, resumen=resumen, nombre=nombre,
            whatsapp=whatsapp, email=email)
    except Exception as exc:  # noqa: BLE001
        logger.warning("handoff_record_failed", error=str(exc))

    subject = f"[ESCALAMIENTO] {nombre or 'Usuario'}: {motivo[:60]}"
    html, text = _render(motivo, resumen, nombre=nombre, whatsapp=whatsapp,
                         email=email)
    ok = send_email(to=settings.handoff_to, subject=subject, html=html, text=text,
                    reply_to=email or None)
    logger.info("handoff_sent", ok=ok)
    return HandoffResult(ok=ok, motivo=motivo)
