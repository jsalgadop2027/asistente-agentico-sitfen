"""Recuperador RAG avanzado: multi-query + búsqueda vectorial + reranking.

Técnicas aplicadas (requisito "RAG más avanzado del mercado"):
  1. Expansión/reescritura de consulta (multi-query) para mayor recall.
  2. Búsqueda KNN nativa en Firestore por cada sub-consulta.
  3. Fusión por Reciprocal Rank Fusion (RRF, Cormack et al. 2009): combina los
     rankings de las distintas sub-consultas por POSICIÓN relativa en cada
     lista, no por distancia cruda — las distancias de embeddings de
     reformulaciones distintas no son directamente comparables entre sí, así
     que promediarlas/ordenarlas juntas (el enfoque anterior) subestima
     candidatos que solo una sub-consulta encontró pero en 1er lugar.
  4. Deduplicación exacta (mismo chunk) + colapso de near-duplicates (misma
     fuente, texto casi idéntico por el solape entre chunks vecinos).
  5. Reranking con un cross-encoder real (Vertex AI Ranking API) — un modelo
     entrenado específicamente para ranking de pasajes, no un LLM generalista
     al que se le pide ordenar índices en un prompt (más preciso, más barato,
     sin riesgo de "alucinar" un orden inválido). Fail-open: si la API no
     está disponible, cae al reranking por prompt con Gemini (mecanismo
     original), mostrando el texto completo del chunk sin truncar.
  6. Construcción de contexto con citaciones para grounding.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher

import httpx

from app.agent.models import get_embeddings, invoke_with_failover
from app.config import settings
from app.firestore_store import FirestoreVectorStore, RetrievedChunk
from app.observability import get_logger

logger = get_logger(__name__)

# Reciprocal Rank Fusion: constante estándar de la literatura (Cormack et al.
# 2009 usan k=60; poco sensible al valor exacto, amortigua el peso de los
# primeros puestos frente a 1/rank puro).
_RRF_K = 60

_RANKING_API_URL = (
    "https://discoveryengine.googleapis.com/v1/projects/{project}/locations/"
    "global/rankingConfigs/default_ranking_config:rank"
)
_RANKING_MODEL = "semantic-ranker-512@latest"
_RANKING_TIMEOUT = 10

_MULTIQUERY_PROMPT = (
    "Eres un asistente experto en inteligencia comercial del arándano peruano. "
    "Genera {n} reformulaciones breves y diversas de la siguiente consulta para "
    "mejorar la búsqueda documental. Devuelve SOLO una lista JSON de strings.\n\n"
    "Consulta: {query}"
)

_RERANK_PROMPT = (
    "Consulta del usuario:\n{query}\n\n"
    "A continuación hay fragmentos numerados de documentos. Devuelve SOLO un "
    "arreglo JSON con los índices (enteros) de los {n} fragmentos MÁS relevantes "
    "para responder la consulta, del más al menos relevante.\n\n{candidates}"
)


@dataclass
class RetrievalResult:
    chunks: list[RetrievedChunk]

    @property
    def context(self) -> str:
        """Bloque de contexto numerado con citaciones para el prompt del LLM."""
        parts = []
        for i, c in enumerate(self.chunks, 1):
            parts.append(f"[{i}] (Fuente: {c.source})\n{c.text}")
        return "\n\n".join(parts)

    @property
    def sources(self) -> list[str]:
        seen: list[str] = []
        for c in self.chunks:
            if c.source not in seen:
                seen.append(c.source)
        return seen


def _collapse_near_duplicates(candidates: list[RetrievedChunk],
                              *, threshold: float = 0.9) -> list[RetrievedChunk]:
    """Descarta candidatos casi idénticos a otro ya conservado de la MISMA fuente
    (típico del solape entre chunks vecinos). `candidates` debe venir ordenado
    por relevancia (mejor primero) para que se conserve siempre la mejor copia.
    Comparación acotada a la misma fuente para evitar falsos positivos entre
    documentos distintos."""
    kept: list[RetrievedChunk] = []
    for c in candidates:
        if any(k.source == c.source
               and SequenceMatcher(None, k.text, c.text).quick_ratio() > threshold
               for k in kept):
            continue
        kept.append(c)
    return kept


def _safe_json_list(text: str) -> list:
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        return []
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return []


def _reciprocal_rank_fusion(
    ranked_lists: list[list[RetrievedChunk]],
) -> list[RetrievedChunk]:
    """Fusiona los resultados KNN de varias sub-consultas por RRF.

    score(chunk) = Σ 1/(k + rank) en cada lista donde aparece — un chunk que
    una sola sub-consulta encontró en 1er lugar puntúa alto aunque las demás
    ni lo hayan recuperado, sin necesitar comparar distancias de embeddings de
    consultas distintas (no son comparables entre sí: la distancia depende de
    la consulta, no solo del documento)."""
    scores: dict[str, float] = {}
    chunk_by_id: dict[str, RetrievedChunk] = {}
    for ranked in ranked_lists:
        for rank, chunk in enumerate(ranked, start=1):
            scores[chunk.doc_id] = scores.get(chunk.doc_id, 0.0) + 1.0 / (_RRF_K + rank)
            chunk_by_id.setdefault(chunk.doc_id, chunk)
    ordered_ids = sorted(scores, key=lambda doc_id: scores[doc_id], reverse=True)
    return [chunk_by_id[doc_id] for doc_id in ordered_ids]


def _rank_via_api(query: str, candidates: list[RetrievedChunk],
                  top_n: int) -> list[RetrievedChunk] | None:
    """Reranking con un cross-encoder real (Vertex AI Ranking API).

    None si la API falla o no está habilitada (fail-open: el llamador cae al
    reranking por prompt existente). No lanza nunca."""
    if not settings.rag_ranking_api_enabled:
        return None
    try:
        import google.auth
        from google.auth.transport import requests as google_requests

        credentials, _ = google.auth.default()
        credentials.refresh(google_requests.Request())
        records = [{"id": str(i), "content": c.text[:2000]}
                  for i, c in enumerate(candidates)]
        resp = httpx.post(
            _RANKING_API_URL.format(project=settings.gcp_project_id),
            headers={"Authorization": f"Bearer {credentials.token}",
                    "Content-Type": "application/json"},
            json={
                "model": _RANKING_MODEL, "query": query, "records": records,
                "topN": top_n, "ignoreRecordDetailsInResponse": True,
            },
            timeout=_RANKING_TIMEOUT,
        )
        resp.raise_for_status()
        ranked_ids = [r["id"] for r in resp.json().get("records", [])
                     if str(r.get("id", "")).isdigit()]
        ranked = [candidates[int(i)] for i in ranked_ids if int(i) < len(candidates)]
        return ranked or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("vertex_rerank_failed", error=str(exc))
        return None


class AdvancedRetriever:
    def __init__(self, store: FirestoreVectorStore | None = None) -> None:
        self._store = store or FirestoreVectorStore()
        self._embeddings = get_embeddings()

    def _expand_query(self, query: str, n: int = 2) -> list[str]:
        try:
            resp = invoke_with_failover(
                _MULTIQUERY_PROMPT.format(n=n, query=query), temperature=0.3)
            variants = [str(v) for v in _safe_json_list(resp.content) if str(v).strip()]
            return [query, *variants[:n]]
        except Exception as exc:  # noqa: BLE001
            logger.warning("multiquery_failed", error=str(exc))
            return [query]

    def _rerank_by_prompt(self, query: str, candidates: list[RetrievedChunk],
                          top_n: int) -> list[RetrievedChunk]:
        """Reranking por prompt a Gemini (mecanismo original). Fallback cuando
        la Vertex AI Ranking API no está disponible."""
        listing = "\n\n".join(
            f"[{i}] {c.text}" for i, c in enumerate(candidates)
        )
        try:
            resp = invoke_with_failover(
                _RERANK_PROMPT.format(query=query, n=top_n, candidates=listing),
                temperature=0.0,
            )
            order = [int(x) for x in _safe_json_list(resp.content)
                     if isinstance(x, (int, float))]
            ranked = [candidates[i] for i in order if 0 <= i < len(candidates)]
            # completar por si el LLM omitió índices
            for i, c in enumerate(candidates):
                if c not in ranked:
                    ranked.append(c)
            return ranked[:top_n]
        except Exception as exc:  # noqa: BLE001
            logger.warning("rerank_failed", error=str(exc))
            return candidates[:top_n]

    def _rerank(self, query: str, candidates: list[RetrievedChunk],
                top_n: int) -> list[RetrievedChunk]:
        if len(candidates) <= top_n:
            return candidates
        ranked = _rank_via_api(query, candidates, top_n)
        if ranked is not None:
            return ranked[:top_n]
        return self._rerank_by_prompt(query, candidates, top_n)

    def retrieve(self, query: str, *, top_k: int | None = None,
                 rerank_top_n: int | None = None,
                 use_multiquery: bool = True) -> RetrievalResult:
        k = top_k or settings.rag_top_k
        top_n = rerank_top_n or settings.rag_rerank_top_n

        queries = (self._expand_query(query, n=settings.rag_multiquery_n)
                   if use_multiquery else [query])

        ranked_lists = []
        for q in queries:
            vector = self._embeddings.embed_query(q)
            ranked_lists.append(self._store.search(vector, top_k=k))

        # Hybrid Search: se suma la lista BM25 (léxica, sobre la consulta
        # ORIGINAL sin reformular — las reformulaciones ayudan a la búsqueda
        # semántica, no a la coincidencia de términos exactos) como una lista
        # más para la fusión RRF. best-effort: [] si el índice aún no
        # terminó de construirse (arranque en frío) o está deshabilitado, sin
        # bloquear ni fallar la recuperación.
        from app.agent import bm25_index

        bm25_hits = bm25_index.search(query, top_k=k)
        if bm25_hits:
            ranked_lists.append(bm25_hits)

        candidate_list = _reciprocal_rank_fusion(ranked_lists)
        candidate_list = _collapse_near_duplicates(candidate_list)
        logger.info("retrieval", query=query, candidates=len(candidate_list))

        reranked = self._rerank(query, candidate_list, top_n)
        return RetrievalResult(chunks=reranked)
