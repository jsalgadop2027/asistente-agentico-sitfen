"""Objetivos/metas de negocio del usuario (#B de la Fase 3).

El MISMO clasificador Flash de `app.concerns` detecta, sin una llamada extra, si
el usuario declara o actualiza una meta de negocio (p. ej. "quiero exportar a
China", "busco certificarme en GlobalGAP"). Aquí se persiste esa meta por usuario
y el orquestador la inyecta al prompt para orientar sus respuestas hacia ella.

Diseño:
  - Un documento por usuario (id = código interno estable) en `user_goals`; la
    última meta declarada reemplaza a la anterior (merge). Sin índices compuestos.
  - Minimización de PII: se redacta y trunca el texto antes de persistir.
  - Fail-open: cualquier fallo se registra y no rompe la captura ni la respuesta.
"""
from __future__ import annotations

from typing import Optional

from google.cloud import firestore

from app.agent.guardrails import redact_pii
from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

_MAX_GOAL_CHARS = 300


class GoalStore:
    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        self._client = client or firestore.Client(project=settings.gcp_project_id)
        self._collection = settings.firestore_goals_collection

    def upsert(self, user_id: str, objetivo: str) -> None:
        self._client.collection(self._collection).document(user_id).set({
            "user_id": user_id,
            "objetivo": objetivo,
            "updated_at": firestore.SERVER_TIMESTAMP,
        }, merge=True)

    def get(self, user_id: str) -> Optional[str]:
        snap = self._client.collection(self._collection).document(user_id).get()
        if not snap.exists:
            return None
        objetivo = (snap.to_dict() or {}).get("objetivo")
        return objetivo or None


def record_goal(user_id: str, objetivo: str,
                store: Optional[GoalStore] = None) -> None:
    """Persiste (o actualiza) la meta de negocio del usuario. Fail-open."""
    try:
        text = redact_pii(objetivo or "").strip()[:_MAX_GOAL_CHARS]
        if not text:
            return
        (store or GoalStore()).upsert(user_id, text)
        logger.info("goal_recorded", user_id=redact_pii(user_id))
    except Exception as exc:  # noqa: BLE001
        logger.warning("goal_record_failed", error=str(exc))
