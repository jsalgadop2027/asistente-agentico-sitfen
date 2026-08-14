"""Tools de RAG del agente, implementadas con LangChain @tool.

Todas se apoyan en el AdvancedRetriever (multi-query + KNN Firestore + rerank).
Las tools especializadas enriquecen la consulta con contexto de dominio para
mejorar la recuperación, demostrando el patrón tool+skill por funcionalidad.

El retriever se inicializa de forma perezosa para no requerir GCP en import-time
(facilita los tests unitarios sin credenciales).
"""
from __future__ import annotations

import re
import time
import unicodedata
from functools import lru_cache

from langchain_core.tools import tool

from app.agent.skills import NO_CONTEXT_FALLBACK
from app.observability import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _retriever():
    from app.agent.retriever import AdvancedRetriever

    return AdvancedRetriever()


def _localize(result) -> str:
    """Traduce los fragmentos al idioma de la petición si están en otro idioma.

    Detecta el idioma del contenido recuperado; si coincide con el idioma objetivo
    (el de la pregunta del usuario), no traduce (caso común es→es, costo nulo).
    """
    from app.agent.translation import detect_lang, get_target_lang, translate_fragments

    target = get_target_lang()
    sample = " ".join(c.text for c in result.chunks)[:1000]
    if not sample or detect_lang(sample) == target:
        return result.context
    logger.info("translating_fragments", target=target)
    return translate_fragments(result.context, target)


def _run_rag(query: str, *, domain_hint: str = "") -> str:
    augmented = f"{domain_hint} {query}".strip() if domain_hint else query
    result = _retriever().retrieve(augmented)
    if not result.chunks:
        return NO_CONTEXT_FALLBACK
    fuentes = ", ".join(result.sources)
    return f"{_localize(result)}\n\n[Fuentes disponibles: {fuentes}]"


@tool
def consultar_base_conocimiento(consulta: str) -> str:
    """Busca información general en el corpus documental del arándano peruano.
    Úsala para cualquier pregunta sobre cultivo, exportación, mercados, sanidad
    o comercio del arándano que no encaje en una herramienta más específica."""
    return _run_rag(consulta)


@tool
def consultar_requisitos_exportacion(consulta: str) -> str:
    """Busca requisitos, documentación, certificaciones y protocolos sanitarios
    para exportar arándano peruano (p. ej. documentos para exportar, protocolo
    fitosanitario con China, certificación orgánica)."""
    return _run_rag(
        consulta,
        domain_hint="requisitos documentación certificación protocolo exportación",
    )


@tool
def consultar_tarifas_y_costos(consulta: str) -> str:
    """Busca tarifas, costos logísticos, de certificación o de servicios
    relacionados con la exportación del arándano (tarifario, costos de campaña)."""
    return _run_rag(consulta, domain_hint="tarifa costo precio logística certificación")


@tool
def consultar_inteligencia_comercial(consulta: str) -> str:
    """Busca inteligencia de mercado: demanda, países destino, oportunidades,
    competitividad, sostenibilidad y tendencias del arándano peruano."""
    return _run_rag(
        consulta,
        domain_hint="mercado demanda oportunidad competitividad tendencia exportación",
    )


@tool
def resumir_contenido(tema: str) -> str:
    """Genera un resumen ejecutivo sobre un tema del arándano, recuperando y
    sintetizando los fragmentos más relevantes del corpus."""
    result = _retriever().retrieve(tema, use_multiquery=True)
    if not result.chunks:
        return NO_CONTEXT_FALLBACK
    fuentes = ", ".join(result.sources)
    return (f"Contenido a sintetizar (resume en viñetas para el usuario):\n"
            f"{_localize(result)}\n\n[Fuentes: {fuentes}]")


