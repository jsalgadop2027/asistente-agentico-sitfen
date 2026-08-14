"""Idioma de la respuesta y traducción de fragmentos recuperados.

Soporta tres comportamientos relacionados con el idioma:
  - El agente responde SIEMPRE en español (vía prompt), sin importar el idioma
    en que escribió el usuario.
  - Las citas textuales se traducen al español (vía prompt).
  - Los fragmentos recuperados (que pueden estar en inglés u otro idioma) se
    traducen EXPLÍCITAMENTE al idioma de la petición antes de pasarlos al LLM,
    solo cuando difieren (para no pagar traducción en el caso común es→es).

El idioma objetivo de la petición se propaga del orquestador a las tools con un
`contextvar` (seguro entre peticiones concurrentes: cada invocación tiene su
propio contexto).
"""
from __future__ import annotations

import contextvars
import logging
import re

logger = logging.getLogger("agent.translation")

_DEFAULT_LANG = "es"

# Marcador que las RAG tools anexan a su resultado: "[Fuentes disponibles: a, b]",
# "[Fuentes: a, b]" o "[Fuente: a]". Se usa para recolectar las fuentes reales del
# turno de forma determinista (no se confía en que el LLM las escriba).
_SOURCES_MARKER = re.compile(r"\[Fuentes?(?:\s+disponibles)?:\s*(.*?)\]", re.IGNORECASE)
_CHART_URL_MARKER = re.compile(r"\[GRAFICO_URL:\s*(\S+)\]")

# Etiqueta de la sección de fuentes según el idioma de la respuesta.
_SOURCES_LABEL = {
    "es": "Fuentes", "en": "Sources", "pt": "Fontes", "fr": "Sources",
    "de": "Quellen", "it": "Fonti", "zh-cn": "来源", "zh": "来源",
}
_LANG_NAMES = {
    "es": "español", "en": "inglés", "pt": "portugués", "fr": "francés",
    "de": "alemán", "it": "italiano", "zh-cn": "chino", "zh": "chino",
    "ja": "japonés", "ko": "coreano",
}

# Idioma objetivo (ISO 639-1) de la petición en curso. Lo fija el orquestador.
_target_lang: contextvars.ContextVar[str] = contextvars.ContextVar(
    "target_lang", default=_DEFAULT_LANG)


def set_target_lang(lang: str) -> None:
    _target_lang.set((lang or _DEFAULT_LANG).lower())


def get_target_lang() -> str:
    return _target_lang.get()


def lang_name(code: str) -> str:
    return _LANG_NAMES.get((code or "").lower(), code or _DEFAULT_LANG)


def sources_label(lang: str) -> str:
    """Etiqueta de la sección de fuentes en el idioma de la respuesta."""
    return _SOURCES_LABEL.get((lang or _DEFAULT_LANG).lower(), _SOURCES_LABEL["es"])


def extract_sources(messages) -> list[str]:
    """Recolecta, de forma determinista y deduplicada, las fuentes citadas en los
    resultados de las tools (ToolMessage) de un turno del agente.

    Lee el marcador '[Fuentes: ...]' que las RAG tools anexan a su salida, sin
    depender de que el LLM las escriba. Preserva el orden de aparición.
    """
    seen: list[str] = []
    for m in messages:
        if getattr(m, "type", None) != "tool":
            continue
        content = getattr(m, "content", "")
        if not isinstance(content, str):
            content = str(content)
        for match in _SOURCES_MARKER.finditer(content):
            for src in match.group(1).split(","):
                name = src.strip()
                if name and name not in seen:
                    seen.append(name)
    return seen


def extract_chart_url(messages) -> str | None:
    """Recupera, de forma determinista, la URL del gráfico generado por una tool
    de `app.agent.tools.chart_tools` en este turno (si la hubo).

    Lee el marcador '[GRAFICO_URL: ...]' del ToolMessage real en vez de depender
    de un `contextvar` propagado por la tool: LangGraph ejecuta cada tool call en
    un hilo del pool con un `contextvars.copy_context()` propio (ver
    `ToolNode._func`), así que una mutación hecha DENTRO de la tool nunca es
    visible fuera de `agent.invoke()` — mismo motivo por el que `extract_sources`
    ya usa este patrón de marcador en vez de un canal de estado compartido.
    """
    for m in messages:
        if getattr(m, "type", None) != "tool":
            continue
        content = getattr(m, "content", "")
        if not isinstance(content, str):
            content = str(content)
        match = _CHART_URL_MARKER.search(content)
        if match:
            return match.group(1)
    return None


def detect_lang(text: str) -> str:
    """Detecta el idioma del texto (ISO 639-1). Default 'es' si falla o es muy corto."""
    if not text or len(text.strip()) < 4:
        return _DEFAULT_LANG
    try:
        from langdetect import DetectorFactory, detect

        DetectorFactory.seed = 0  # determinismo entre ejecuciones
        return detect(text).lower()
    except Exception as exc:  # noqa: BLE001
        logger.warning("detect_lang_failed: %s", exc)
        return _DEFAULT_LANG


def _to_text(content) -> str:
    """Normaliza el contenido de la respuesta del LLM (str o bloques) a texto."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type", "text") == "text":
                if block.get("text"):
                    parts.append(block["text"])
        return "\n".join(parts).strip()
    return str(content).strip()


def translate_fragments(context: str, target_lang: str) -> str:
    """Traduce el texto de los fragmentos al idioma objetivo, preservando los
    marcadores `[n] (Fuente: ...)` y los nombres de archivo. Usa Gemini.

    Si la traducción falla, devuelve el contexto original (degradación segura:
    el LLM final aún puede traducir al responder, por instrucción de prompt).
    """
    from app.agent.models import invoke_with_failover

    target = lang_name(target_lang)
    prompt = (
        f"Traduce al {target} ÚNICAMENTE el texto de los siguientes fragmentos de "
        f"documentos. Conserva EXACTAMENTE los marcadores con el formato "
        f"'[n] (Fuente: nombre_archivo)' y NO traduzcas los nombres de archivo de "
        f"las fuentes. Mantén la estructura y el orden. Devuelve solo el texto "
        f"traducido, sin comentarios ni explicaciones.\n\n{context}"
    )
    try:
        out = _to_text(invoke_with_failover(prompt, temperature=0.0).content)
        return out or context
    except Exception as exc:  # noqa: BLE001
        logger.warning("translate_fragments_failed: %s", exc)
        return context
