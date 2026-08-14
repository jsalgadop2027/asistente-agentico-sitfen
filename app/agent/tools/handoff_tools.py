"""Tool de escalamiento a humano: avisa al equipo para que una persona intervenga.

El agente la usa cuando el usuario pide explícitamente hablar con una persona, o
cuando detecta angustia real o insatisfacción que no puede resolver por sí mismo.
Los datos de contacto del usuario se toman del contexto del turno (no del LLM).
Ver `app.handoff`.
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


@tool
def escalar_a_humano(motivo: str, resumen_conversacion: str) -> str:
    """Avisa al equipo humano para que una persona retome la conversación.

    Úsala SOLO cuando el usuario pida explícitamente hablar con una persona, o
    percibas angustia real o una insatisfacción que tú no puedes resolver. NO la
    uses para consultas que puedes responder con el corpus. `motivo` es una frase
    breve del porqué del escalamiento; `resumen_conversacion` resume lo tratado y
    lo que el usuario necesita. Devuelve la confirmación para el usuario.
    """
    if not settings.handoff_enabled:
        return ("Por ahora no puedo transferirte con una persona, pero sigo aquí "
                "para ayudarte en lo que necesites.")

    from app.agent.turn_context import get_current_user_id
    from app.handoff import send_handoff
    from app.user_registry import get_user_registry, looks_like_code

    nombre = whatsapp = email = ""
    uid = get_current_user_id() or ""
    if uid and looks_like_code(uid):
        try:
            rec = get_user_registry().get_by_code(uid)
            if rec is not None:
                nombre, whatsapp, email = rec.nombre, rec.whatsapp, rec.email
        except Exception as exc:  # noqa: BLE001
            logger.warning("handoff_user_lookup_failed", error=str(exc))

    motivo = (motivo or "").strip()
    if not motivo:
        return ("¿Me confirmas brevemente el motivo para avisar a una persona del "
                "equipo?")

    res = send_handoff(motivo, (resumen_conversacion or "").strip(), user_id=uid,
                       nombre=nombre, whatsapp=whatsapp, email=email)
    if not res.ok:
        return ("No pude avisar al equipo en este momento. Probemos de nuevo en unos "
                "minutos; mientras tanto, sigo ayudándote en lo que pueda.")
    return ("✅ Ya avisé a una persona del equipo para que te acompañe; te "
            "contactarán pronto. Mientras tanto, sigo aquí para lo que necesites.")
