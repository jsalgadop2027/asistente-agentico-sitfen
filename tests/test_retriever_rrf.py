"""Tests de la fusión multi-query (RRF) y el reranker por Vertex AI Ranking API
del retriever — sin red real (httpx/credenciales monkeypatcheadas), sobre las
funciones puras del módulo (no se instancia AdvancedRetriever: su __init__
requiere GCP para embeddings/Firestore, igual que el resto del proyecto separa
las funciones puras testeables de los objetos que sí necesitan credenciales).
"""
import google.auth as _google_auth

import app.agent.retriever as retriever
from app.agent.retriever import RetrievedChunk, _reciprocal_rank_fusion, _rank_via_api
from app.config import settings


def _chunk(doc_id, source="doc.pdf", text="texto"):
    return RetrievedChunk(doc_id=doc_id, source=source, title="t", text=text,
                          chunk_index=0)


def test_rrf_ranks_by_combined_reciprocal_rank():
    a, b, c = _chunk("a"), _chunk("b"), _chunk("c")
    # 'a' es 1º en ambas listas -> debe ganar aunque 'b' aparezca en más listas
    # con peor posición.
    fused = _reciprocal_rank_fusion([[a, b], [a, c]])
    assert fused[0].doc_id == "a"
    assert {c.doc_id for c in fused} == {"a", "b", "c"}


def test_rrf_rewards_appearing_in_multiple_lists():
    a, b = _chunk("a"), _chunk("b")
    # 'a' aparece en las 3 listas en 2º lugar; 'b' solo en la 1ª, en 1er lugar.
    # RRF debe premiar la consistencia de 'a' sobre el pico aislado de 'b'.
    fused = _reciprocal_rank_fusion([[b, a], [a], [a]])
    assert fused[0].doc_id == "a"


def test_rrf_handles_empty_lists():
    assert _reciprocal_rank_fusion([]) == []
    assert _reciprocal_rank_fusion([[], []]) == []


class _FakeCredentials:
    token = "fake-token"

    def refresh(self, request):
        pass


class _FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


def test_rank_via_api_reorders_candidates_by_score(monkeypatch):
    candidates = [_chunk("a", text="poco relevante"),
                  _chunk("b", text="muy relevante"),
                  _chunk("c", text="algo relevante")]
    monkeypatch.setattr(_google_auth, "default", lambda: (_FakeCredentials(), None))
    monkeypatch.setattr(
        retriever.httpx, "post",
        lambda *a, **kw: _FakeResponse({"records": [
            {"id": "1", "score": 0.9}, {"id": "2", "score": 0.5}, {"id": "0", "score": 0.1},
        ]}),
    )

    ranked = _rank_via_api("consulta", candidates, top_n=3)

    assert ranked is not None
    assert [c.doc_id for c in ranked] == ["b", "c", "a"]


def test_rank_via_api_returns_none_on_http_failure(monkeypatch):
    candidates = [_chunk("a"), _chunk("b")]
    monkeypatch.setattr(_google_auth, "default", lambda: (_FakeCredentials(), None))

    def _boom(*a, **kw):
        raise RuntimeError("network down")

    monkeypatch.setattr(retriever.httpx, "post", _boom)

    assert _rank_via_api("consulta", candidates, top_n=2) is None


def test_rank_via_api_disabled_by_config_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "rag_ranking_api_enabled", False)
    candidates = [_chunk("a"), _chunk("b")]

    assert _rank_via_api("consulta", candidates, top_n=2) is None
