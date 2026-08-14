"""Observabilidad de producción con Confident AI (DeepEval LLM tracing).

Envía a Confident AI la traza de CADA consulta al agente: estructura del grafo
ReAct (nodos, llamadas al modelo, tools, retrievers), latencias, errores y
eventos de seguridad (rate-limit, inyección bloqueada). En el dashboard se
visualizan métricas de rendimiento, trazabilidad, monitoreo, seguimiento por
conversación (thread), seguridad y salud del chatbot.

Diseño DEFENSIVO (regla de oro): el tracing es best-effort y NUNCA debe tumbar la
ruta del usuario. Si DeepEval no está instalado, la key falta o la librería
falla, el chatbot responde con normalidad. Se activa con
CONFIDENT_TRACING_ENABLED=true.

Privacidad (Ley 29733 / GDPR — minimización de datos): los inputs/outputs pasan
por una máscara de PII (redact_pii) antes de subirse, coherente con la política
langsmith_hide_io del proyecto. Confident AI es un SaaS en EE. UU.
"""
from __future__ import annotations

import functools
import os
from typing import Any, Callable, Optional

from app.config import get_secret, settings
from app.observability import get_logger

logger = get_logger(__name__)

_configured = False
_active = False


def _pii_mask(data: Any) -> Any:
    """Máscara que DeepEval aplica a inputs/outputs antes de subir la traza.

    Reutiliza el guardrail de redacción del proyecto. Recorre estructuras
    (dict/list) para alcanzar el texto anidado que capturan las integraciones.
    """
    from app.agent.guardrails import redact_pii

    try:
        if isinstance(data, str):
            return redact_pii(data)
        if isinstance(data, dict):
            return {k: _pii_mask(v) for k, v in data.items()}
        if isinstance(data, (list, tuple)):
            return type(data)(_pii_mask(v) for v in data)
    except Exception:  # noqa: BLE001
        pass
    return data


def configure() -> None:
    """Configura el tracing de Confident AI. Idempotente y best-effort."""
    global _configured, _active
    if _configured:
        return
    _configured = True

    if not settings.enable_confident_tracing:
        return

    api_key = settings.confident_api_key or get_secret(
        settings.secret_confident_api_key, fallback_env="CONFIDENT_API_KEY"
    )
    if not api_key:
        logger.warning("confident_key_missing")
        return

    # DeepEval gatea TODO el posteo con su propia env CONFIDENT_TRACING_ENABLED:
    # tracing_enabled() == (os.getenv("CONFIDENT_TRACING_ENABLED","YES").upper()
    # == "YES"). Cualquier otro valor (p. ej. "true") APAGA el tracing y las
    # trazas ni se encolan. La forzamos a "YES" para garantizar que esté activa.
    os.environ["CONFIDENT_TRACING_ENABLED"] = "YES"

    try:
        from deepeval.tracing import trace_manager

        trace_manager.configure(
            confident_api_key=api_key,
            environment=settings.confident_environment,
            sampling_rate=settings.confident_sampling_rate,
            mask=_pii_mask if settings.confident_mask_pii else None,
            tracing_enabled=True,
        )
        _active = True
        logger.info(
            "confident_tracing_enabled",
            environment=settings.confident_environment,
            mask_pii=settings.confident_mask_pii,
            sampling_rate=settings.confident_sampling_rate,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("confident_configure_failed", error=str(exc))


def is_active() -> bool:
    return _active


def get_callback(
    *, user_id: str, thread_id: str, tier: str, metadata: Optional[dict] = None
):
    """CallbackHandler de LangChain para adjuntar a graph.invoke (o None).

    Auto-instrumenta el grafo ReAct: cada nodo, llamada al modelo y tool se
    convierte en un span anidado de la traza, con sus latencias y errores.
    """
    if not _active:
        return None
    try:
        from deepeval.integrations.langchain import CallbackHandler

        md = {"tier": tier}
        if metadata:
            md.update(metadata)
        return CallbackHandler(
            name="arandano-orchestrator",
            tags=[f"tier:{tier}", f"env:{settings.confident_environment}"],
            metadata=md,
            user_id=user_id,
            thread_id=thread_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("confident_callback_failed", error=str(exc))
        return None


def observe_root(name: str) -> Callable:
    """Decorador que envuelve una función como traza RAÍZ de Confident AI.

    Garantiza una traza por consulta incluso en las rutas que cortan antes de
    invocar al agente (rate-limit, guardrail) — clave para ver seguridad/salud.
    Si el tracing no está disponible/instalado, devuelve la función intacta:
    la decoración nunca añade riesgo ni dependencia dura.
    """

    def decorator(fn: Callable) -> Callable:
        try:
            from deepeval.tracing import observe

            observed = observe(name=name)(fn)
        except Exception:  # noqa: BLE001
            return fn

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # Si el tracing no se activó en runtime, ejecuta la función original
            # sin overhead ni traza.
            if not _active:
                return fn(*args, **kwargs)
            try:
                return observed(*args, **kwargs)
            finally:
                # La traza raíz ya terminó y está encolada: la posteamos de forma
                # SÍNCRONA aquí (no dependemos del hilo daemon del poster, que en
                # Cloud Run no drena de forma fiable y abandona las trazas).
                flush()

        return wrapper

    return decorator


def flush() -> None:
    """Postea sincrónicamente las trazas encoladas y registra el resultado.

    Diseñado para Cloud Run / entornos efímeros: en vez de confiar en el hilo
    daemon en background de DeepEval (que puede no drenar la cola antes de que la
    instancia se recicle), drena la cola en el hilo de la petición. Best-effort:
    cualquier fallo se registra y NO se propaga a la ruta del usuario.
    """
    if not _active:
        return
    try:
        from deepeval.tracing import trace_manager

        q = getattr(trace_manager, "_trace_queue", None)
        if q is None:
            return
        # Drena la cola y convierte cada Trace -> TraceApi (lo que hace el daemon
        # internamente). Luego flush_traces() postea SÍNCRONO y BLOQUEANTE vía
        # HTTP, imprimiendo el resultado. NOTA: post_trace() NO sirve aquí: solo
        # reencola y delega en el daemon (el que no drena en Cloud Run).
        apis = []
        while True:
            try:
                trace = q.get_nowait()
            except Exception:  # noqa: BLE001  (cola vacía)
                break
            try:
                apis.append(trace_manager.create_trace_api(trace))
            except Exception as exc:  # noqa: BLE001
                logger.warning("confident_convert_failed", error=str(exc))
        if apis:
            trace_manager.flush_traces(apis)
            logger.info("confident_flushed", posted=len(apis))
    except Exception as exc:  # noqa: BLE001
        logger.warning("confident_flush_failed", error=str(exc))


def annotate(**fields: Any) -> None:
    """Fija atributos en la traza raíz activa (input/output/tags/metadata/…).

    Best-effort: no-op si el tracing está inactivo o si la API cambia. No debe
    propagar excepciones a la ruta del usuario.
    """
    if not _active:
        return
    try:
        from deepeval.tracing import update_current_trace

        update_current_trace(**fields)
    except Exception as exc:  # noqa: BLE001
        logger.debug("confident_annotate_failed", error=str(exc))
