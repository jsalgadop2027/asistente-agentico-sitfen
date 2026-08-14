"""Eventos de la base de conocimiento: novedades de documentos vectorizados.

Cuando la ingesta incorpora y vectoriza un documento nuevo (subida desde la
Admin UI, Job de GCS o scraping de URL), registra aquí un evento. El canal web
(avatar) consulta los eventos pendientes para anunciar por TEXTO y VOZ la novedad
y, si el usuario acepta, presentar su contenido.

Se usa una colección Firestore pequeña con un documento por fuente. Para evitar
índices compuestos, los ordenamientos por fecha se resuelven en memoria (el
volumen de documentos del corpus es bajo).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from google.cloud import firestore

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


@dataclass
class KBEvent:
    source: str
    title: str
    chunks: int
    announced: bool = False


def _ts_key(value) -> float:
    """Clave de orden segura para 'updated_at' (timestamps de Firestore)."""
    try:
        return value.timestamp() if value is not None else 0.0
    except Exception:  # noqa: BLE001
        return 0.0


class KBEventStore:
    """Acceso a la colección de eventos de novedades de la base de conocimiento."""

    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        db = settings.firestore_database
        self._client = client or firestore.Client(
            project=settings.gcp_project_id,
            database=None if db in ("(default)", "", None) else db,
        )
        self._collection_name = settings.firestore_kb_events_collection

    @property
    def collection(self):
        return self._client.collection(self._collection_name)

    @staticmethod
    def _doc_id(source: str) -> str:
        return hashlib.sha1(source.encode("utf-8")).hexdigest()[:24]

    @classmethod
    def doc_id_for(cls, source: str) -> str:
        """Id del documento de evento para una fuente (lo usa el difusor/trigger)."""
        return cls._doc_id(source)

    # -------------------------------------------------- claim (difusión única)
    def claim_broadcast(self, doc_id: str) -> Optional[dict]:
        """Reclama, de forma atómica, el derecho a difundir este evento por WhatsApp.

        Devuelve los datos del evento (source/title/…) si esta llamada «gana» la
        difusión, o None si ya se difundió para esta ingesta. Hace idempotente el
        envío frente a: reintentos del trigger de Eventarc, el eco del propio write
        de `broadcast_at`, `mark_announced` del canal web y el envío manual desde la
        Admin UI. Reingestar (nuevo `updated_at`) vuelve a habilitar un envío.
        """
        ref = self.collection.document(doc_id)

        @firestore.transactional
        def _claim(txn) -> Optional[dict]:
            snap = ref.get(transaction=txn)
            if not snap.exists:
                return None
            data = snap.to_dict() or {}
            if not data.get("source"):
                return None
            updated = data.get("updated_at")
            broadcast_at = data.get("broadcast_at")
            # Ya difundido para esta ingesta (marca posterior o igual a la ingesta).
            if broadcast_at is not None and updated is not None and broadcast_at >= updated:
                return None
            txn.set(ref, {"broadcast_at": firestore.SERVER_TIMESTAMP}, merge=True)
            return data

        try:
            return _claim(self._client.transaction())
        except Exception as exc:  # noqa: BLE001
            logger.warning("kb_claim_broadcast_failed", doc_id=doc_id, error=str(exc))
            return None

    # ------------------------------------------------------------------ write
    def record_ingestion(self, source: str, title: str, chunks: int,
                         content_hash: str = "") -> None:
        """Registra (o reabre) el aviso de un documento recién vectorizado.

        Si la fuente ya estaba registrada con el MISMO `content_hash`, no se
        escribe nada: reingestar contenido idéntico no es una novedad. Sin esta
        guarda, cada corrida de la ingesta sobre el corpus completo volvía a
        poner `announced: False` en TODOS los documentos (el control de
        duplicados de `ingest.py` sólo omite una fuente cuando el mismo
        contenido está indexado bajo OTRA fuente, no al reingestar el mismo
        archivo), y el avatar anunciaba "acabo de incorporar un documento
        nuevo" sesión tras sesión. Al no tocar `updated_at` tampoco se
        rehabilita la difusión por WhatsApp (ver `claim_broadcast`).

        `content_hash` vacío (llamador que no lo conoce) conserva el
        comportamiento anterior: se registra la novedad.
        """
        try:
            if content_hash and self._content_hash_of(source) == content_hash:
                logger.info("kb_event_unchanged", source=source)
                return
            payload = {
                "source": source,
                "title": title or source,
                "chunks": int(chunks),
                "announced": False,
                "updated_at": firestore.SERVER_TIMESTAMP,
            }
            if content_hash:
                payload["content_hash"] = content_hash
            self.collection.document(self._doc_id(source)).set(payload, merge=True)
            logger.info("kb_event_recorded", source=source, chunks=chunks)
        except Exception as exc:  # noqa: BLE001
            logger.warning("kb_event_record_failed", source=source, error=str(exc))

    def _content_hash_of(self, source: str) -> str:
        """Hash de contenido con el que se registró la última ingesta de `source`.

        Cadena vacía si el evento no existe o viene de antes de que se guardara
        el hash (esos documentos se reabren una última vez y ya quedan estables).
        """
        snap = self.collection.document(self._doc_id(source)).get()
        if not snap.exists:
            return ""
        return str((snap.to_dict() or {}).get("content_hash") or "")

    def mark_announced(self, source: str) -> None:
        """Marca el aviso como ya anunciado (no se vuelve a emitir)."""
        try:
            self.collection.document(self._doc_id(source)).set(
                {"announced": True, "announced_at": firestore.SERVER_TIMESTAMP},
                merge=True,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("kb_event_ack_failed", source=source, error=str(exc))

    # ------------------------------------------------------------------- read
    def _all(self) -> list[dict]:
        rows = []
        for snap in self.collection.stream():
            data = snap.to_dict() or {}
            if data.get("source"):
                rows.append(data)
        return rows

    @staticmethod
    def _to_event(data: dict) -> KBEvent:
        return KBEvent(
            source=data.get("source", ""),
            title=data.get("title", "") or data.get("source", ""),
            chunks=int(data.get("chunks", 0)),
            announced=bool(data.get("announced", False)),
        )

    def latest_pending(self) -> Optional[KBEvent]:
        """Documento más reciente aún no anunciado (para el polling del canal web)."""
        try:
            pending = [d for d in self._all() if not d.get("announced", False)]
            if not pending:
                return None
            pending.sort(key=lambda d: _ts_key(d.get("updated_at")), reverse=True)
            return self._to_event(pending[0])
        except Exception as exc:  # noqa: BLE001
            logger.warning("kb_latest_pending_failed", error=str(exc))
            return None

    def latest(self) -> Optional[KBEvent]:
        """Documento incorporado más recientemente (anunciado o no)."""
        try:
            rows = self._all()
            if not rows:
                return None
            rows.sort(key=lambda d: _ts_key(d.get("updated_at")), reverse=True)
            return self._to_event(rows[0])
        except Exception as exc:  # noqa: BLE001
            logger.warning("kb_latest_failed", error=str(exc))
            return None

    def find(self, query: str) -> Optional[KBEvent]:
        """Busca un evento por coincidencia (case-insensitive) en source o título."""
        if not query:
            return None
        q = query.strip().lower()
        try:
            for d in self._all():
                src = (d.get("source", "") or "").lower()
                title = (d.get("title", "") or "").lower()
                if q in src or q in title or src in q or title in q:
                    return self._to_event(d)
        except Exception as exc:  # noqa: BLE001
            logger.warning("kb_find_failed", error=str(exc))
        return None
