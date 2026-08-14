"""Búsqueda léxica (BM25) en memoria, para fusionar por RRF con la búsqueda
vectorial (Hybrid Search — Tier B de la mejora RAG).

Por qué hace falta además de la búsqueda vectorial: los embeddings capturan
similitud SEMÁNTICA, pero difuminan términos EXACTOS que importan mucho en
este dominio — números de resolución, códigos arancelarios, normas técnicas
("NTP 231.300"), números de informe ("N°12-2026"). Una pregunta que cita uno
de esos términos literalmente puede no traer el documento correcto por
similitud pura; BM25 (ranking léxico clásico, robusto y sin costo de LLM) sí
lo encuentra por coincidencia exacta de términos.

Firestore no tiene búsqueda de texto completo nativa, así que el índice se
construye EN MEMORIA a partir de todo el corpus (~20 000 chunks, ~24 MB de
texto) y se cachea por la vida de la instancia de Cloud Run. La construcción
tarda decenas de segundos (paginar Firestore + tokenizar), así que:
  - Se lanza en un hilo de fondo desde el arranque de la app (`app.main`,
    lifespan), NO bloqueando el health check ni la primera petición.
  - `search()` es best-effort: si el índice aún no está listo (arranque en
    frío reciente) devuelve [] y la fusión RRF sigue solo con resultados
    vectoriales — nunca bloquea el turno de un usuario esperando la
    construcción.
  - Sin TTL de refresco automático: un documento nuevo ingerido en producción
    se refleja en la siguiente instancia fría (Cloud Run recicla instancias
    con tráfico esporádico), igual que ya asume el resto del proyecto para
    caches de proceso (`get_embeddings`, `_retriever`). La búsqueda vectorial
    (Firestore KNN) sí ve el documento nuevo de inmediato — BM25 es un
    complemento, no la única vía de recuperación.
"""
from __future__ import annotations

import re
import threading
import time
import unicodedata

from rank_bm25 import BM25Okapi

from app.config import settings
from app.firestore_store import RetrievedChunk
from app.observability import get_logger

logger = get_logger(__name__)

_PAGE_SIZE = 500

_state: dict = {"index": None, "chunks": None, "building": False, "built_at": None}
_lock = threading.Lock()


def _strip_accents(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", text)
                   if not unicodedata.combining(c))


def tokenize(text: str) -> list[str]:
    """Tokenizador simple (minúsculas, sin acentos, alfanumérico). BM25 no
    necesita nada más sofisticado — es coincidencia léxica, no semántica."""
    return re.findall(r"[a-z0-9]+", _strip_accents(text or "").lower())


def build_index_from_chunks(
    chunks: list[RetrievedChunk],
) -> tuple[BM25Okapi, list[RetrievedChunk]]:
    """Construye el índice BM25 a partir de una lista de chunks ya en memoria
    (función pura, testable sin Firestore)."""
    corpus = [tokenize(c.text) for c in chunks]
    return BM25Okapi(corpus), chunks


def _scan_all_chunks() -> list[RetrievedChunk]:
    from app.firestore_store import FirestoreVectorStore

    store = FirestoreVectorStore()
    chunks: list[RetrievedChunk] = []
    last = None
    while True:
        query = (store.collection
                 .select(["doc_id", "source", "title", "chunk_index", "text"])
                 .order_by("__name__").limit(_PAGE_SIZE))
        if last is not None:
            query = query.start_after(last)
        batch = list(query.stream())
        if not batch:
            break
        for snap in batch:
            data = snap.to_dict() or {}
            chunks.append(RetrievedChunk(
                doc_id=data.get("doc_id", snap.id),
                source=data.get("source", "desconocido"),
                title=data.get("title", ""),
                text=data.get("text", ""),
                chunk_index=int(data.get("chunk_index", 0)),
            ))
        last = batch[-1]
        if len(batch) < _PAGE_SIZE:
            break
    return chunks


def _build_index_sync() -> None:
    t0 = time.time()
    try:
        chunks = _scan_all_chunks()
        index, chunks = build_index_from_chunks(chunks)
        with _lock:
            _state.update(index=index, chunks=chunks, building=False, built_at=time.time())
        logger.info("bm25_index_built", chunks=len(chunks),
                   seconds=round(time.time() - t0, 1))
    except Exception as exc:  # noqa: BLE001
        logger.warning("bm25_index_build_failed", error=str(exc))
        with _lock:
            _state["building"] = False


def ensure_index_building() -> None:
    """Lanza la construcción en un hilo de fondo si no hay una en curso ni un
    índice ya listo. Idempotente y no bloqueante — segura de llamar en cada
    petición como red de seguridad además del arranque de la app."""
    if not settings.rag_hybrid_search_enabled:
        return
    with _lock:
        if _state["building"] or _state["index"] is not None:
            return
        _state["building"] = True
    threading.Thread(target=_build_index_sync, daemon=True, name="bm25-index-build").start()


def is_ready() -> bool:
    return _state["index"] is not None


def search(query: str, top_k: int) -> list[RetrievedChunk]:
    """Top-k por score BM25. [] si el índice no está listo o si está
    deshabilitado — nunca bloquea ni lanza (fail-open)."""
    if not settings.rag_hybrid_search_enabled:
        return []
    ensure_index_building()
    index = _state["index"]
    chunks = _state["chunks"]
    if index is None or not chunks:
        return []
    tokens = tokenize(query)
    if not tokens:
        return []
    try:
        scores = index.get_scores(tokens)
    except Exception as exc:  # noqa: BLE001
        logger.warning("bm25_search_failed", error=str(exc))
        return []
    ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
    return [chunks[i] for i in ranked_idx[:top_k] if scores[i] > 0]
