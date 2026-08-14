"""Tests de captura de inquietudes y objetivos (#3/#B) — sin GCP ni LLM."""
from datetime import datetime, timedelta, timezone

import app.concerns as concerns
from app.concerns import (Classification, ConcernStore, _parse_classification,
                          lima_day_str, record_concern)


class _FakeStore:
    def __init__(self):
        self.added = []

    def add(self, concern):
        self.added.append(concern)


class _FakeGoalStore:
    def __init__(self):
        self.upserts = []

    def upsert(self, user_id, objetivo):
        self.upserts.append((user_id, objetivo))


# --------------------------- parsing del clasificador ---------------------------
def test_parse_classification_concern_only():
    out = _parse_classification(
        '{"tipo":"reclamo","resumen":"no llego el pedido","objetivo":""}')
    assert out == Classification(tipo="reclamo", resumen="no llego el pedido",
                                 objetivo="")


def test_parse_classification_backward_compatible_without_objetivo():
    out = _parse_classification('{"tipo":"pedido","resumen":"quiere tarifa"}')
    assert out is not None and out.tipo == "pedido" and out.objetivo == ""


def test_parse_classification_fenced():
    raw = '```json\n{"tipo":"pedido","resumen":"quiere tarifa","objetivo":""}\n```'
    out = _parse_classification(raw)
    assert out is not None and out.tipo == "pedido"


def test_parse_classification_objetivo_only():
    out = _parse_classification(
        '{"tipo":"ninguno","resumen":"","objetivo":"exportar a China"}')
    assert out is not None and out.tipo is None and out.objetivo == "exportar a China"


def test_parse_classification_concern_and_objetivo():
    out = _parse_classification(
        '{"tipo":"pedido","resumen":"tarifa","objetivo":"exportar a China"}')
    assert out is not None and out.tipo == "pedido"
    assert out.objetivo == "exportar a China"


def test_parse_classification_preocupacion():
    out = _parse_classification(
        '{"tipo":"preocupacion","resumen":"teme perder su cosecha por el FEN",'
        '"objetivo":""}')
    assert out is not None and out.tipo == "preocupacion"
    assert "cosecha" in out.resumen


def test_parse_classification_nothing_returns_none():
    assert _parse_classification('{"tipo":"ninguno","resumen":"","objetivo":""}') is None


def test_parse_classification_garbage_returns_none():
    assert _parse_classification("esto no es json") is None


def test_lima_day_is_iso_date():
    day = lima_day_str()
    assert len(day) == 10 and day[4] == "-" and day[7] == "-"


