"""Registro liviano de atenciones normales de WhatsApp (no derivadas).

`app.concerns` solo persiste el mensaje del usuario cuando el clasificador Flash
lo etiqueta como un punto de dolor accionable (reclamo/pedido/sugerencia/
recomendación/preocupación) — la mayoría del tráfico real son consultas
informativas comunes ("ninguno" para ese clasificador) que nunca quedaban
registradas en ningún lado consultable, así que el reporte de atenciones del
Admin UI (`admin_ui/_atenciones.py`) las pasaba por alto por completo.

Este módulo registra CADA turno de WhatsApp que el agente respondió (sin
bloqueo de guardrails/rate-limit), sin clasificarlo con un LLM — es solo la
constancia de que hubo una atención, para poder contarla y cruzarla contra
`derivations` (¿ese usuario tuvo una derivación el mismo día?) en el reporte.

Diseño (igual que `app.concerns`):
  - **Fire-and-forget:** `record_attention_async` lanza un hilo daemon; nunca
    añade latencia perceptible ni rompe la respuesta al usuario (fail-open).
  - **Minimización de PII:** se redacta el mensaje antes de persistir.
  - **Sin índices compuestos:** se ordena por `created_at` y se filtra por
    rango en memoria, igual que `ConcernStore`/`DerivationStore`.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.cloud import firestore

from app.agent.guardrails import redact_pii
from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


def lima_day_str(when: Optional[datetime] = None) -> str:
    """Fecha (YYYY-MM-DD) en hora de Lima. Perú no tiene DST → offset fijo UTC-5."""
    now = when or datetime.now(timezone.utc)
    local = now.astimezone(timezone.utc) + timedelta(hours=settings.lima_utc_offset_hours)
    return local.date().isoformat()


@dataclass
class Attention:
    user_id: str
    message: str
    day: str
    medio: str = "texto"  # "texto" | "voz" | "imagen" (ver app.agent.turn_context)


class AttentionStore:
    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        self._client = client or firestore.Client(project=settings.gcp_project_id)
        self._collection = settings.firestore_attentions_collection

    def add(self, attention: Attention) -> None:
        self._client.collection(self._collection).add({
            "user_id": attention.user_id,
            "message": attention.message,
            "day": attention.day,
            "medio": attention.medio,
            "created_at": firestore.SERVER_TIMESTAMP,
        })

    def list_recent(self, limit: int = 5000) -> list[dict]:
        """Atenciones más recientes, para el reporte del Admin UI. Sin filtro de
        fecha en la consulta (evita requerir un índice compuesto): el recorte
        por rango se hace en memoria, igual que `ConcernStore.list_recent`."""
        docs = (self._client.collection(self._collection)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit).stream())
        return [d.to_dict() or {} for d in docs]


def record_attention(user_id: str, message: str, medio: str = "texto",
                     store: Optional[AttentionStore] = None) -> None:
    """Registra la atención (síncrono). Fail-open: nunca lanza."""
    try:
        (store or AttentionStore()).add(Attention(
            user_id=user_id, message=redact_pii(message)[:200], day=lima_day_str(),
            medio=medio,
        ))
    except Exception as exc:  # noqa: BLE001
        logger.warning("attention_capture_failed", error=str(exc))


def record_attention_async(user_id: str, message: str, medio: str = "texto") -> None:
    """Lanza el registro en un hilo daemon (no bloquea la respuesta al usuario)."""
    if not settings.attention_capture_enabled:
        return
    threading.Thread(
        target=record_attention, args=(user_id, message, medio), daemon=True,
    ).start()
