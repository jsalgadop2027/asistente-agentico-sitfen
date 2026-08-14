"""Tool de derivación: envía la solicitud del usuario a la entidad pública pertinente.

El agente identifica la entidad más apropiada y, SOLO tras la confirmación explícita
del usuario, invoca esta tool. Los datos de contacto del usuario se toman del
contexto del turno (no los maneja el LLM). Ver `app.derivation`.
"""
from __future__ import annotations

from langchain_core.tools import tool

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


def ejecutar_derivacion(resumen: str, *, entidades_propuestas: str = "",
                        user_id: str = "") -> str:
    """Clasifica, envía y registra la derivación. Devuelve el texto para el usuario.

    Núcleo compartido por los DOS caminos que pueden derivar un caso:
      - la tool `derivar_solicitud_entidad`, cuando el LLM la invoca;
      - la confirmación determinista del orquestador (ver
        `app.pending_derivation`), que no depende de que el LLM haga nada.
    Se extrajo aquí para que ambos apliquen exactamente las mismas reglas de
    urgencia, elección de entidad y registro; duplicarlas habría dejado que los
    dos caminos divergieran con el tiempo.

    NO comprueba la confirmación del usuario: eso es responsabilidad de quien
    llama (el gate de la tool, o la máquina de estados del orquestador).
    """
    from app.agent.turn_context import get_current_medio
    from app.derivation import send_derivations
    from app.entity_catalog import (evaluar_urgencia, identificar_entidades,
                                    match_known_entities)
    from app.user_registry import get_user_registry, looks_like_code

    # Canal de ENTRADA real del turno ("texto"/"voz"/"imagen", ver
    # app.agent.turn_context): lo fija el orquestador antes de invocar al
    # agente, así que ya está disponible sin importar por cuál de los dos
    # caminos se llegó a esta función.
    medio = get_current_medio()

    nombre = whatsapp = email = ""
    if user_id and looks_like_code(user_id):
        try:
            rec = get_user_registry().get_by_code(user_id)
            if rec is not None:
                nombre, whatsapp, email = rec.nombre, rec.whatsapp, rec.email
        except Exception as exc:  # noqa: BLE001
            logger.warning("derivation_user_lookup_failed", error=str(exc))

    lista_llm = [e.strip() for e in (entidades_propuestas or "").replace(";", ",").split(",")
                if e.strip()]

    urgencia = evaluar_urgencia(resumen)
    clasificadas = identificar_entidades(resumen, urgencia=urgencia)
    propuestas = match_known_entities(lista_llm)
    lista = list(dict.fromkeys(clasificadas + propuestas)) or lista_llm
    if not lista:
        return ("No pude determinar a qué entidad corresponde tu caso. "
                "¿Puedes contarme un poco más de qué se trata?")

    res = send_derivations(lista, resumen, user_id=user_id, nombre=nombre,
                           whatsapp=whatsapp, email=email, urgencia=urgencia,
                           medio=medio)
    if not res.ok:
        return ("No pude enviar tu caso en este momento. Por favor intenta de "
                "nuevo en unos minutos.")
    nombres = ", ".join(res.enviadas)
    destinatario = "a tu correo registrado" if email else "por los canales del asistente"
    prioridad = (" Lo marqué como URGENTE para que le den atención prioritaria."
                if urgencia in ("alta", "critica") else "")
    return (f"✅ Listo. Registré y canalicé tu caso a {nombres} para tu atención "
            f"personalizada.{prioridad} Le daremos seguimiento y te responderán "
            f"{destinatario}.")


