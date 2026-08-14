"""Tests de la alerta SST (#4) — sin GCP ni red (fakes/monkeypatch)."""
import httpx

import app.sst_alert as sst
from app.config import settings
from app.sst_alert import SSTReading, compute_reading, run_sst_alert


def _fen_status(**overrides):
    base = {"available": True, "level": "moderado", "label": "Cálido moderado",
            "value": 2.0, "date": "18 jul", "source": "MUR L4"}
    base.update(overrides)
    return base


def test_compute_reading_maps_fen_status_to_severity(monkeypatch):
    monkeypatch.setattr(settings, "sst_monitor_base_url", "https://sst.example")
    monkeypatch.setattr(sst, "_fetch_fen_status", lambda: _fen_status())
    r = compute_reading()
    assert r.anomaly == 2.0 and r.level == 2 and r.level_key == "moderado"
    assert r.label == "Cálido moderado" and r.date == "18 jul"


def test_compute_reading_cold_and_neutral_map_to_zero_severity(monkeypatch):
    for level_key in ("neutro", "frio_debil", "frio_moderado", "frio_fuerte"):
        monkeypatch.setattr(sst, "_fetch_fen_status",
                            lambda level_key=level_key: _fen_status(level=level_key))
        assert compute_reading().level == 0


def test_compute_reading_none_when_no_data(monkeypatch):
    monkeypatch.setattr(sst, "_fetch_fen_status", lambda: None)
    assert compute_reading() is None


def test_fetch_fen_status_none_when_monitor_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "sst_monitor_base_url", None)
    assert sst._fetch_fen_status() is None


def test_fetch_fen_status_fail_open_on_http_error(monkeypatch):
    monkeypatch.setattr(settings, "sst_monitor_base_url", "https://sst.example")

    class _Boom:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **kw):
            raise httpx.ConnectError("caido")

    monkeypatch.setattr(sst.httpx, "Client", lambda **kw: _Boom())
    assert sst._fetch_fen_status() is None


def test_fetch_fen_status_none_when_unavailable(monkeypatch):
    monkeypatch.setattr(settings, "sst_monitor_base_url", "https://sst.example")

    class _Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"available": False}

    class _Client:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **kw):
            return _Resp()

    monkeypatch.setattr(sst.httpx, "Client", lambda **kw: _Client())
    assert sst._fetch_fen_status() is None


class _FakeStore:
    """Almacén en memoria del evento de alerta vigente (mismo contrato que Firestore)."""

    def __init__(self, event=None):
        self.event = dict(event) if event else None
        self.saves = 0

    def get_event(self):
        return self.event if (self.event and self.event.get("active", True)) else None

    def save_event(self, event):
        self.event = {**event, "active": True}
        self.saves += 1

    def mark_broadcast(self, event_id):
        if self.event and self.event.get("event_id") == event_id:
            self.event["broadcast_at"] = "2026-07-18T09:00:00Z"

    def clear_event(self):
        if self.event:
            self.event["active"] = False


def _reading(anomaly=2.0, level=2, label="moderado", date="2026-07-18"):
    return SSTReading(anomaly=anomaly, level=level, level_key=label, label=label,
                      date=date)


def test_alert_broadcasts_a_new_event(monkeypatch):
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    monkeypatch.setattr(sst, "compute_reading", _reading)
    monkeypatch.setattr(sst, "_broadcast", lambda reading: (3, 0))
    store = _FakeStore()

    res = run_sst_alert(store=store)

    assert res.alerted is True and res.sent == 3
    assert store.event["level"] == 2 and store.event["broadcast_at"]


def test_alert_skips_when_level_unchanged(monkeypatch):
    """Mismo nivel = misma alerta vigente: no se vuelve a difundir."""
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    monkeypatch.setattr(sst, "compute_reading", _reading)

    def _must_not_call(_r):
        raise AssertionError("no debe difundir dos veces el mismo evento")

    monkeypatch.setattr(sst, "_broadcast", _must_not_call)
    store = _FakeStore({"event_id": "sst-2-2026-07-18", "level": 2,
                        "broadcast_at": "2026-07-18T09:00:00Z"})

    res = run_sst_alert(store=store)

    assert res.alerted is False and res.sent == 0
    assert store.saves == 0  # no reescribe: el nivel no cambió


def test_new_day_same_level_is_still_the_same_event(monkeypatch):
    """La fuente es diaria: que cambie la fecha del dato no es una alerta nueva."""
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    store = _FakeStore({"event_id": "sst-2-2026-07-18", "level": 2,
                        "broadcast_at": "2026-07-18T09:00:00Z"})

    event = sst.current_alert(_reading(date="2026-07-19"), store=store)

    assert event["event_id"] == "sst-2-2026-07-18"  # el de siempre
    assert store.saves == 0


def test_level_change_opens_a_new_event(monkeypatch):
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    monkeypatch.setattr(sst, "compute_reading",
                        lambda: _reading(anomaly=4.1, level=4, label="extraordinario"))
    monkeypatch.setattr(sst, "_broadcast", lambda reading: (2, 0))
    store = _FakeStore({"event_id": "sst-2-2026-07-18", "level": 2,
                        "broadcast_at": "2026-07-18T09:00:00Z"})

    res = run_sst_alert(store=store)

    assert res.alerted is True and res.sent == 2
    assert store.event["level"] == 4


def test_alert_skips_below_threshold_and_closes_the_event(monkeypatch):
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    monkeypatch.setattr(sst, "compute_reading",
                        lambda: _reading(anomaly=0.4, level=0, label="normal"))

    def _must_not_call(_r):
        raise AssertionError("no debe difundir bajo el umbral")

    monkeypatch.setattr(sst, "_broadcast", _must_not_call)
    store = _FakeStore({"event_id": "sst-2-2026-07-18", "level": 2,
                        "broadcast_at": "2026-07-18T09:00:00Z"})

    assert run_sst_alert(store=store).alerted is False
    assert store.get_event() is None  # cerrado: si vuelve a subir, se re-alerta


def test_broadcast_quotes_the_event_not_the_live_reading(monkeypatch):
    """WhatsApp y el avatar deben citar las MISMAS cifras: las del evento.

    El evento se abrió con +2.0; aunque hoy el satélite publique +2.9, mientras
    no cambie el nivel sigue siendo la misma alerta y el mensaje dice +2.0.
    """
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    monkeypatch.setattr(sst, "compute_reading", lambda: _reading(anomaly=2.9))
    difundido = {}
    monkeypatch.setattr(sst, "_broadcast",
                        lambda event: (difundido.update(event), (1, 0))[1])
    store = _FakeStore({"event_id": "sst-2-2026-07-18", "level": 2, "anomaly": 2.0,
                        "label": "moderado", "date": "2026-07-18",
                        "broadcast_at": None})

    run_sst_alert(store=store)

    assert difundido["anomaly"] == 2.0
    assert difundido["event_id"] == "sst-2-2026-07-18"


def test_failed_send_does_not_consume_the_event(monkeypatch):
    """Sin plantilla o sin destinatarios se reintenta mañana, no se da por hecho."""
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    monkeypatch.setattr(sst, "compute_reading", _reading)
    monkeypatch.setattr(sst, "_broadcast", lambda reading: (0, 0))
    store = _FakeStore()

    run_sst_alert(store=store)

    assert not store.event.get("broadcast_at")


def test_alert_disabled(monkeypatch):
    monkeypatch.setattr(settings, "sst_alert_enabled", False)
    res = run_sst_alert(store=_FakeStore())
    assert res.checked is False and res.skipped_reason is not None
