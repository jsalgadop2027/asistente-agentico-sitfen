"""Memoria semántica de largo plazo por usuario (Firestore Vector Search).

Guarda cada intercambio (usuario+asistente) como un vector y recupera, para la
consulta actual, los recuerdos MÁS RELEVANTES de interacciones pasadas del MISMO
usuario — incluso de sesiones antiguas fuera de la ventana de corto plazo.

Documento (colección `conversation_memory`):
    { user_id, text, embedding: Vector(768), created_at }

Requiere un índice vectorial COMPUESTO (user_id + embedding) porque la búsqueda
prefiltra por `user_id` (ver infra/06_conversation_memory_index.ps1).

Diseño fail-open: si falta el índice, no hay GCP o falla la red, `recall` devuelve
[] y `add` no hace nada; NUNCA interrumpe la respuesta del agente.

Privacidad (Ley 29733 / GDPR): `user_id` ya es un identificador de sesión sin PII
(código interno o token pseudonimizado); el texto se redacta antes de persistir.
"""
from __future__ import annotations

import hashlib
import time
from typing import Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from app.agent.guardrails import redact_pii
from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

_DISTANCE_MAP = {
    "COSINE": DistanceMeasure.COSINE,
    "EUCLIDEAN": DistanceMeasure.EUCLIDEAN,
    "DOT_PRODUCT": DistanceMeasure.DOT_PRODUCT,
}


class SemanticMemory:
    """Acceso a la colección vectorial de recuerdos conversacionales."""

    def __init__(self, client: Optional[firestore.Client] = None,
                 embeddings=None) -> None:
        db = settings.firestore_database
        self._client = client or firestore.Client(
            project=settings.gcp_project_id,
            database=None if db in ("(default)", "", None) else db,
        )
        self._collection_name = settings.firestore_conv_memory_collection
        self._embeddings = embeddings  # perezoso si es None

    @property
    def collection(self):
        return self._client.collection(self._collection_name)

    def _ensure_embeddings(self):
        if self._embeddings is None:
            from app.agent.models import get_embeddings

            self._embeddings = get_embeddings()
        return self._embeddings

    def _embed_for_storage(self, text: str) -> list[float]:
        """Embedding de lo que se persiste (RETRIEVAL_DOCUMENT)."""
        return self._ensure_embeddings().embed_documents([text])[0]

    def _embed_for_query(self, text: str) -> list[float]:
        """Embedding de la consulta al recuperar (RETRIEVAL_QUERY)."""
        return self._ensure_embeddings().embed_query(text)

    @staticmethod
    def _compose(user_msg: str, assistant_msg: str) -> str:
        return (f"Usuario: {redact_pii(user_msg)}\n"
                f"Asistente: {assistant_msg}").strip()

    def add(self, user_id: str, user_msg: str, assistant_msg: str) -> bool:
        """Vectoriza y persiste un intercambio. Fail-open (devuelve False si falla)."""
        if not user_id:
            return False
        text = self._compose(user_msg, assistant_msg)
        try:
            vector = self._embed_for_storage(text)
            doc_id = hashlib.sha1(
                f"{user_id}:{time.time()}:{text}".encode("utf-8")
            ).hexdigest()[:24]
            self.collection.document(doc_id).set({
                "user_id": user_id,
                "text": text[:4000],
                "embedding": Vector(vector),
                "created_at": firestore.SERVER_TIMESTAMP,
            })
            return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("semantic_add_failed", error=str(exc))
            return False

    def recall(self, user_id: str, query: str, *, top_k: Optional[int] = None) -> list[str]:
        """Recuerdos más relevantes del MISMO usuario. Fail-open (devuelve [])."""
        if not (user_id and query):
            return []
        k = top_k or settings.ltm_recall_top_k
        distance = _DISTANCE_MAP.get(settings.vector_distance, DistanceMeasure.COSINE)
        try:
            vector = self._embed_for_query(query)
            base = self.collection.where(
                filter=FieldFilter("user_id", "==", user_id)
            )
            vector_query = base.find_nearest(
                vector_field="embedding",
                query_vector=Vector(vector),
                distance_measure=distance,
                limit=k,
                distance_result_field="vector_distance",
            )
            out: list[str] = []
            for snap in vector_query.stream():
                data = snap.to_dict() or {}
                text = data.get("text")
                if text:
                    out.append(text)
            return out
        except Exception as exc:  # noqa: BLE001
            logger.warning("semantic_recall_failed", error=str(exc))
            return []

    def forget(self, user_id: str) -> int:
        """Borra todos los recuerdos de un usuario (derecho de supresión)."""
        deleted = 0
        try:
            query = self.collection.where(filter=FieldFilter("user_id", "==", user_id))
            for snap in query.stream():
                snap.reference.delete()
                deleted += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("semantic_forget_failed", error=str(exc))
        return deleted
