"""Boletín bajo demanda del FEN vía Grounding con Google Search (Gemini nativo).

A diferencia de las demás tools del agente (RAG sobre el corpus propio,
AccuWeather, NOAA), esto consulta la web abierta en tiempo real para dar
advertencias, consejos y recomendaciones sobre el Fenómeno de El Niño con la
fuente siempre citada. Por eso vive AISLADO del loop ReAct conversacional (no
es una tool de `app.agent.tools`): se activa solo por el botón de
proactividad del avatar (`POST /api/fen-briefing`), nunca por decisión
implícita del LLM en medio de una conversación.

Usa el SDK `google-genai` directamente (no el `ChatVertexAI` de LangChain que
usa el resto del agente en `app.agent.models`) porque el grounding con Google
Search vía `langchain-google-vertexai` no expone hoy la tool nativa de
búsqueda; `google-genai` sí, y además devuelve `grounding_metadata` con las
fuentes estructuradas (título + URL) que necesitamos mostrar.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from google import genai
from google.genai import types

from app.agent.guardrails import sanitize_external_text
from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

_PROMPT = (
    "Eres SITFEN, el asistente de inteligencia comercial y estratégica para las "
    "Mypes agroindustriales del norte del Perú en el contexto del Fenómeno de El "
    "Niño (FEN). Busca la información más reciente disponible y redacta en "
    "español, en prosa breve (máximo 120 palabras), un boletín con advertencias, "
    "consejos y recomendaciones prácticas y accionables ante el FEN para un "
    "productor agroindustrial de esa zona. Sé concreto; no inventes cifras que "
    "no encuentres en la búsqueda."
)

_FALLBACK_TEXT = (
    "No pude generar el boletín del FEN en este momento. Intenta de nuevo en "
    "unos minutos."
)


@dataclass
class FenSource:
    title: str
    uri: str
    domain: str = ""


@dataclass
class FenBriefing:
    text: str
    sources: list[FenSource] = field(default_factory=list)


def generate_fen_briefing() -> FenBriefing:
    """Genera el boletín. Fail-open: ante cualquier error devuelve un aviso sin fuentes."""
    try:
        client = genai.Client(
            vertexai=True, project=settings.gcp_project_id, location=settings.gcp_location,
        )
        resp = client.models.generate_content(
            model=settings.gemini_model_fast,
            contents=_PROMPT,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())],
                temperature=0.2,
                # Gemini 2.5 razona internamente ("thinking") antes de responder;
                # eso consume del mismo presupuesto que max_output_tokens y, con
                # un límite bajo, dejaba el boletín cortado a media frase. Se
                # desactiva el thinking (no aporta aquí, es una consulta breve y
                # factual) y se deja margen amplio para el texto + el grounding.
                max_output_tokens=2048,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        # ASI01:2026 (Agent Goal Hijack vía contenido externo): a diferencia del
        # corpus curado, esto viene de la web abierta sin control editorial, así
        # que se neutraliza igual que el texto libre de AccuWeather/NOAA antes de
        # mostrarlo.
        raw_text = getattr(resp, "text", None) or ""
        text = sanitize_external_text(raw_text.strip(), fallback=_FALLBACK_TEXT)

        sources: list[FenSource] = []
        candidates = getattr(resp, "candidates", None) or []
        if candidates:
            meta = getattr(candidates[0], "grounding_metadata", None)
            for chunk in (getattr(meta, "grounding_chunks", None) or []):
                web = getattr(chunk, "web", None)
                if not web or not getattr(web, "uri", None):
                    continue
                domain = getattr(web, "domain", "") or ""
                title = sanitize_external_text(
                    getattr(web, "title", "") or domain or web.uri,
                    fallback=domain or "fuente",
                )
                sources.append(FenSource(title=title, uri=web.uri, domain=domain))
        return FenBriefing(text=text, sources=sources)
    except Exception as exc:  # noqa: BLE001
        logger.warning("fen_briefing_failed", error=str(exc))
        return FenBriefing(text=_FALLBACK_TEXT, sources=[])