@tool
def presentar_documento_nuevo(nombre_documento: str = "") -> str:
    """Presenta el contenido de un documento RECIÉN incorporado y vectorizado en
    la base de conocimiento. Úsala cuando el usuario confirme (responda "Sí") que
    desea conocer un documento nuevo que se acaba de añadir, o pida presentar,
    mostrar o resumir ese documento nuevo. Si no se indica `nombre_documento`,
    toma el último documento incorporado. Devuelve los fragmentos del documento
    para que los presentes al usuario de forma clara y bien estructurada."""
    from app.firestore_store import FirestoreVectorStore
    from app.kb_events import KBEventStore

    events = KBEventStore()
    event = events.find(nombre_documento) if nombre_documento else None
    if event is None:
        event = events.latest()
    if event is None or not event.source:
        return ("No encontré ningún documento nuevo registrado en la base de "
                "conocimiento para presentar.")

    chunks = FirestoreVectorStore().get_document_chunks(event.source, limit=30)
    if not chunks:
        return (f"El documento «{event.title}» figura como incorporado, pero no "
                "pude recuperar su contenido. Intenta de nuevo en un momento.")

    events.mark_announced(event.source)
    cuerpo = "\n\n".join(c.text for c in chunks)[:12000]
    logger.info("presentar_documento_nuevo", source=event.source, chunks=len(chunks))
    return (
        f"Documento recién incorporado a la base de conocimiento: «{event.title}» "
        f"(fuente: {event.source}, {event.chunks} fragmentos).\n\n"
        "Preséntalo al usuario EN EL IDIOMA DE SU CONSULTA (traduce el contenido si "
        "está en otro idioma) con un título, una breve introducción de qué trata y "
        "los puntos clave en viñetas. Sé fiel a este contenido y no inventes datos."
        f"\n\nContenido del documento:\n{cuerpo}\n\n"
        f"[Fuente: {event.source}]"
    )


# --------------------- "último documento de una serie": fecha real, no similitud
# Bug detectado en producción: ante "¿cuál es el último informe de ENFEN?", la
# recuperación semántica (consultar_base_conocimiento) no tiene noción de
# cronología — devuelve lo semánticamente más parecido a la pregunta, no lo más
# reciente por fecha, así que el LLM citó un informe de meses atrás como "el
# último". El corpus tiene VARIAS series periódicas con el mismo riesgo (ENFEN
# mensual, reportes de exportación ADEX/CIEN, informes mensuales PROMPERÚ...),
# así que esta tool es genérica: dado un tema/serie, resuelve la fecha real de
# cada documento candidato a partir de su nombre de archivo (el corpus no trae
# un campo de fecha estructurado en Firestore) y trae el contenido del que de
# verdad es el más reciente, para que la respuesta quede anclada a un hecho
# verificado en vez de a un ranking de similitud.
_SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "setiembre": 9, "septiembre": 9, "octubre": 10,
    "noviembre": 11, "diciembre": 12,
}
_DOCUMENT_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})?\D{0,6}(?P<month>" + "|".join(_SPANISH_MONTHS) + r")"
    r"\D{0,6}(?P<year>\d{4})",
    re.IGNORECASE,
)
_LATEST_DOC_CACHE_TTL_SECONDS = 3600

# Palabras demasiado genéricas para servir de filtro por sí solas (si se
# quitan todos los tokens de `tema`, no hay con qué discriminar la serie).
_STOPWORDS = {
    "el", "la", "los", "las", "de", "del", "informe", "informes", "reporte",
    "reportes", "documento", "documentos", "mas", "reciente", "recientes",
    "ultimo", "ultima", "ultimos", "ultimas", "que", "cual", "nuevo", "nueva",
}


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))


def parse_document_date(source: str) -> tuple[int, int, int] | None:
    """Extrae (año, mes, día) del nombre de archivo de un documento periódico.

    Los informes del corpus (ENFEN, ADEX/CIEN, PROMPERÚ...) usan más de una
    decena de convenciones de nombre distintas (con o sin día, con "N° xx-AAAA",
    con conectores "de"/"del", mayúsculas/minúsculas...). Devuelve None si no
    logra reconocer un mes en español + año de 4 dígitos (p. ej. informes viejos
    con mes abreviado a 3 letras) — esos simplemente quedan fuera del ranking de
    "más reciente", lo cual es seguro porque nunca son los más nuevos.
    """
    match = _DOCUMENT_DATE_RE.search(_strip_accents(source))
    if not match:
        return None
    month = _SPANISH_MONTHS[match.group("month").lower()]
    year = int(match.group("year"))
    day_raw = match.group("day")
    day = int(day_raw) if day_raw and 1 <= int(day_raw) <= 31 else 1
    return (year, month, day)


