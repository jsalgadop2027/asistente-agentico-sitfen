"""Tests de los eventos de novedad de la base de conocimiento (Firestore falso).

El foco: reingestar contenido IDÉNTICO no debe reabrir el aviso. Antes, cada
corrida de la ingesta sobre el corpus completo ponía `announced: False` en todos
los documentos y el avatar repetía "acabo de incorporar un documento nuevo".
"""
import datetime as dt

import pytest
from google.cloud import firestore

from app.kb_events import KBEventStore


# ------------------------- Firestore en memoria (fake) ------------------------
def _resolve(payload: dict) -> dict:
    out = {}
    for k, v in payload.items():
        out[k] = dt.datetime.now(dt.timezone.utc) if v is firestore.SERVER_TIMESTAMP else v
    return out


class _Snap:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data else {}


class _Doc:
    def __init__(self, coll, doc_id):
        self._coll, self.id = coll, doc_id

    def get(self):
        return _Snap(self.id, self._coll.store.get(self.id))

    def set(self, payload, merge=False):
        payload = _resolve(payload)
        if merge and self.id in self._coll.store:
            self._coll.store[self.id].update(payload)
        else:
            self._coll.store[self.id] = dict(payload)


class _Collection:
    def __init__(self):
        self.store = {}

    def document(self, doc_id):
        return _Doc(self, doc_id)

    def stream(self):
        return [_Snap(k, v) for k, v in self.store.items()]


class _FakeClient:
    def __init__(self):
        self._colls = {}

    def collection(self, name):
        return self._colls.setdefault(name, _Collection())


@pytest.fixture
def store():
    return KBEventStore(client=_FakeClient())


HASH_A = "a" * 64
HASH_B = "b" * 64


# ----------------------- reingesta del MISMO contenido ------------------------
def test_reingesting_identical_content_does_not_reopen_the_notice(store):
    """La corrida repetida de la ingesta no vuelve a anunciar lo ya anunciado."""
    store.record_ingestion("informe.pdf", "Informe ENFEN", 12, content_hash=HASH_A)
    store.mark_announced("informe.pdf")
    assert store.latest_pending() is None

    store.record_ingestion("informe.pdf", "Informe ENFEN", 12, content_hash=HASH_A)

    assert store.latest_pending() is None  # sigue anunciado: no es novedad


def test_reingesting_identical_content_keeps_updated_at(store):
    """`updated_at` intacto: `claim_broadcast` no rehabilita el envío por WhatsApp."""
    store.record_ingestion("informe.pdf", "Informe ENFEN", 12, content_hash=HASH_A)
    doc_id = KBEventStore.doc_id_for("informe.pdf")
    coll = store.collection
    before = coll.document(doc_id).get().to_dict()["updated_at"]

    store.record_ingestion("informe.pdf", "Informe ENFEN", 12, content_hash=HASH_A)

    assert coll.document(doc_id).get().to_dict()["updated_at"] == before


# ------------------------- contenido nuevo o cambiado -------------------------
def test_changed_content_reopens_the_notice(store):
    """Si el documento cambió de verdad, sí vuelve a ser novedad."""
    store.record_ingestion("informe.pdf", "Informe ENFEN", 12, content_hash=HASH_A)
    store.mark_announced("informe.pdf")

    store.record_ingestion("informe.pdf", "Informe ENFEN v2", 15, content_hash=HASH_B)

    event = store.latest_pending()
    assert event is not None
    assert event.title == "Informe ENFEN v2" and event.chunks == 15


def test_new_source_is_always_a_novelty(store):
    store.record_ingestion("nuevo.pdf", "Boletín", 3, content_hash=HASH_A)
    event = store.latest_pending()
    assert event is not None and event.source == "nuevo.pdf"


def test_event_without_stored_hash_reopens_once_then_stabilizes(store):
    """Eventos previos a esta guarda (sin hash): se reabren una vez y ya quedan."""
    store.record_ingestion("viejo.pdf", "Antiguo", 5)  # sin content_hash
    store.mark_announced("viejo.pdf")

    store.record_ingestion("viejo.pdf", "Antiguo", 5, content_hash=HASH_A)
    assert store.latest_pending() is not None  # se reabre (no había hash que comparar)

    store.mark_announced("viejo.pdf")
    store.record_ingestion("viejo.pdf", "Antiguo", 5, content_hash=HASH_A)
    assert store.latest_pending() is None  # a partir de aquí, estable


def test_caller_without_hash_keeps_previous_behaviour(store):
    """Sin hash no se puede decidir: se registra la novedad (como antes)."""
    store.record_ingestion("informe.pdf", "Informe", 12, content_hash=HASH_A)
    store.mark_announced("informe.pdf")

    store.record_ingestion("informe.pdf", "Informe", 12)

    assert store.latest_pending() is not None
