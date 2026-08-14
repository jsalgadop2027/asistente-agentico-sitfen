"""Vector store sobre Firestore nativo (FindNearest / búsqueda vectorial).

Firestore soporta búsqueda KNN nativa con `find_nearest` sobre campos de tipo
Vector, lo que permite un RAG 100% serverless y de costo casi nulo para el MVP.
Este módulo es la única puerta de acceso a la colección de chunks: lo usan tanto
la ingesta (upsert) como el agente (search).

Documento de chunk:
    {
      "doc_id":     str,   # identificador estable del chunk
      "source":     str,   # nombre del PDF de origen
      "title":      str,
      "chunk_index": int,
      "text":       str,   # contenido del chunk
      "tokens":     int,
      "embedding":  Vector(768),
      "updated_at": timestamp,
    }
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Iterable, Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

from app.config import settings

_DISTANCE_MAP = {
    "COSINE": DistanceMeasure.COSINE,
    "EUCLIDEAN": DistanceMeasure.EUCLIDEAN,
    "DOT_PRODUCT": DistanceMeasure.DOT_PRODUCT,
}


@dataclass
class RetrievedChunk:
    doc_id: str
    source: str
    title: str
    text: str
    chunk_index: int
    distance: Optional[float] = None

    @property
    def citation(self) -> str:
        return f"{self.source} (fragmento {self.chunk_index})"


def make_doc_id(source: str, chunk_index: int, text: str) -> str:
    digest = hashlib.sha1(f"{source}:{chunk_index}:{text}".encode("utf-8")).hexdigest()
    return digest[:24]


class FirestoreVectorStore:
    """Acceso a la colección de chunks vectorizados en Firestore."""

    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        db = settings.firestore_database
        self._client = client or firestore.Client(
            project=settings.gcp_project_id,
            database=None if db in ("(default)", "", None) else db,
        )
        self._collection_name = settings.firestore_vector_collection

    @property
    def collection(self):
        return self._client.collection(self._collection_name)

    # ----------------------------- Ingesta ---------------------------------
    def upsert_chunks(self, chunks: Iterable[dict[str, Any]], *, batch_size: int = 200) -> int:
        """Inserta/actualiza chunks. Cada dict debe traer 'embedding' (list[float])."""
        count = 0
        batch = self._client.batch()
        pending = 0
        for chunk in chunks:
            doc_id = chunk.get("doc_id") or make_doc_id(
                chunk["source"], chunk["chunk_index"], chunk["text"]
            )
            payload = dict(chunk)
            payload["doc_id"] = doc_id
            payload["embedding"] = Vector(payload["embedding"])
            payload["updated_at"] = firestore.SERVER_TIMESTAMP
            batch.set(self.collection.document(doc_id), payload)
            pending += 1
            count += 1
            if pending >= batch_size:
                batch.commit()
                batch = self._client.batch()
                pending = 0
        if pending:
            batch.commit()
        return count

    def delete_by_source(self, source: str) -> int:
        """Elimina todos los chunks de un PDF (para re-ingesta o derecho de borrado)."""
        deleted = 0
        query = self.collection.where(filter=FieldFilter("source", "==", source))
        for doc in query.stream():
            doc.reference.delete()
            deleted += 1
        return deleted

    def find_source_by_content_hash(self, content_hash: str) -> Optional[str]:
        """Devuelve el `source` ya indexado cuyo contenido tiene este hash, o None.

        Permite detectar documentos duplicados aunque se suban con otro nombre o
        URL: la clave de identidad es el contenido (hash), no el nombre de fuente.
        Sólo encuentra chunks ingestados con este control activo (que llevan el
        campo `content_hash`); los previos a esta función no se comparan.
        """
        query = (
            self.collection.where(filter=FieldFilter("content_hash", "==", content_hash))
            .select(["source"])
            .limit(1)
        )
        for snap in query.stream():
            return (snap.to_dict() or {}).get("source")
        return None

    def count(self) -> int:
        return self.collection.count().get()[0][0].value

    def list_sources(self) -> list[dict[str, Any]]:
        """Lista los documentos del índice ordenados por nombre.

        Cada entrada: {source, title, chunks, content_hash, updated_at}.
        El `content_hash` es común a todos los chunks de una fuente; `updated_at`
        es el más reciente entre ellos (fecha/hora de procesamiento del documento).
        """
        agg: dict[str, dict[str, Any]] = {}
        for snap in self.collection.select(
            ["source", "title", "content_hash", "updated_at"]
        ).stream():
            data = snap.to_dict() or {}
            src = data.get("source", "desconocido")
            entry = agg.setdefault(src, {
                "source": src, "title": data.get("title", ""), "chunks": 0,
                "content_hash": None, "updated_at": None,
            })
            entry["chunks"] += 1
            if not entry["content_hash"] and data.get("content_hash"):
                entry["content_hash"] = data["content_hash"]
            ts = data.get("updated_at")
            if ts is not None and (entry["updated_at"] is None or ts > entry["updated_at"]):
                entry["updated_at"] = ts
        return sorted(agg.values(), key=lambda d: d["source"].lower())

    def get_document_chunks(self, source: str, *, limit: int = 30) -> list[RetrievedChunk]:
        """Devuelve los chunks de un documento ordenados por posición.

        Se usa para PRESENTAR un documento recién incorporado (no es una búsqueda
        semántica, sino una lectura secuencial de su contenido). El orden por
        `chunk_index` se hace en memoria para no exigir un índice compuesto.
        """
        query = self.collection.where(filter=FieldFilter("source", "==", source)).limit(limit)
        chunks: list[RetrievedChunk] = []
        for snap in query.stream():
            data = snap.to_dict() or {}
            chunks.append(
                RetrievedChunk(
                    doc_id=data.get("doc_id", snap.id),
                    source=data.get("source", source),
                    title=data.get("title", ""),
                    text=data.get("text", ""),
                    chunk_index=int(data.get("chunk_index", 0)),
                )
            )
        chunks.sort(key=lambda c: c.chunk_index)
        return chunks

    # --------------------------- Recuperación ------------------------------
    def search(
        self,
        query_embedding: list[float],
        *,
        top_k: Optional[int] = None,
        source_filter: Optional[str] = None,
    ) -> list[RetrievedChunk]:
        """Búsqueda KNN nativa (find_nearest) con filtro opcional por fuente."""
        k = top_k or settings.rag_top_k
        distance = _DISTANCE_MAP.get(settings.vector_distance, DistanceMeasure.COSINE)

        base = self.collection
        if source_filter:
            base = base.where(filter=FieldFilter("source", "==", source_filter))

        vector_query = base.find_nearest(
            vector_field="embedding",
            query_vector=Vector(query_embedding),
            distance_measure=distance,
            limit=k,
            distance_result_field="vector_distance",
        )

        results: list[RetrievedChunk] = []
        for snapshot in vector_query.stream():
            data = snapshot.to_dict() or {}
            results.append(
                RetrievedChunk(
                    doc_id=data.get("doc_id", snapshot.id),
                    source=data.get("source", "desconocido"),
                    title=data.get("title", ""),
                    text=data.get("text", ""),
                    chunk_index=int(data.get("chunk_index", 0)),
                    distance=data.get("vector_distance"),
                )
            )
        return results