@tool
def derivar_solicitud_entidad(entidades: str, resumen_solicitud: str) -> str:
    """Canaliza por correo el caso del usuario a las entidades del Estado peruano.

    Sirve tanto para SOLICITUDES o trámites formales como para PUNTOS DE DOLOR
    (una preocupación, temor, inquietud, indecisión o desorientación) frente a los
    eventos que enfrenta, de modo que las entidades le den atención personalizada.
    Úsala SOLO después de que el usuario CONFIRME explícitamente ("Sí"). `entidades`
    son los nombres de TODAS las entidades públicas peruanas involucradas en el caso,
    separados por coma (a menudo es más de una; p. ej. "SENAMHI, INDECI, MIDAGRI" o
    "SENASA, CITEagroindustrial Chavimochic"). Incluye a los gestores técnicos de
    soporte tecnológico —CITEagroindustrial Chavimochic y la Red de CITE (RedCITE,
    ITP – PRODUCE)— cuando el caso tenga componente técnico, productivo o de calidad.
    `resumen_solicitud` es un resumen claro y formal del caso (la inquietud o el
    pedido del ciudadano). Devuelve la confirmación.
    """
    if not settings.derivation_enabled:
        return "La derivación a entidades públicas no está habilitada por ahora."

    from app.agent.guardrails import is_affirmative_confirmation
    from app.agent.turn_context import get_current_user_id, get_current_user_text

    # Gate de confirmación determinístico (OWASP LLM06, Excessive Agency): esta
    # acción es consecuente e irreversible (envía por correo el caso de un
    # ciudadano a una entidad del Estado). NO basta con que el LLM "decida"
    # invocar la tool tras interpretar la conversación —eso sería confiar en el
    # propio modelo para autorizar su propia acción, exactamente el vector que
    # una inyección de prompt podría explotar—. Se exige en código que el texto
    # REAL del turno actual del usuario sea una confirmación afirmativa clara.
    #
    # Nota: en la práctica el camino habitual ya NO pasa por aquí. El orquestador
    # ejecuta la derivación de forma determinista al recibir la confirmación (ver
    # `app.pending_derivation`), porque confiar en que el LLM invocara esta tool
    # en el turno correcto resultó poco fiable: narraba el éxito sin llamarla.
    # Esta tool se conserva para los casos en que el propio modelo la invoca con
    # un resumen explícito dentro del mismo turno.
    if not is_affirmative_confirmation(get_current_user_text() or ""):
        logger.warning("derivation_blocked_no_confirmation")
        return ("Antes de canalizar tu caso necesito tu confirmación explícita. "
                "¿Confirmas que deseas que lo envíe? Responde «Sí» para continuar.")

    uid = get_current_user_id() or ""

    # Segundo anclaje, contra el "Sí" HUÉRFANO: que el mensaje sea afirmativo no
    # dice A QUÉ asiente. Bug real: tras un ofrecimiento sobre una vía colapsada,
    # el usuario preguntó por costos portuarios y luego dijo "sí"; el orquestador
    # ya había descartado el pendiente (cambio de tema), pero el LLM invocó esta
    # tool igualmente y derivó el caso viejo. Se exige que exista un ofrecimiento
    # VIVO: si no lo hay, la confirmación no está anclada a nada y no se ejecuta.
    # (El camino normal ni siquiera llega aquí: el orquestador resuelve la
    # confirmación antes de invocar al LLM.)
    try:
        from app.pending_derivation import PendingDerivationStore

        pendiente = PendingDerivationStore().get(uid)
    except Exception as exc:  # noqa: BLE001
        logger.warning("pending_derivation_check_failed", error=str(exc))
        pendiente = None
    if pendiente is None:
        logger.warning("derivation_blocked_orphan_confirmation")
        # Sin signos de interrogación a propósito: este texto no debe
        # reconocerse como un nuevo ofrecimiento (ver pending_derivation.is_offer),
        # o un "sí" posterior quedaría anclado a un caso equivocado.
        return ("No tengo claro a qué caso te refieres. Cuéntame en un mensaje "
                "cuál es la situación que deseas que canalice al Estado y la "
                "gestiono de inmediato.")

    resumen = (resumen_solicitud or "").strip() or pendiente.caso
    return ejecutar_derivacion(resumen, entidades_propuestas=entidades or "",
                               user_id=uid)