# ------------------------------- record_concern --------------------------------
def test_record_concern_stores_when_relevant(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(concerns, "classify_message",
                        lambda m: Classification("reclamo",
                                                 "la app no carga datos satelitales"))
    c = record_concern("AGBXMBMQ",
                       "La aplicacion no carga los datos satelitales de la NASA",
                       store=store)
    assert c is not None and c.tipo == "reclamo"
    assert len(store.added) == 1 and store.added[0].user_id == "AGBXMBMQ"


def test_record_concern_records_goal_for_registered_user(monkeypatch):
    store, goal_store = _FakeStore(), _FakeGoalStore()
    monkeypatch.setattr(concerns, "classify_message",
                        lambda m: Classification("pedido", "tarifa a China",
                                                 "exportar arandano a China"))
    c = record_concern("AGBXMBMQ", "Quiero exportar arandano a China, deme la tarifa",
                       store=store, goal_store=goal_store)
    assert c is not None and c.tipo == "pedido"
    assert goal_store.upserts and goal_store.upserts[0][0] == "AGBXMBMQ"
    assert "China" in goal_store.upserts[0][1]


def test_record_concern_goal_only_no_concern(monkeypatch):
    store, goal_store = _FakeStore(), _FakeGoalStore()
    monkeypatch.setattr(concerns, "classify_message",
                        lambda m: Classification(None, "", "certificarme en GlobalGAP"))
    c = record_concern("AGBXMBMQ", "Mi meta es certificarme en GlobalGAP este anio",
                       store=store, goal_store=goal_store)
    assert c is None and store.added == []          # no hubo inquietud
    assert goal_store.upserts[0][1] == "certificarme en GlobalGAP"


def test_record_concern_goal_skipped_for_unregistered(monkeypatch):
    store, goal_store = _FakeStore(), _FakeGoalStore()
    monkeypatch.setattr(concerns, "classify_message",
                        lambda m: Classification(None, "", "exportar a China"))
    c = record_concern("web:anon123456", "Quiero exportar a China algun dia pronto",
                       store=store, goal_store=goal_store)
    assert c is None and goal_store.upserts == []   # no es código interno estable


def test_record_concern_skips_when_nothing(monkeypatch):
    store = _FakeStore()
    monkeypatch.setattr(concerns, "classify_message", lambda m: None)
    assert record_concern("AG111111", "muchas gracias por la ayuda",
                          store=store) is None
    assert store.added == []


def test_record_concern_skips_short_without_classifying(monkeypatch):
    store = _FakeStore()
    called = []
    monkeypatch.setattr(concerns, "classify_message",
                        lambda m: called.append(m) or Classification("reclamo", "x"))
    assert record_concern("AG111111", "ok", store=store) is None
    assert store.added == [] and called == []  # ni siquiera clasifica


def test_record_concern_is_fail_open(monkeypatch):
    store = _FakeStore()

    def boom(_m):
        raise RuntimeError("LLM caido")

    monkeypatch.setattr(concerns, "classify_message", boom)
    assert record_concern("AG111111", "un mensaje suficientemente largo",
                          store=store) is None


# ------------------ seguimiento in-session: list_recent_open --------------------
class _FakeDoc:
    def __init__(self, data):
        self._d = data

    def to_dict(self):
        return self._d


class _FakeQuery:
    def __init__(self, docs):
        self._docs = docs

    def stream(self):
        return iter(self._docs)


class _FakeColl:
    def __init__(self, docs):
        self._docs = docs

    def where(self, filter=None):  # noqa: A002 (firma de Firestore)
        return _FakeQuery(self._docs)


class _FakeClient:
    def __init__(self, docs):
        self._docs = docs

    def collection(self, name):
        return _FakeColl(self._docs)


def _doc(tipo, resumen, days_ago, cerrado=False):
    ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
    data = {"user_id": "AGBXMBMQ", "tipo": tipo, "resumen": resumen,
            "created_at": ts}
    if cerrado:
        data["seguimiento_cerrado"] = True
    return _FakeDoc(data)


def test_list_recent_open_filters_type_and_recency():
    docs = [
        _doc("reclamo", "reciente", 1),
        _doc("pedido", "reciente 2", 3),
        _doc("sugerencia", "no cuenta", 1),   # tipo excluido
        _doc("reclamo", "viejo", 30),         # fuera de la ventana
    ]
    store = ConcernStore(client=_FakeClient(docs))
    out = store.list_recent_open_for_user("AGBXMBMQ", days=14, limit=5)
    assert [r["resumen"] for r in out] == ["reciente", "reciente 2"]  # desc por fecha


def test_list_recent_open_skips_closed_followups():
    """Cerrar apaga el seguimiento proactivo del avatar, no borra la inquietud."""
    docs = [
        _doc("reclamo", "cerrada", 1, cerrado=True),
        _doc("pedido", "abierta", 2),
    ]
    store = ConcernStore(client=_FakeClient(docs))
    out = store.list_recent_open_for_user("AGBXMBMQ", days=14, limit=5)
    assert [r["resumen"] for r in out] == ["abierta"]


def test_closed_concerns_still_visible_for_report_and_admin():
    """El dato se conserva: el informe diario y las atenciones las siguen viendo."""
    docs = [_doc("reclamo", "cerrada", 1, cerrado=True)]
    store = ConcernStore(client=_FakeClient(docs))
    assert len(store.list_for_day("2026-08-14")) == 1


def test_list_recent_open_respects_limit():
    docs = [_doc("reclamo", f"r{i}", i) for i in range(5)]
    store = ConcernStore(client=_FakeClient(docs))
    out = store.list_recent_open_for_user("AGBXMBMQ", days=30, limit=2)
    assert len(out) == 2
