"""Consola de operador en vivo (handoff humano) para WhatsApp — un solo usuario.

Espeja los mensajes (entrante/saliente) en Firestore para que una interfaz web
los muestre casi en tiempo real, permite responder desde la web y pausar el bot
(handoff, para no duplicar respuestas). El número de destino se **captura del
webhook entrante** (no se escribe a mano); el envío saliente solo va a ese número.

Diseño defensivo:
  - Se activa SOLO si existe la variable de entorno `LIVE_CONSOLE_TOKEN`. Sin ella
    todo es no-op → cero cambio de comportamiento del bot.
  - Todas las operaciones de espejo son fail-open (envueltas por el llamador): un
    fallo en Firestore nunca interrumpe la conversación de WhatsApp.

Colecciones Firestore:
  - `live_messages`  : un documento por mensaje del hilo (dir, text, kind, ts_ms).
  - `live_state/config` : { linked_number, paused, updated_at }.
"""
from __future__ import annotations

import os
import time
from typing import Optional

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

_MSGS = "live_messages"
_STATE = "live_state"
_STATE_DOC = "config"


def live_token() -> str:
    return os.environ.get("LIVE_CONSOLE_TOKEN", "")


class LiveStore:
    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        self._client = client or firestore.Client(project=settings.gcp_project_id)

    @property
    def enabled(self) -> bool:
        return bool(live_token())

    def _state_ref(self):
        return self._client.collection(_STATE).document(_STATE_DOC)

    def _msgs(self):
        return self._client.collection(_MSGS)

    # --- estado / vínculo de número ---
    def capture_number(self, from_number: str) -> None:
        if not from_number:
            return
        self._state_ref().set(
            {"linked_number": from_number, "updated_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )

    def linked_number(self) -> Optional[str]:
        snap = self._state_ref().get()
        return (snap.to_dict() or {}).get("linked_number") if snap.exists else None

    def is_paused(self) -> bool:
        snap = self._state_ref().get()
        return bool((snap.to_dict() or {}).get("paused")) if snap.exists else False

    def set_paused(self, paused: bool) -> None:
        self._state_ref().set(
            {"paused": bool(paused), "updated_at": firestore.SERVER_TIMESTAMP},
            merge=True,
        )

    # --- espejo de mensajes ---
    def _add(self, direction: str, text: str, kind: str, media_url: Optional[str]) -> None:
        self._msgs().add(
            {
                "dir": direction,            # 'in' (WhatsApp→web) | 'out' (web/bot→WhatsApp)
                "text": text or "",
                "kind": kind,                # 'text' | 'voice' | 'bot' | 'human'
                "media_url": media_url,
                "ts": firestore.SERVER_TIMESTAMP,
                "ts_ms": int(time.time() * 1000),
            }
        )

    def mirror_in(self, text: str, kind: str = "text", media_url: Optional[str] = None) -> None:
        self._add("in", text, kind, media_url)

    def mirror_out(self, text: str, kind: str = "bot", media_url: Optional[str] = None) -> None:
        self._add("out", text, kind, media_url)

    def list_messages(self, since_ms: int = 0, limit: int = 200) -> list[dict]:
        query = (
            self._msgs()
            .where(filter=FieldFilter("ts_ms", ">", int(since_ms)))
            .order_by("ts_ms")
            .limit(limit)
        )
        out: list[dict] = []
        for doc in query.stream():
            d = doc.to_dict() or {}
            out.append(
                {
                    "id": doc.id,
                    "dir": d.get("dir"),
                    "text": d.get("text"),
                    "kind": d.get("kind"),
                    "media_url": d.get("media_url"),
                    "ts_ms": d.get("ts_ms"),
                }
            )
        return out


def mask_number(num: Optional[str]) -> Optional[str]:
    """Enmascara el número para mostrarlo (deja los últimos 4 dígitos)."""
    if not num:
        return None
    digits = "".join(ch for ch in num if ch.isdigit())
    if len(digits) <= 4:
        return "••••"
    return "•••" + digits[-4:]


_store: Optional[LiveStore] = None


def get_live_store() -> LiveStore:
    global _store
    if _store is None:
        _store = LiveStore()
    return _store
