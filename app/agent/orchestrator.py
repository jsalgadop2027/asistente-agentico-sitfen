"""Agente orquestador (LangGraph) — punto único de entrada de las consultas.

Implementa el requisito de "un agente como elemento orquestador": un agente
ReAct (Gemini + tools) que decide qué herramientas usar, integrado con:
  - Guardrails de entrada/salida (seguridad).
  - Memoria conversacional en Firestore (continuidad multiusuario).
  - Trazas en LangSmith (observabilidad).

`AgentOrchestrator.answer()` es seguro para concurrencia: no guarda estado por
usuario en memoria del proceso; el estado vive en Firestore.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage

from app import confident_tracing
from app.agent.guardrails import (
    RateLimiter,
    check_input,
    check_output,
    is_affirmative_confirmation,
    pseudonymize,
    redact_pii,
)
from app.agent.memory import ConversationMemory
from app.agent.models import get_llm, is_capacity_error, llm_locations
from app.agent.router import route_model
from app.agent.skills import (OBJECTIVE_SECTION, ORCHESTRATOR_SYSTEM_PROMPT,
                              REASONING_EXAMPLE, TOOLS_SECTION)
from app.agent.tools import ALL_TOOLS
from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


def _content_to_text(content) -> str:
    """Normaliza el contenido de un AIMessage a texto plano.

    Gemini 2.5 puede devolver el contenido como lista de bloques
    (p. ej. [{'type': 'text', 'text': '...', 'thought_signature': '...'}]).
    Se extrae sólo el texto, descartando firmas de razonamiento y bloques
    no textuales, para no enviar basura al usuario por WhatsApp.
    """
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict):
                text = block.get("text")
                if text and block.get("type", "text") == "text":
                    parts.append(text)
        return "\n".join(p for p in parts if p).strip()
    return str(content).strip()


@dataclass
class AgentResponse:
    text: str
    blocked: bool = False
    sources: list[str] | None = None
    chart_url: str | None = None


@lru_cache(maxsize=16)
def _build_agent(pro: bool = False, location: str | None = None):
    """Construye el grafo ReAct (uno por tier del router y ubicación de Vertex).

    Se cachea por (`pro`, `location`) para no reconstruir el grafo en cada
    petición. El tamaño cubre holgadamente los 2 tiers × las ubicaciones de
    failover configuradas, así que en régimen todo sale de caché.
    """
    from langgraph.prebuilt import create_react_agent

    llm = get_llm(pro=pro, temperature=0.2, location=location)
    return create_react_agent(llm, ALL_TOOLS)


# Tools cuya ejecución es una ACCIÓN irreversible hacia fuera (correo al Estado o
# al equipo). El LLM no debe poder afirmar que ocurrieron si no ocurrieron.
_ACTION_TOOLS = ("derivar_solicitud_entidad", "escalar_a_humano")

# Afirmaciones de acción CONSUMADA (pretérito/perfecto), en contraste con los
# OFRECIMIENTOS ("puedo comunicar", "¿deseas que lo canalice?"), que son legítimos
# y no deben dispararse aquí. Sólo se buscan formas que declaran el hecho ya hecho.
_ACTION_CLAIM_RE = re.compile(
    r"\b("
    r"(?:ya\s+)?(?:he|hemos)\s+(?:comunicad|canalizad|derivad|escalad|registrad|"
    r"notificad|informad|enviad|transferid)\w*"
    r"|ya\s+(?:comuniqu|canalic|deriv|escal|registr|notifiqu|envi|transfer)\w*"
    r"|(?:tu|su)\s+(?:caso|solicitud|pedido|reporte)\s+(?:ya\s+)?(?:fue|ha\s+sido)\s+"
    r"(?:comunicad|canalizad|derivad|escalad|registrad|notificad|enviad|transferid)\w*"
    r"|qued[óo]\s+(?:registrad|canalizad|derivad)\w*"
    r")\b",
    re.IGNORECASE,
)


def _tool_was_used(messages, names: tuple[str, ...]) -> bool:
    """True si alguna de esas tools realmente se ejecutó en el turno.

    Se mira el `ToolMessage` REAL devuelto por LangGraph (que fija `name` con el
    nombre de la tool invocada), no lo que el LLM diga haber hecho.
    """
    for m in messages:
        if getattr(m, "type", None) != "tool":
            continue
        if (getattr(m, "name", "") or "") in names:
            return True
    return False


def _action_tool_succeeded(messages) -> bool:
    """True sólo si una tool de acción se ejecutó Y **completó** la acción.

    No basta con que la tool se haya invocado: cuando el gate de confirmación la
    rechaza (o el envío falla), igualmente queda un `ToolMessage` en el turno —
    con un texto que PIDE confirmación, no que la confirma. Tomar esa ejecución
    como respaldo dejaría pasar justo el caso peligroso: el LLM llama a la tool
    sin un "Sí" real, la tool se niega, y el LLM narra un éxito que no ocurrió.
    Ambas tools de acción prefijan su confirmación con "✅"; el resto de sus
    salidas (gate no superado, error de envío) no lo llevan.
    """
    for m in messages:
        if getattr(m, "type", None) != "tool":
            continue
        if (getattr(m, "name", "") or "") not in _ACTION_TOOLS:
            continue
        content = getattr(m, "content", "")
        if not isinstance(content, str):
            content = str(content)
        if "✅" in content:
            return True
    return False


def _strip_unbacked_action_claim(final: str, messages) -> tuple[str, bool]:
    """Neutraliza una afirmación de acción que NUNCA se ejecutó (OWASP LLM09).

    El gate determinista de `derivar_solicitud_entidad` impide DERIVAR sin
    confirmación real, pero nada impedía que el modelo DIJERA haberlo hecho. Bug
    real de producción: ante una vía colapsada, el agente respondió "He comunicado
    tu interés ... a SENASA y al CITEagroindustrial" sin invocar ninguna tool —
    ningún correo salió y el ciudadano quedó creyendo que el Estado ya estaba
    avisado. Aquí se contrasta la afirmación contra los `ToolMessage` reales del
    turno y, si no hay respaldo, se sustituye por una petición explícita de
    confirmación sobre el caso ACTUAL (mismo principio que el pie de fuentes: no
    se confía en lo que el LLM declara).

    Devuelve `(texto, se_sustituyó)`. Cuando `se_sustituyó` es True, quien llama
    NO debe tratar ese texto como un ofrecimiento nuevo para `_remember_offer`
    (ver `app.pending_derivation`): es un pedido de RECONFIRMACIÓN genérico
    ("¿Confirmas que lo envíe a las entidades correspondientes?"), no una oferta
    recién formulada sobre el asunto correcto. Bug real de producción: esa
    frase genérica coincide por accidente con el patrón que detecta
    ofrecimientos reales (`pending_derivation.is_offer`, por el "¿...que lo
    envíe...?"), así que sin esta bandera el sistema la registraba como un
    ofrecimiento nuevo y guardaba como "caso pendiente" el último mensaje
    sustantivo del usuario — que podía no tener NADA que ver con una
    derivación (p. ej. un "Sí" ambiguo tras pedir un gráfico terminó
    canalizando esa petición de gráfico a SENAMHI/ENFEN como si fuera un
    punto de dolor real).
    """
    if not _ACTION_CLAIM_RE.search(final or ""):
        return final, False
    if _action_tool_succeeded(messages):
        return final, False
    logger.warning("unbacked_action_claim_blocked", claim=(final or "")[:160])
    return (
        "Antes de dar por hecho nada: todavía NO he canalizado este caso. "
        "Para hacerlo necesito tu confirmación explícita sobre el asunto que "
        "acabas de plantearme. ¿Confirmas que lo envíe a las entidades "
        "correspondientes? Responde «Sí» y lo canalizo de inmediato."
    ), True


def _invoke_with_location_failover(pro: bool, messages: list, invoke_config: dict):
    """Invoca el agente cambiando de ubicación de Vertex ante un 429 de capacidad.

    Gemini 2.5 bajo demanda comparte capacidad por (ubicación, modelo) vía Dynamic
    Shared Quota; cuando ese pool se satura devuelve 429 aunque el proyecto no haya
    excedido ninguna cuota propia. Como los pools son independientes, se reintenta
    el MISMO modelo en la siguiente ubicación en vez de insistir en la saturada.
    Cualquier otra excepción se propaga tal cual (no es un problema de capacidad y
    reintentarla en otra región sólo añadiría latencia).
    """
    locations = llm_locations()
    last_exc: Exception | None = None
    for i, location in enumerate(locations):
        try:
            agent = _build_agent(pro, location)
            result = agent.invoke({"messages": messages}, config=invoke_config)
            if i:
                logger.info("agent_failover_ok", location=location, intentos=i + 1)
            return result
        except Exception as exc:  # noqa: BLE001
            if not is_capacity_error(exc):
                raise
            last_exc = exc
            logger.warning("agent_capacity_exhausted", location=location,
                           restantes=len(locations) - i - 1)
    assert last_exc is not None  # el bucle siempre corre ≥1 vez
    raise last_exc


class AgentOrchestrator:
    def __init__(self) -> None:
        self._memory = ConversationMemory()
        from app.agent.semantic_memory import SemanticMemory

        self._semantic = SemanticMemory()
        self._rate_limiter = RateLimiter()

    def _augment_with_ltm(self, system: str, user_id: str, summary: str,
                          query: str) -> str:
        """Antepone la memoria de largo plazo al contexto: resumen progresivo +
        recuerdos semánticos relevantes de interacciones pasadas del usuario.

        Fail-open: cualquier fallo de la memoria semántica no rompe la respuesta.
        """
        if not settings.ltm_enabled:
            return system
        # Bug real de producción: un "Sí" aislado del usuario (sin que TU turno
        # inmediatamente anterior haya propuesto una acción) fue interpretado como
        # confirmación de un asunto pendiente mencionado aquí abajo (p. ej. "esperando
        # que lo contacten"), disparando "escalar_a_humano" sobre un tema viejo y no
        # relacionado con el turno actual. Este bloque es SOLO trasfondo — nunca algo
        # pendiente de confirmar en el turno actual.
        ltm_caveat = (
            " Úsalo SOLO como trasfondo para entender quién es el usuario y "
            "personalizar tu respuesta — NUNCA como algo pendiente de confirmar ahora: "
            "una confirmación del usuario ('Sí') solo es válida si TÚ propusiste esa "
            "acción específica en tu mensaje inmediatamente anterior dentro de esta "
            "misma conversación."
        )
        if settings.ltm_summary_enabled and summary:
            system = (
                f"{system}\n\n=== MEMORIA DE LARGO PLAZO (resumen de conversaciones "
                f"previas con este usuario) ==={ltm_caveat}\n{summary}"
            )
        # Un "Sí"/"Ok" suelto no tiene contenido semántico propio: su embedding
        # es casi idéntico al de CUALQUIER otra confirmación pasada del mismo
        # usuario, así que el recall siempre termina trayendo de vuelta el
        # intercambio (irrelevante) que por azar quedó más cerca en el índice
        # vectorial — no el asunto real que se está confirmando. Bug real de
        # producción: cada "Sí" de un usuario recuperaba SIEMPRE el mismo
        # intercambio antiguo sobre un gráfico del ENFEN, y el LLM terminaba
        # repitiendo esa respuesta sin relación con lo que el usuario acababa
        # de pedir. El contexto útil de una confirmación ya lo cubren el
        # historial corto (turno inmediatamente anterior) y la derivación
        # pendiente determinista (`_resolve_pending_derivation`), no la
        # memoria semántica.
        if settings.ltm_semantic_enabled and not is_affirmative_confirmation(query):
            try:
                recalls = self._semantic.recall(user_id, query)
            except Exception as exc:  # noqa: BLE001
                logger.warning("ltm_recall_failed", error=str(exc))
                recalls = []
            if recalls:
                joined = "\n---\n".join(recalls)
                system = (
                    f"{system}\n\n=== RECUERDOS RELEVANTES DE INTERACCIONES PASADAS "
                    f"(memoria semántica) ==={ltm_caveat}\n{joined}"
                )
        return system

    def _augment_with_fase3(self, system: str, user_id: str) -> str:
        """Fase 3: inyecta el OBJETIVO de negocio del usuario y sus INQUIETUDES
        abiertas recientes para el acompañamiento proactivo in-session.

        Solo aplica a usuarios con código interno estable (registrados). Ambos
        bloques son fail-open: un fallo de Firestore no rompe la respuesta.
        """
        from app.user_registry import looks_like_code

        if not looks_like_code(user_id):
            return system

        if settings.goal_tracking_enabled:
            try:
                from app.user_goals import GoalStore

                goal = GoalStore().get(user_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("goal_recall_failed", error=str(exc))
                goal = None
            if goal:
                system = (
                    f"{system}\n\n=== OBJETIVO DEL USUARIO ===\n{goal}\n"
                    f"Ten presente este objetivo del usuario y, cuando encaje de forma "
                    f"natural, orienta tus respuestas y sugerencias a acercarlo a él — "
                    f"sin forzarlo. Si el mensaje ACTUAL del usuario trata de un asunto "
                    f"distinto (una pregunta, un pedido, un trámite, una queja), "
                    f"atiéndelo primero y por completo: este objetivo es solo trasfondo, "
                    f"nunca un reemplazo de la respuesta al asunto de ahora."
                )

        if settings.concern_followup_enabled:
            try:
                from app.concerns import ConcernStore

                open_concerns = ConcernStore().list_recent_open_for_user(
                    user_id, days=settings.concern_followup_days,
                    limit=settings.concern_followup_max,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("concern_followup_failed", error=str(exc))
                open_concerns = []
            if open_concerns:
                lines = "\n".join(
                    f"- [{c.get('tipo')}] {c.get('resumen')}" for c in open_concerns
                )
                # Mismo blindaje que el bloque de memoria de largo plazo (ver
                # _augment_with_ltm): estas inquietudes son TRASFONDO, nunca algo
                # pendiente de confirmar en el turno actual. Bug real de
                # producción: el usuario reportó una trocha colapsada, respondió
                # "Sí", y el agente amarró ese "Sí" a una inquietud ANTIGUA de
                # esta lista (capacitación en BPA) y afirmó haberla canalizado.
                system = (
                    f"{system}\n\n=== SEGUIMIENTO (inquietudes recientes de este "
                    f"usuario, aún sin cerrar) ===\n{lines}\n"
                    f"PRIORIDAD: el mensaje ACTUAL del usuario va SIEMPRE primero. Si "
                    f"trae un asunto propio (una pregunta, un pedido, un trámite, una "
                    f"queja), respóndelo o atiéndelo COMPLETO —incluida la oferta de "
                    f"canalizarlo si aplica la regla 11— antes de pensar en esta lista. "
                    f"Retomar una inquietud de aquí es SIEMPRE opcional y secundario: "
                    f"como mucho, UNA frase breve al cierre, y solo si no compite con "
                    f"el asunto del turno actual. NUNCA sustituyas tu respuesta al "
                    f"asunto actual por retomar algo de esta lista, y si el usuario no "
                    f"la tomó la última vez, no la repitas en el siguiente turno.\n"
                    f"IMPORTANTE: esta lista es SOLO trasfondo histórico. NUNCA la "
                    f"trates como algo pendiente de confirmar ahora: una respuesta "
                    f"afirmativa del usuario ('Sí') se refiere ÚNICAMENTE a la acción "
                    f"que TÚ propusiste en tu mensaje inmediatamente anterior, sobre "
                    f"el asunto del turno actual. Si el usuario acaba de plantear un "
                    f"caso nuevo, su 'Sí' es sobre ESE caso, jamás sobre una "
                    f"inquietud de esta lista."
                )
        return system

    def _resolve_pending_derivation(self, user_id: str,
                                    text: str) -> AgentResponse | None:
        """Ejecuta la derivación pendiente si el usuario acaba de confirmarla.

        Devuelve la respuesta ya lista (y el LLM no se invoca en ese turno), o
        None para seguir el flujo normal. Fail-open: cualquier fallo del store
        deja continuar la conversación con el agente.
        """
        from app.agent.guardrails import is_affirmative_confirmation
        from app.pending_derivation import PendingDerivationStore

        try:
            store = PendingDerivationStore()
            pending = store.get(user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("pending_derivation_read_failed", error=str(exc))
            return None

        if not is_affirmative_confirmation(text):
            # El usuario cambió de tema: el ofrecimiento caduca aquí mismo para
            # que un "sí" posterior no dispare este caso (bug real: un "sí" tras
            # preguntar por costos portuarios derivó un caso de 9 minutos antes).
            if pending is not None:
                logger.info("pending_derivation_discarded", motivo="cambio_de_tema")
                try:
                    store.clear(user_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning("pending_derivation_clear_failed", error=str(exc))
            return None

        if pending is None:
            return None

        from app.agent.tools.derivation_tools import ejecutar_derivacion

        try:
            texto = ejecutar_derivacion(pending.caso, user_id=user_id)
        except Exception as exc:  # noqa: BLE001
            logger.error("pending_derivation_failed", error=str(exc))
            return None
        try:
            store.clear(user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("pending_derivation_clear_failed", error=str(exc))
        logger.info("pending_derivation_executed", caso=pending.caso[:120])
        return AgentResponse(texto, blocked=False)

    def _remember_offer(self, user_id: str, reply: str, history,
                        current_text: str) -> None:
        """Guarda el caso si la respuesta del agente OFRECE canalizarlo.

        El caso es el último mensaje SUSTANTIVO del usuario (no un "Sí"), para
        que la confirmación del turno siguiente se ejecute sobre el asunto real.
        """
        from app.pending_derivation import (PendingDerivationStore, is_offer,
                                            last_substantive_user_message)

        if not is_offer(reply):
            return
        caso = last_substantive_user_message(history, current_text)
        if not caso:
            return
        try:
            PendingDerivationStore().set(user_id, caso)
            logger.info("pending_derivation_stored", caso=caso[:120])
        except Exception as exc:  # noqa: BLE001
            logger.warning("pending_derivation_store_failed", error=str(exc))

    @confident_tracing.observe_root("orchestrator.answer")
    def answer(self, user_id: str, text: str,
              on_before_agent: Callable[[bool], None] | None = None,
              medio: str = "texto") -> AgentResponse:
        """`on_before_agent` (opcional): se invoca justo antes de llamar al agente
        (que puede tardar varios segundos en tools/tier Pro), con `decision.pro`
        como único argumento. Pensado para que un canal lento como WhatsApp pueda
        avisar "estoy revisando tu consulta" mientras espera; no se llama en los
        atajos que responden sin invocar al agente (rate limit, guardrail de
        entrada, derivación pendiente). Fail-open: un fallo del callback no debe
        romper la respuesta.

        `medio` ("texto" | "voz" | "imagen"): canal de ENTRADA real del turno —
        WhatsApp lo fija según si el mensaje era una nota de voz transcrita o una
        imagen descrita (`text` ya viene como texto plano en ambos casos, así
        que sin este parámetro esa procedencia se perdía). Se propaga a las
        tools vía `turn_context` para que una derivación resultante (y el
        correo a la entidad) quede etiquetada con el canal real de origen."""
        # Identificador pseudonimizado y estable (HMAC): agrupa la conversación
        # por usuario en el dashboard (thread/user) SIN exponer el teléfono. Nota:
        # redact_pii colapsaría todos los teléfonos en la misma etiqueta, por eso
        # aquí se usa pseudonymize (token único por usuario).
        anon = pseudonymize(user_id)

        # 1) Rate limiting (anti-abuso / anti-DoS).
        if not self._rate_limiter.allow(user_id):
            confident_tracing.annotate(
                user_id=anon, thread_id=anon,
                input=redact_pii(text), output="[rate_limited]",
                tags=["security", "blocked:rate_limit"],
                metadata={"blocked": True, "reason": "rate_limit"},
            )
            return AgentResponse(
                "Has enviado muchas consultas en poco tiempo. Espera un momento "
                "y vuelve a intentarlo, por favor.",
                blocked=True,
            )

        # 2) Guardrail de entrada (inyección, longitud).
        guard = check_input(text)
        if not guard.allowed:
            confident_tracing.annotate(
                user_id=anon, thread_id=anon,
                input=redact_pii(text), output="[input_blocked]",
                tags=["security", "blocked:guardrail"],
                metadata={"blocked": True, "reason": "input_guardrail"},
            )
            return AgentResponse(guard.reason or "Consulta no permitida.", blocked=True)

        # 3) Idioma: el agente responde SIEMPRE en español, sin importar el
        #    idioma de la pregunta (las tools traducen a español los fragmentos
        #    recuperados si están en otro idioma).
        from app.agent.translation import lang_name, set_target_lang
        from app.agent.turn_context import (set_current_medio, set_current_user_id,
                                            set_current_user_text)

        target_lang = "es"
        set_target_lang(target_lang)
        # Propaga el usuario, el texto (ya saneado/normalizado) y el medio de
        # entrada del turno a las tools. El texto sirve de ancla determinística
        # para el gate de confirmación de acciones consecuentes (LLM06, ver
        # turn_context.py); el medio, para etiquetar el canal real de origen de
        # una eventual derivación (voz/imagen se pierde al pasar a texto plano).
        set_current_user_id(user_id)
        set_current_user_text(guard.sanitized_text)
        set_current_medio(medio)

        # 3a-bis) CONFIRMACIÓN DETERMINISTA de una derivación ya ofrecida.
        #     Se resuelve en código ANTES de invocar al LLM (ver
        #     app.pending_derivation): si el turno anterior ofreció canalizar un
        #     caso y el usuario acaba de confirmar, se ejecuta sobre ESE caso.
        #     Dejarlo en manos del modelo falló de dos formas en producción: no
        #     invocaba la tool (el usuario confirmaba una y otra vez sin que se
        #     canalizara nada) y, más tarde, ataba un "sí" a un caso viejo tras
        #     una consulta no relacionada. Si no hay confirmación, el pendiente
        #     se descarta: un "sí" posterior ya no puede resucitarlo.
        pending_resp = self._resolve_pending_derivation(user_id, guard.sanitized_text)
        if pending_resp is not None:
            self._memory.append(user_id, guard.sanitized_text, pending_resp.text)
            confident_tracing.annotate(
                user_id=anon, thread_id=anon,
                input=redact_pii(guard.sanitized_text), output=pending_resp.text[:400],
                tags=["derivation", "deterministic_confirmation"],
                metadata={"path": "pending_derivation"},
            )
            return pending_resp

        # 3b) Contexto: memoria de largo plazo (resumen + recuerdos semánticos) +
        #     historial reciente de corto plazo + skill de sistema.
        # Fail-open: un blip de Firestore aquí NO debe tumbar el turno entero (a
        # diferencia de los pasos previos, esto ya no tiene forma de devolver un
        # AgentResponse temprano sin perder el resto del pipeline) — se sigue sin
        # historial/resumen en vez de dejar que la excepción suba sin capturar
        # hasta _process_and_reply (main.py), donde el usuario de WhatsApp se
        # queda sin ninguna respuesta.
        try:
            history, summary = self._memory.load_state(user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory_load_failed", error=str(exc))
            history, summary = [], ""
        history_prompt = ConversationMemory.as_prompt(history)
        system = (f"{ORCHESTRATOR_SYSTEM_PROMPT}\n\n{OBJECTIVE_SECTION}\n\n"
                  f"{TOOLS_SECTION}\n\n{REASONING_EXAMPLE}")
        system = self._augment_with_ltm(system, user_id, summary, guard.sanitized_text)
        if history_prompt:
            system = f"{system}\n\n{history_prompt}"

        # 3b-bis) Personalización: si la sesión pertenece a un usuario registrado
        #    (el id de sesión es su código interno de 8 caracteres), el agente lo
        #    trata por su nombre; y en el PRIMER mensaje lo saluda por su nombre.
        from app.user_registry import registered_first_name

        first_name = registered_first_name(user_id)
        if first_name:
            if not history:
                system = (
                    f"{system}\n\n=== USUARIO ===\n"
                    f"Te escribe {first_name}, un usuario registrado, y es el inicio "
                    f"de la conversación: salúdalo por su nombre de forma cordial y "
                    f"breve antes de responder su consulta."
                )
            else:
                system = (
                    f"{system}\n\n=== USUARIO ===\n"
                    f"Te escribe {first_name}, un usuario registrado. Dirígete a él "
                    f"por su nombre con naturalidad cuando sea oportuno (sin repetirlo "
                    f"en cada frase)."
                )

        # 3b-ter) Fase 3: objetivo de negocio del usuario + seguimiento de sus
        #    inquietudes abiertas (acompañamiento proactivo in-session).
        system = self._augment_with_fase3(system, user_id)

        # Directiva de idioma inyectada dinámicamente con el idioma detectado.
        # El prompt base está en español; sin una orden explícita y con el idioma
        # concreto al final (recencia), Gemini tiende a responder en español
        # aunque la consulta y/o los fragmentos estén en otro idioma.
        system = (
            f"{system}\n\n=== IDIOMA DE RESPUESTA (OBLIGATORIO) ===\n"
            f"Redacta TODA tu respuesta única y completamente en "
            f"{lang_name(target_lang)}: explicaciones, listas, ofertas para "
            f"presentar documentos y citas textuales. Es independiente del idioma "
            f"de los documentos recuperados; si un fragmento está en otro idioma, "
            f"tradúcelo a {lang_name(target_lang)} al usarlo o citarlo."
        )

        # 3c) Router multimodelo Flash<->Pro: por defecto Flash (rápido/barato);
        #     Pro sólo si la consulta requiere razonamiento complejo. Mantiene el
        #     costo bajo sin sacrificar calidad en preguntas difíciles.
        decision = route_model(guard.sanitized_text)
        logger.info("model_routed", user_id=redact_pii(user_id),
                    tier=decision.tier.value, reason=decision.reason)

        # 3d) Aviso de "procesando" para canales lentos (ver docstring de
        #     `on_before_agent`): se dispara AQUÍ, ya con el tier decidido y justo
        #     antes de la llamada al agente que puede demorar, nunca antes (para
        #     no avisar en un turno que termina bloqueado/rate-limited sin llegar
        #     a invocar al agente).
        if on_before_agent is not None:
            try:
                on_before_agent(decision.pro)
            except Exception as exc:  # noqa: BLE001
                logger.warning("on_before_agent_failed", error=str(exc))

        # 4) Ejecución del agente ReAct (decide y usa tools).
        #    Se adjunta el CallbackHandler de Confident AI para trazar cada nodo,
        #    llamada al modelo y tool como spans anidados (rendimiento/salud).
        invoke_config: dict = {
            "recursion_limit": 8,
            "metadata": {"user_id": redact_pii(user_id)},
        }
        cb = confident_tracing.get_callback(
            user_id=anon, thread_id=anon, tier=decision.tier.value,
            metadata={"routed_reason": decision.reason},
        )
        if cb is not None:
            invoke_config["callbacks"] = [cb]
        try:
            result = _invoke_with_location_failover(
                decision.pro,
                [
                    SystemMessage(content=system),
                    HumanMessage(content=guard.sanitized_text),
                ],
                invoke_config,
            )
            final = _content_to_text(result["messages"][-1].content)
        except Exception as exc:  # noqa: BLE001
            logger.error("agent_error", error=str(exc))
            confident_tracing.annotate(
                user_id=anon, thread_id=anon,
                input=redact_pii(guard.sanitized_text), output="[agent_error]",
                tags=["error", f"tier:{decision.tier.value}"],
                metadata={"error": str(exc)[:200], "tier": decision.tier.value},
            )
            # Ante saturación de capacidad, pedir que "reformule" desorienta: el
            # texto del usuario no tiene nada que ver y reescribirlo no ayuda.
            if is_capacity_error(exc):
                return AgentResponse(
                    "Ahora mismo tengo mucha demanda y no pude procesar tu "
                    "consulta. Vuelve a enviármela en un par de minutos, por "
                    "favor — no necesitas cambiar nada de tu mensaje.",
                    blocked=False,
                )
            return AgentResponse(
                "Tuve un problema procesando tu consulta. ¿Puedes reformularla?",
                blocked=False,
            )

        # 5) Guardrail de salida.
        final = check_output(final)

        # 5a-bis) Antialucinación de ACCIONES: si el texto afirma haber canalizado
        #     o escalado el caso pero ninguna tool de acción se ejecutó realmente
        #     en este turno, se sustituye por una petición de confirmación. Es el
        #     mismo principio que el footer de fuentes: se contrasta contra los
        #     ToolMessage reales, no contra lo que el LLM afirma. `claim_stripped`
        #     baja más adelante para que ese texto de reconfirmación NUNCA se
        #     registre como un ofrecimiento nuevo (ver docstring de la función).
        final, claim_stripped = _strip_unbacked_action_claim(final, result["messages"])

        # 5b) Footer determinista de fuentes: recolecta las fuentes reales de TODAS
        #     las tools usadas en el turno y las anexa (no se confía en que el LLM
        #     las escriba). Etiqueta en el idioma de la respuesta.
        from app.agent.translation import (extract_chart_url, extract_sources,
                                            get_target_lang, sources_label)

        sources = extract_sources(result["messages"])
        if sources:
            final = f"{final.rstrip()}\n\n{sources_label(get_target_lang())}: " \
                    f"{', '.join(sources)}"

        # 5c) Persistencia de memoria: corto plazo + resumen progresivo (append) y
        #     memoria semántica de largo plazo (recuerdo recuperable). Ambas son
        #     por usuario y fail-open: `final` ya está calculado y listo para el
        #     usuario, así que un fallo de Firestore aquí no debe tirar la
        #     respuesta — como mucho, se pierde ese turno de memoria (se
        #     reconstruye con el próximo mensaje).
        try:
            self._memory.append(user_id, guard.sanitized_text, final)
        except Exception as exc:  # noqa: BLE001
            logger.warning("memory_append_failed", error=str(exc))
        # No indexar confirmaciones vacías de contenido ("Sí", "Ok"): un
        # embedding casi idéntico al de cualquier otra confirmación pasada del
        # mismo usuario solo iría a contaminar futuros recalls (ver el caveat
        # en `_augment_with_ltm`, misma raíz del bug).
        if (settings.ltm_enabled and settings.ltm_semantic_enabled
                and not is_affirmative_confirmation(guard.sanitized_text)):
            self._semantic.add(user_id, guard.sanitized_text, final)

        # 5c-ter) Si la respuesta OFRECE canalizar el caso, se guarda cuál es para
        #     que la confirmación del siguiente turno lo ejecute de forma
        #     determinista, sin depender de que el LLM invoque la tool. NUNCA
        #     sobre el texto de reconfirmación genérico de arriba (claim_stripped):
        #     ese texto no es una oferta recién formulada sobre el asunto correcto,
        #     y guardarlo como tal derivó una vez una petición de gráfico del
        #     ENFEN a SENAMHI como si fuera un punto de dolor real.
        if not claim_stripped:
            self._remember_offer(user_id, final, history, guard.sanitized_text)
        logger.info("agent_answered", user_id=redact_pii(user_id),
                    chars=len(final), sources=len(sources),
                    tier=decision.tier.value)

        # 5c-bis) Captura de inquietudes (#3): clasifica el mensaje del usuario en
        #     reclamo/pedido/sugerencia/recomendación y lo guarda para el informe
        #     diario (#8). Fire-and-forget en un hilo: no añade latencia ni rompe
        #     la respuesta (fail-open dentro del propio módulo).
        if settings.concern_capture_enabled:
            from app.concerns import capture_concern_async

            capture_concern_async(user_id, guard.sanitized_text)

        # 5d) Traza raíz de Confident AI: input/output (enmascarados) y métricas
        #     del turno (tier del router, nº de fuentes, longitud, idioma).
        confident_tracing.annotate(
            user_id=anon, thread_id=anon,
            input=redact_pii(guard.sanitized_text), output=redact_pii(final),
            tags=[f"tier:{decision.tier.value}", f"lang:{target_lang}"],
            metadata={
                "blocked": False,
                "tier": decision.tier.value,
                "sources": len(sources),
                "chars": len(final),
                "lang": target_lang,
            },
        )
        return AgentResponse(final, sources=sources or None,
                             chart_url=extract_chart_url(result["messages"]))


@lru_cache(maxsize=1)
def get_orchestrator() -> AgentOrchestrator:
    return AgentOrchestrator()
