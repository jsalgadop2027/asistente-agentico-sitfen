"""Tests del índice BM25 (Hybrid Search) — sin Firestore ni hilos reales.

La razón de ser de esta pieza: un embedding difumina semánticamente términos
EXACTOS (códigos, números de norma/resolución) que sí importan en este
dominio. Los tests centrales verifican justamente eso: que un término exacto
hace ganar al chunk correcto por BM25, algo que la búsqueda vectorial pura
puede fallar.
"""
import app.agent.bm25_index as bm25
from app.config import settings
from app.firestore_store import RetrievedChunk


def _chunk(doc_id, text, source="doc.pdf"):
    return RetrievedChunk(doc_id=doc_id, source=source, title="t", text=text,
                          chunk_index=0)


def _reset_state():
    bm25._state.update(index=None, chunks=None, building=False, built_at=None)


def test_tokenize_strips_accents_and_lowercases():
    assert bm25.tokenize("Protocolo Fitosanitario Perú-China") == \
        ["protocolo", "fitosanitario", "peru", "china"]


def test_tokenize_empty_text():
    assert bm25.tokenize("") == []
    assert bm25.tokenize(None) == []


def test_exact_term_ranks_correct_chunk_first():
    """El caso de uso central de Hybrid Search: un código/norma EXACTO debe
    ganar por coincidencia léxica, aunque el resto del texto sea genérico."""
    chunks = [
        _chunk("a", "El manejo agronómico general del cultivo requiere buen drenaje."),
        _chunk("b", "La Norma Técnica Peruana NTP 231.300 regula la fibra en vellón."),
        _chunk("c", "La exportación de arándano creció en la última campaña."),
    ]
    index, indexed_chunks = bm25.build_index_from_chunks(chunks)
    scores = index.get_scores(bm25.tokenize("NTP 231.300"))
    best = indexed_chunks[max(range(len(scores)), key=lambda i: scores[i])]
    assert best.doc_id == "b"


def test_search_returns_empty_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "rag_hybrid_search_enabled", False)
    assert bm25.search("cualquier consulta", top_k=5) == []


def test_search_returns_empty_when_index_not_ready(monkeypatch):
    monkeypatch.setattr(settings, "rag_hybrid_search_enabled", True)
    _reset_state()
    # No lanza el hilo real de construcción en el test: lo neutralizamos para
    # que search() vea el índice como "aún no listo" de forma determinista.
    monkeypatch.setattr(bm25, "ensure_index_building", lambda: None)
    assert bm25.search("consulta", top_k=5) == []


def test_search_ranks_by_bm25_score_once_index_is_ready(monkeypatch):
    monkeypatch.setattr(settings, "rag_hybrid_search_enabled", True)
    # 3+ documentos: con solo 2, un término presente en un único documento
    # puede quedar con IDF=0 en la fórmula clásica de BM25 (caso degenerado
    # de corpus diminuto, no representativo del corpus real de ~20 000
    # chunks), y el filtro `score > 0` de search() lo descartaría.
    chunks = [
        _chunk("a", "Requisitos generales de exportación agrícola."),
        _chunk("b", "Protocolo fitosanitario Perú-China para arándano fresco."),
        _chunk("c", "Tarifas logísticas del puerto de embarque."),
    ]
    index, indexed_chunks = bm25.build_index_from_chunks(chunks)
    _reset_state()
    bm25._state.update(index=index, chunks=indexed_chunks)
    monkeypatch.setattr(bm25, "ensure_index_building", lambda: None)

    results = bm25.search("protocolo fitosanitario China", top_k=5)

    assert results and results[0].doc_id == "b"


def test_search_filters_out_zero_score_results(monkeypatch):
    monkeypatch.setattr(settings, "rag_hybrid_search_enabled", True)
    chunks = [_chunk("a", "Contenido totalmente ajeno a la consulta.")]
    index, indexed_chunks = bm25.build_index_from_chunks(chunks)
    _reset_state()
    bm25._state.update(index=index, chunks=indexed_chunks)
    monkeypatch.setattr(bm25, "ensure_index_building", lambda: None)

    assert bm25.search("terminos que no aparecen en ningun lado", top_k=5) == []


def test_ensure_index_building_is_idempotent(monkeypatch):
    _reset_state()
    monkeypatch.setattr(settings, "rag_hybrid_search_enabled", True)
    started = []

    class _FakeThread:
        def __init__(self, target, daemon=True, name=""):
            started.append(name)
            self._target = target

        def start(self):
            pass  # no ejecuta el build real en el test

    monkeypatch.setattr(bm25.threading, "Thread", _FakeThread)

    bm25.ensure_index_building()
    bm25.ensure_index_building()  # segunda llamada: no debe lanzar otro hilo

    assert len(started) == 1