def _tokenize_hint(tema: str) -> tuple[str, ...]:
    normalized = _strip_accents(tema or "").lower()
    tokens = [t for t in re.findall(r"[a-z0-9]+", normalized)
             if len(t) > 2 and t not in _STOPWORDS]
    return tuple(sorted(set(tokens)))


@lru_cache(maxsize=64)
def _find_latest_document_cached(tokens: tuple[str, ...],
                                 _hour_bucket: int) -> tuple[str, str] | None:
    """(source, title) del documento con la fecha más reciente cuyo nombre de
    archivo contiene TODOS los `tokens`. Cacheado por hora (`_hour_bucket`,
    ver `_find_latest_document`): evita re-escanear `kb_events` en cada
    llamada sin quedar indefinidamente obsoleto si se ingiere un documento
    nuevo en producción (no requiere redeploy para reflejarlo).

    Lee `kb_events` (un documento por fuente ingerida, ~200 en total) en vez de
    escanear la colección de chunks (~20 000 documentos): mismo resultado,
    muchas veces más rápido.
    """
    from app.kb_events import KBEventStore

    best: tuple[tuple[int, int, int], str, str] | None = None
    try:
        for snap in KBEventStore().collection.stream():
            data = snap.to_dict() or {}
            source = data.get("source") or ""
            norm_source = _strip_accents(source).lower()
            if not all(t in norm_source for t in tokens):
                continue
            fecha = parse_document_date(source)
            if fecha is None:
                continue
            if best is None or fecha > best[0]:
                best = (fecha, source, data.get("title") or source)
    except Exception as exc:  # noqa: BLE001
        logger.warning("latest_document_lookup_failed", error=str(exc))
        return None

    if best is None:
        return None
    _, source, title = best
    return source, title


def _find_latest_document(tema: str) -> tuple[str, str] | None:
    tokens = _tokenize_hint(tema)
    if not tokens:
        return None
    return _find_latest_document_cached(tokens, int(time.time() // _LATEST_DOC_CACHE_TTL_SECONDS))


@tool
def consultar_documento_mas_reciente(tema: str) -> str:
    """Trae el documento MÁS RECIENTE por fecha real (no por similitud
    semántica) de una serie periódica de informes del corpus (p. ej. informes
    técnicos ENFEN, reportes de exportación ADEX/CIEN, informes mensuales de
    PROMPERÚ). Úsala SIEMPRE que el usuario pregunte explícitamente por "el
    último/más reciente informe/reporte de X" — no uses
    consultar_base_conocimiento para esa pregunta específica, porque la
    búsqueda semántica no distingue cronología y puede traer un documento
    antiguo por error. `tema` debe ser una o dos palabras clave DISTINTIVAS de
    la serie (p. ej. "ENFEN", "ADEX exportaciones", "PROMPERÚ informe
    mensual"), no la pregunta completa del usuario. Para preguntas sobre el
    HISTÓRICO (no "el último"), sigue usando la base de conocimiento
    general."""
    from app.firestore_store import FirestoreVectorStore

    found = _find_latest_document(tema)
    if found is None:
        return (f"No encontré ninguna serie de informes que coincida con «{tema}» "
                "en la base de conocimiento para determinar cuál es el más reciente.")
    source, title = found

    chunks = FirestoreVectorStore().get_document_chunks(source, limit=30)
    if not chunks:
        return (f"Identifiqué que el documento más reciente de «{tema}» es "
                f"«{title}», pero no pude recuperar su contenido ahora mismo. "
                "Intenta de nuevo en un momento.")

    cuerpo = "\n\n".join(c.text for c in chunks)[:12000]
    logger.info("consultar_documento_mas_reciente", tema=tema, source=source,
               chunks=len(chunks))
    return (
        f"Este ES, verificado por fecha (no por similitud semántica), el "
        f"documento MÁS RECIENTE de «{tema}» incorporado a la base de "
        f"conocimiento: «{title}». NO menciones un documento distinto como "
        "\"el más reciente\" — este es el correcto; si el usuario pregunta "
        "por periodos anteriores, usa consultar_base_conocimiento para esos."
        f"\n\nContenido:\n{cuerpo}\n\n"
        f"[Fuente: {source}]"
    )
