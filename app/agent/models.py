"""Factory de modelos de Vertex AI (Model Garden): LLM Gemini + embeddings.

Centraliza la creación de modelos para reusar configuración (proyecto, región,
safety settings) en toda la app. Los safety settings de Vertex son la primera
capa de guardrails (ver app/agent/guardrails.py para el resto).
"""
from __future__ import annotations

import functools

import vertexai
from langchain_google_vertexai import (
    ChatVertexAI,
    HarmBlockThreshold,
    HarmCategory,
    VertexAIEmbeddings,
)

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

# Safety settings: bloquear contenido peligroso/odioso/acoso/explícito (medio+).
SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
}


@functools.lru_cache(maxsize=1)
def init_vertex() -> None:
    """Inicializa el SDK de Vertex AI (una sola vez por proceso).

    Compartido por todo lo que use el SDK directamente además de los LLM de este
    módulo (p. ej. `app.agent.tools.image_gen_tools`, que llama a Imagen vía
    `vertexai.preview.vision_models.ImageGenerationModel`).
    """
    vertexai.init(project=settings.gcp_project_id, location=settings.gcp_location)


def llm_locations() -> list[str]:
    """Cadena de ubicaciones a intentar ante un 429 de capacidad (ver Settings).

    La preferida va primero. Se deduplica conservando el orden y se garantiza que
    `gcp_location` esté presente, para que una configuración incompleta nunca deje
    la lista vacía.
    """
    raw = [loc.strip() for loc in settings.vertex_llm_locations.split(",")]
    ordered = [loc for loc in raw if loc]
    if settings.gcp_location not in ordered:
        ordered.insert(0, settings.gcp_location)
    return list(dict.fromkeys(ordered))


def get_llm(*, pro: bool = False, temperature: float = 0.2,
            location: str | None = None) -> ChatVertexAI:
    """Devuelve un ChatVertexAI (Gemini). `pro=True` para razonamiento complejo.

    Gemini 2.5 razona internamente ("thinking") antes de responder, y eso consume
    del MISMO presupuesto que `max_output_tokens` — sin acotarlo, una respuesta que
    requiere más razonamiento (p. ej. la confirmación de una derivación a varias
    entidades) puede dejar el thinking devorar el budget y cortar el texto visible
    a media frase (bug real, ver `app.agent.fen_briefing`). Flash sí admite
    desactivarlo (`thinking_budget=0`); Pro NO admite desactivarlo del todo (mínimo
    128), así que se le acota a un presupuesto bajo en vez de dejarlo dinámico.

    `location` permite servir el MISMO modelo desde otro pool de capacidad de
    Vertex cuando el preferido devuelve 429 (ver `llm_locations` y el failover en
    `app.agent.orchestrator`). Por defecto, la región configurada.
    """
    init_vertex()
    model_name = settings.gemini_model_pro if pro else settings.gemini_model_fast
    return ChatVertexAI(
        model_name=model_name,
        project=settings.gcp_project_id,
        location=location or settings.gcp_location,
        temperature=temperature,
        max_output_tokens=4096,
        thinking_budget=1024 if pro else 0,
        max_retries=settings.vertex_llm_max_retries,
        safety_settings=SAFETY_SETTINGS,
    )


def is_capacity_error(exc: Exception) -> bool:
    """True si la excepción es un 429 de capacidad de Vertex (DSQ).

    Se comprueba por tipo y, como red de seguridad, por el texto: LangChain y el
    SDK envuelven la excepción en varias capas y no siempre propagan la clase
    original de google-api-core.
    """
    from google.api_core.exceptions import ResourceExhausted, TooManyRequests

    if isinstance(exc, (ResourceExhausted, TooManyRequests)):
        return True
    msg = str(exc)
    return "429" in msg or "resource exhausted" in msg.lower()


def invoke_with_failover(payload, *, pro: bool = False, temperature: float = 0.2):
    """Invoca el LLM cambiando de ubicación de Vertex ante un 429 de capacidad.

    Mismo mecanismo que el failover del agente ReAct
    (`app.agent.orchestrator._invoke_with_location_failover`) pero para las
    llamadas auxiliares de un solo turno (clasificadores, resúmenes, traducción,
    reranking...). Se centraliza aquí porque el 429 de DSQ afecta por igual a
    TODAS: bug real, el agente respondía con el failover ya puesto pero
    `concerns.classify_message` moría en el mismo 429 y la inquietud no llegaba a
    Firestore, así que la atención no aparecía en el Admin UI.

    `payload` es lo que se le pasaría a `.invoke()` (un prompt de texto o una
    lista de mensajes multimodales). Cualquier excepción que no sea de capacidad
    se propaga tal cual.
    """
    locations = llm_locations()
    last_exc: Exception | None = None
    for i, location in enumerate(locations):
        try:
            resp = get_llm(pro=pro, temperature=temperature,
                          location=location).invoke(payload)
            if i:
                logger.info("llm_failover_ok", location=location, intentos=i + 1)
            return resp
        except Exception as exc:  # noqa: BLE001
            if not is_capacity_error(exc):
                raise
            last_exc = exc
            logger.warning("llm_capacity_exhausted", location=location,
                           restantes=len(locations) - i - 1)
    assert last_exc is not None  # el bucle siempre corre ≥1 vez
    raise last_exc


@functools.lru_cache(maxsize=1)
def get_embeddings() -> VertexAIEmbeddings:
    """Modelo de embeddings multilingüe (corpus en español).

    `dimensions` fija la dimensión de salida (Matryoshka/output_dimensionality)
    para que coincida siempre con la del índice vectorial de Firestore ya
    creado (ver `Settings.embedding_dim`), sin importar qué `embedding_model`
    esté configurado. La librería ya aplica por defecto `task_type` distinto
    para `embed_documents` (RETRIEVAL_DOCUMENT) y `embed_query`
    (RETRIEVAL_QUERY), así que no hace falta pasarlo explícitamente aquí.
    """
    init_vertex()
    return VertexAIEmbeddings(
        model_name=settings.embedding_model,
        project=settings.gcp_project_id,
        location=settings.gcp_location,
        dimensions=settings.embedding_dim,
    )
