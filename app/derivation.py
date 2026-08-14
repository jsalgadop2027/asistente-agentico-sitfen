"""Derivación de solicitudes del usuario a la entidad pública pertinente.

Cuando el usuario confirma, el agente envía su solicitud por correo (SendGrid) a la
entidad pública más apropiada (SENASA, SENAMHI, PROMPERÚ, SUNAT, MIDAGRI, INDECI,
Gobierno Regional, etc.). El agente (LLM) identifica la entidad; aquí se resuelve el
destinatario y se compone el correo.

Seguridad de destinatario: NUNCA se inventa un correo. Si la entidad no tiene un
correo verificado en `ENTITY_EMAILS`, la solicitud cae a `settings.derivation_to`
(admin) etiquetada con la entidad, para ruteo manual. A medida que se agreguen
correos verificados a `ENTITY_EMAILS`, el envío pasa a ser directo.

Cada derivación (una entidad de un caso = un documento) se registra además en
Firestore vía `DerivationStore`, independiente del envío por correo, para que el
Admin UI pueda mostrar estadísticas (ver `admin_ui/_derivaciones.py`). Igual que en
`app.handoff`: el registro y el correo son fail-open por separado — que falle uno no
debe impedir el otro.
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


def _lima_day() -> str:
    local = datetime.now(timezone.utc) + timedelta(hours=settings.lima_utc_offset_hours)
    return local.date().isoformat()


class DerivationStore:
    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        self._client = client or firestore.Client(project=settings.gcp_project_id)
        self._collection = settings.firestore_derivations_collection

    def add(self, *, user_id: str, entidad: str, resumen: str, urgencia: str,
            directo: bool, ok: bool, destino: str, nombre: str, whatsapp: str,
            email: str, medio: str = "texto") -> None:
        self._client.collection(self._collection).add({
            "user_id": user_id,
            "entidad": entidad,
            "resumen": resumen,
            "urgencia": urgencia,
            "directo": directo,
            "ok": ok,
            "destino": destino,
            "nombre": nombre,
            "whatsapp": whatsapp,
            "email": email,
            "medio": medio,
            "day": _lima_day(),
            "created_at": firestore.SERVER_TIMESTAMP,
        })

    def list_recent(self, limit: int = 2000) -> list[dict]:
        """Derivaciones más recientes, para las estadísticas del Admin UI. Sin
        filtro de fecha en la consulta (evita requerir un índice compuesto): el
        recorte por rango se hace en memoria, igual que el resto del proyecto."""
        docs = (self._client.collection(self._collection)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit).stream())
        return [d.to_dict() or {} for d in docs]

# Catálogo entidad -> correo VERIFICADO. Vacío por ahora (todo cae al admin).
# Rellenar SOLO con direcciones oficiales confirmadas, p. ej.:
#   "senasa": "consultas@senasa.gob.pe",
ENTITY_EMAILS: dict[str, str] = {}


@dataclass
class DerivationResult:
    ok: bool
    entidad: str
    destino: str
    directo: bool  # True = fue directo a la entidad; False = cayó al admin


@dataclass
class MultiDerivationResult:
    """Resultado de canalizar un caso a TODAS las entidades involucradas."""
    solicitadas: list[str]
    enviadas: list[str]
    fallidas: list[str]

    @property
    def ok(self) -> bool:
        return bool(self.enviadas)


def _resolve_destino(entidad: str) -> tuple[str, bool]:
    """(correo, directo). Directo si hay correo verificado de la entidad."""
    key = (entidad or "").strip().lower()
    for name, email in ENTITY_EMAILS.items():
        if key and (name.lower() in key or key in name.lower()):
            return email, True
    return settings.derivation_to, False


_URGENT_LEVELS = ("alta", "critica")

# Nota sobre el canal de origen: solo se agrega al correo cuando NO fue texto
# escrito directamente (el caso por defecto, que no necesita aclaración) — le
# da contexto a la entidad receptora de que el resumen viene de una
# transcripción/descripción automática, no de la redacción literal del
# ciudadano.
_MEDIO_LABELS = {
    "voz": "🎙️ Nota de voz de WhatsApp (transcripción automática)",
    "imagen": "📷 Imagen de WhatsApp (descripción automática)",
}


def _render(entidad: str, resumen: str, *, nombre: str, whatsapp: str,
            email: str, directo: bool, urgencia: str = "",
            medio: str = "texto") -> tuple[str, str]:
    contacto = " · ".join(p for p in [
        f"Nombre: {nombre}" if nombre else "",
        f"WhatsApp: {whatsapp}" if whatsapp else "",
        f"Correo: {email}" if email else "",
    ] if p) or "No disponible"
    encabezado = (
        f"Solicitud dirigida a <strong>{escape(entidad)}</strong>."
        if directo else
        f"<strong>DERIVAR A: {escape(entidad)}</strong> (ruteo manual)."
    )
    urgente = urgencia in _URGENT_LEVELS
    urgencia_html = (
        f'<p style="color:#c53030"><strong>URGENCIA: {escape(urgencia.upper())}</strong> '
        "— caso con riesgo o pérdida en curso, requiere atención prioritaria.</p>"
        if urgente else ""
    )
    urgencia_text = (
        f"URGENCIA: {urgencia.upper()} — requiere atención prioritaria.\n\n"
        if urgente else ""
    )
    medio_label = _MEDIO_LABELS.get(medio, "")
    medio_html = (f'<p style="color:#666"><strong>Origen:</strong> '
                  f"{escape(medio_label)}</p>" if medio_label else "")
    medio_text = f"Origen: {medio_label}\n\n" if medio_label else ""
    html = (
        "<div style=\"font-family:Arial,Helvetica,sans-serif;color:#1a1a1a\">"
        f"<p>{encabezado}</p>"
        f"{urgencia_html}"
        "<p>El asistente de inteligencia comercial del arándano canaliza, con "
        "consentimiento del ciudadano, el siguiente caso (solicitud o inquietud) "
        "para su atención personalizada:</p>"
        f"<blockquote style=\"border-left:3px solid #2b6cb0;padding-left:12px;"
        f"color:#333\">{escape(resumen)}</blockquote>"
        f"{medio_html}"
        f"<p><strong>Contacto del ciudadano:</strong> {escape(contacto)}</p>"
        "<p style=\"color:#888;font-size:12px\">Enviado automáticamente por el "
        "asistente Arándano FEN a solicitud del ciudadano.</p></div>"
    )
    text = (
        f"{'Caso para ' + entidad if directo else 'DERIVAR A: ' + entidad}\n\n"
        f"{urgencia_text}"
        f"Caso del ciudadano (solicitud o inquietud):\n{resumen}\n\n"
        f"{medio_text}"
        f"Contacto del ciudadano: {contacto}\n\n"
        "Enviado por el asistente Arándano FEN a solicitud del ciudadano."
    )
    return html, text


def send_derivation(entidad: str, resumen: str, *, user_id: str = "", nombre: str = "",
                    whatsapp: str = "", email: str = "", urgencia: str = "",
                    medio: str = "texto",
                    store: Optional[DerivationStore] = None) -> DerivationResult:
    """Compone y envía el correo de derivación. Fail-open (no lanza).

    `urgencia` (ver `app.entity_catalog.evaluar_urgencia`) etiqueta el asunto y
    el cuerpo del correo cuando es "alta"/"critica", para que la entidad
    receptora triage primero los casos con riesgo o pérdida en curso. `medio`
    ("texto" | "voz" | "imagen", ver `app.agent.turn_context`) queda registrado
    en Firestore y, si no fue texto escrito, también anotado en el correo.
    """
    from app.channels.email_sender import send_email

    destino, directo = _resolve_destino(entidad)
    etiqueta = "" if directo else "[DERIVAR] "
    prioridad = "🔴 URGENTE — " if urgencia in _URGENT_LEVELS else ""
    subject = f"{prioridad}{etiqueta}Caso de {nombre or 'ciudadano'} para {entidad}"
    html, text = _render(entidad, resumen, nombre=nombre, whatsapp=whatsapp,
                         email=email, directo=directo, urgencia=urgencia, medio=medio)
    ok = send_email(to=destino, subject=subject, html=html, text=text,
                    reply_to=email or None)
    try:
        (store or DerivationStore()).add(
            user_id=user_id, entidad=entidad, resumen=resumen, urgencia=urgencia,
            directo=directo, ok=ok, destino=destino, nombre=nombre,
            whatsapp=whatsapp, email=email, medio=medio,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("derivation_record_failed", error=str(exc))
    logger.info("derivation_sent", entidad=entidad, directo=directo, ok=ok,
               urgencia=urgencia, medio=medio)
    return DerivationResult(ok=ok, entidad=entidad, destino=destino, directo=directo)


def send_derivations(entidades: list[str], resumen: str, *, user_id: str = "",
                     nombre: str = "", whatsapp: str = "", email: str = "",
                     urgencia: str = "", medio: str = "texto",
                     store: Optional[DerivationStore] = None) -> MultiDerivationResult:
    """Canaliza el caso a TODAS las entidades involucradas (un correo por entidad).

    Deduplica por nombre (sin distinguir mayúsculas). Fail-open por entidad: el
    fallo de una no impide enviar a las demás.
    """
    if store is None:
        try:
            store = DerivationStore()
        except Exception as exc:  # noqa: BLE001
            logger.warning("derivation_store_init_failed", error=str(exc))

    seen: set[str] = set()
    solicitadas: list[str] = []
    enviadas: list[str] = []
    fallidas: list[str] = []
    for ent in entidades:
        name = (ent or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        solicitadas.append(name)
        res = send_derivation(name, resumen, user_id=user_id, nombre=nombre,
                              whatsapp=whatsapp, email=email, urgencia=urgencia,
                              medio=medio, store=store)
        (enviadas if res.ok else fallidas).append(name)
    logger.info("derivations_sent", solicitadas=len(solicitadas),
                enviadas=len(enviadas), fallidas=len(fallidas), urgencia=urgencia)
    return MultiDerivationResult(solicitadas=solicitadas, enviadas=enviadas,
                                 fallidas=fallidas)
