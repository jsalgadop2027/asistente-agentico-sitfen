"""Reenganche proactivo de usuarios inactivos por WhatsApp.

Un Cloud Scheduler invoca `/internal/re-engage` dos veces al día (8:00 y 17:00,
hora de Lima; ver `infra/03_deploy.ps1` y `app.main`) que corre
`run_reengagement()`. Se envía una **plantilla aprobada** (`reengage_template_sid`)
a los usuarios activos con opt-in que llevan `reengage_inactive_days` sin
actividad y no fueron reenganchados en los últimos `reengage_cooldown_days`. El
enfriamiento (`last_reengaged_at`) evita ser invasivo: aunque el job corra dos
veces por día, ningún usuario recibe más de un mensaje por ciclo de enfriamiento.

Requiere plantilla porque el mensaje se inicia fuera de la ventana de 24 h; para
mantener el CONTEXTO de la conversación (`_context_snippet`) el mensaje lleva
una segunda variable ({{2}}) con el objetivo de negocio del usuario o, si no
declaró uno, su inquietud abierta más reciente. La plantilla aprobada
(`REENGAGE_TEMPLATE_SID`) debe declarar esa segunda variable — si solo tiene
{{1}}, Twilio rechazará el envío; hay que actualizarla en la consola de Twilio/
WhatsApp Business Manager.

Fail-open: los errores por destinatario se acumulan y nunca se propagan.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


@dataclass
class ReengageResult:
    candidates: int = 0
    sent: int = 0
    failed: int = 0
    skipped_reason: str | None = None
    failures: list[str] = field(default_factory=list)


_DEFAULT_CONTEXT = "cómo va tu cultivo"


def _context_snippet(code: str) -> str:
    """Frase breve de lo último conversado con este usuario (variable {{2}}).

    Prioriza el objetivo de negocio declarado (`app.user_goals`); si no hay,
    la inquietud abierta más reciente (`app.concerns`). Fail-open: ante
    cualquier fallo o si no hay nada registrado, cae a una frase genérica.
    """
    try:
        from app.user_goals import GoalStore

        goal = GoalStore().get(code)
        if goal:
            return f"tu objetivo de {goal}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("reengage_context_goal_failed", error=str(exc))

    try:
        from app.concerns import ConcernStore

        rows = ConcernStore().list_recent_open_for_user(
            code, days=settings.concern_followup_days, limit=1)
        resumen = str((rows[0].get("resumen") or "")).strip() if rows else ""
        if resumen:
            return f"tu consulta sobre {resumen}"
    except Exception as exc:  # noqa: BLE001
        logger.warning("reengage_context_concern_failed", error=str(exc))

    return _DEFAULT_CONTEXT


def _finish(result: ReengageResult) -> ReengageResult:
    """Cierra la ejecución dejando SIEMPRE un rastro, incluso si no envió nada.

    El job corría por Cloud Scheduler dos veces al día y salía en silencio por
    tres caminos distintos (deshabilitado, sin plantilla, sin candidatos). Desde
    fuera los tres se veían igual —ningún log— y el endpoint responde 204 al
    instante porque el trabajo va en segundo plano, así que el código HTTP
    tampoco distinguía nada. En la práctica era imposible saber si "no había a
    quién escribir" o si la plantilla se había perdido en un despliegue y el
    reenganche llevaba semanas muerto. Un único evento de cierre, con el motivo,
    hace esa diferencia observable de un vistazo.
    """
    logger.info("reengage_done", candidates=result.candidates, sent=result.sent,
                failed=result.failed, motivo=result.skipped_reason or "ok")
    return result


def run_reengagement() -> ReengageResult:
    from app.channels.twilio_whatsapp import send_whatsapp_template
    from app.user_registry import get_user_registry

    result = ReengageResult()
    if not settings.reengage_enabled:
        result.skipped_reason = "reenganche deshabilitado"
        return _finish(result)
    template_sid = settings.reengage_template_sid
    if not template_sid:
        # Warning aparte del cierre: esto NO es un estado normal, es una mala
        # configuración que desactiva la función entera sin que nadie se entere
        # (p. ej. un despliegue que no propagó REENGAGE_TEMPLATE_SID).
        logger.warning("reengage_template_missing")
        result.skipped_reason = "sin plantilla de reenganche configurada"
        return _finish(result)

    registry = get_user_registry()
    try:
        candidates = registry.reengagement_candidates(
            inactive_minutes=settings.reengage_inactive_minutes,
            cooldown_minutes=settings.reengage_cooldown_minutes,
            limit=settings.reengage_max_per_run,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("reengage_candidates_failed", error=str(exc))
        result.skipped_reason = f"no se pudo obtener candidatos: {exc}"
        return _finish(result)

    result.candidates = len(candidates)
    if not candidates:
        result.skipped_reason = "sin usuarios inactivos a reenganchar"
        return _finish(result)

    for u in candidates:
        to = u.whatsapp if u.whatsapp.startswith("whatsapp:") else f"whatsapp:{u.whatsapp}"
        variables = {"1": u.nombre or "usuario", "2": _context_snippet(u.code)}
        try:
            ok = send_whatsapp_template(to, template_sid, variables)
        except Exception as exc:  # noqa: BLE001
            ok = False
            logger.warning("reengage_send_error", code=u.code, error=str(exc))
        if ok:
            result.sent += 1
            try:
                registry.mark_reengaged(u.code)
            except Exception as exc:  # noqa: BLE001
                logger.warning("reengage_mark_failed", code=u.code, error=str(exc))
        else:
            result.failed += 1
            result.failures.append(u.code)

    return _finish(result)
