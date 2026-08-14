"""Tests de la iniciativa proactiva del avatar — sin GCP ni red (fakes)."""
import app.concerns as cc
import app.kb_events as kbe
import app.proactive as pro
import app.sst_alert as sst
from app.config import settings
from app.sst_alert import SSTReading


def _reset_caches():
    pro._sst_cache["ts"] = 0.0
    pro._sst_cache["event"] = None
    pro._followup_cache.clear()


def _reading(anomaly=2.1, level=2, label="moderado", source=""):
    return SSTReading(anomaly=anomaly, level=level, level_key=label, label=label,
                      date="2026-07-18", source=source)


def _fake_current_alert(reading, store=None):
    """`current_alert` sin Firestore: mismo evento que difundiría WhatsApp."""
    if not sst.is_significant(reading):
        return None
    return {"event_id": f"sst-{reading.level}-{reading.date}", "level": reading.level,
            "level_key": reading.level_key, "label": reading.label,
            "anomaly": reading.anomaly, "date": reading.date,
            "source": reading.source, "broadcast_at": None}


def _patch_sst(monkeypatch, reading_factory):
    """El avatar lee el evento compartido; aquí se sirve sin tocar la nube."""
    monkeypatch.setattr(sst, "compute_reading", reading_factory)
    monkeypatch.setattr(sst, "current_alert", _fake_current_alert)


class _Ev:
    source = "informe.pdf"
    title = "Informe ENFEN"
    chunks = 12


class _KbStore:
    def latest_pending(self):
        return _Ev()


class _KbEmpty:
    def latest_pending(self):
        return None


# ------------------------------- alerta SST ----------------------------------
def test_sst_nudge_when_anomaly_significant(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    _patch_sst(monkeypatch, _reading)

    n = pro._sst_nudge()

    assert n is not None and n.kind == "sst"
    # La clave es el id del evento compartido con WhatsApp, no la fecha del dato.
    assert n.key == "sst-2-2026-07-18"
    assert "+2.1" in n.text and "moderado" in n.text
    assert "moderado" in n.speak and "⚠️" not in n.speak  # la voz va sin emoji


def test_sst_nudge_key_is_the_shared_event_id(monkeypatch):
    """Avatar y WhatsApp alertan del MISMO evento: misma identidad, mismas cifras.

    Y como el id no lleva la fecha del dato diario, el navegador (que deduplica
    por clave en localStorage) no repite el aviso cada vez que el satélite
    publica un día nuevo con el mismo nivel.
    """
    _reset_caches()
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    _patch_sst(monkeypatch, _reading)

    nudge = pro._sst_nudge()
    evento = _fake_current_alert(_reading())

    assert nudge.key == evento["event_id"]
    assert f"{evento['anomaly']:.1f}" in nudge.text
    assert evento["label"] in nudge.text


def test_sst_nudge_attributes_the_real_source(monkeypatch):
    """El aviso decía "dato NOAA" fijo: con el respaldo activo le atribuía a la
    NOAA el ICEN, que publica el IGP."""
    _reset_caches()
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    _patch_sst(monkeypatch,
               lambda: _reading(source="IGP — Índice Costero El Niño (ICEN)"))

    n = pro._sst_nudge()

    assert "ICEN oficial del IGP" in n.text
    assert "NOAA" not in n.text


def test_sst_nudge_attributes_satellite_when_live(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    _patch_sst(monkeypatch, lambda: _reading(
        source="NASA GIBS / GHRSST MUR L4 — anomalía de SST en la región Niño 1+2"))

    assert "satélite GHRSST MUR" in pro._sst_nudge().text


def test_sst_nudge_without_source_does_not_invent_one(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    _patch_sst(monkeypatch, _reading)  # source=""

    text = pro._sst_nudge().text
    assert "monitoreo satelital" in text and "NOAA" not in text and "IGP" not in text


def test_sst_nudge_none_when_sea_is_calm(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "sst_anomaly_alert_c", 1.0)
    _patch_sst(monkeypatch,
               lambda: _reading(anomaly=0.25, level=0, label="normal"))
    assert pro._sst_nudge() is None


def test_sst_reading_is_cached_across_polls(monkeypatch):
    """El avatar sondea cada 20s por visitante: la lectura real debe cachearse."""
    _reset_caches()
    calls = []
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "proactive_sst_ttl_seconds", 900)
    _patch_sst(monkeypatch,
               lambda: calls.append(1) or _reading())

    for _ in range(3):
        pro._sst_nudge()

    assert len(calls) == 1  # 3 sondeos -> 1 sola lectura del servicio satelital


def test_sst_nudge_is_fail_open(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(settings, "sst_alert_enabled", True)

    def boom():
        raise RuntimeError("servicio satelital caido")

    _patch_sst(monkeypatch, boom)
    assert pro._sst_nudge() is None


# --------------------------- novedad de la base ------------------------------
def test_kb_nudge_announces_new_document(monkeypatch):
    monkeypatch.setattr(kbe, "KBEventStore", lambda: _KbStore())
    n = pro._kb_nudge()
    assert n is not None and n.kind == "kb"
    assert n.key == "kb:informe.pdf" and n.source == "informe.pdf"
    assert "Informe ENFEN" in n.text and "Informe ENFEN" in n.speak


def test_kb_nudge_none_when_nothing_pending(monkeypatch):
    monkeypatch.setattr(kbe, "KBEventStore", lambda: _KbEmpty())
    assert pro._kb_nudge() is None


# --------------------------- seguimiento personal ----------------------------
class _Concerns:
    def list_recent_open_for_user(self, uid, *, days, limit):
        return [{"tipo": "preocupacion", "resumen": "teme perder la cosecha"}]


def test_followup_requires_identified_user(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(settings, "concern_followup_enabled", True)
    monkeypatch.setattr(cc, "ConcernStore", lambda: _Concerns())
    # Sesión anónima del avatar -> sin seguimiento personal.
    assert pro._followup_nudge("web:0f8c-anon") is None


def test_followup_for_identified_user(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(settings, "concern_followup_enabled", True)
    monkeypatch.setattr(cc, "ConcernStore", lambda: _Concerns())

    n = pro._followup_nudge("AGBXMBMQ")

    assert n is not None and n.kind == "followup"
    assert "teme perder la cosecha" in n.text


def test_followup_is_cached_per_session(monkeypatch):
    _reset_caches()
    calls = []
    monkeypatch.setattr(settings, "concern_followup_enabled", True)
    monkeypatch.setattr(settings, "proactive_followup_ttl_seconds", 600)

    class _Counting(_Concerns):
        def list_recent_open_for_user(self, uid, *, days, limit):
            calls.append(uid)
            return super().list_recent_open_for_user(uid, days=days, limit=limit)

    monkeypatch.setattr(cc, "ConcernStore", lambda: _Counting())
    for _ in range(2):
        pro._followup_nudge("AGBXMBMQ")
    assert len(calls) == 1  # segunda vez sale de la caché


# ------------------------------- prioridad -----------------------------------
def test_next_nudge_prioritizes_sst_over_kb(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(settings, "proactive_web_enabled", True)
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    _patch_sst(monkeypatch, _reading)
    monkeypatch.setattr(kbe, "KBEventStore", lambda: _KbStore())

    n = pro.next_nudge("AGBXMBMQ")

    assert n is not None and n.kind == "sst"  # la alerta manda sobre la novedad


def test_next_nudge_falls_back_to_kb(monkeypatch):
    _reset_caches()
    monkeypatch.setattr(settings, "proactive_web_enabled", True)
    monkeypatch.setattr(settings, "sst_alert_enabled", False)
    monkeypatch.setattr(kbe, "KBEventStore", lambda: _KbStore())

    n = pro.next_nudge("web:anon")

    assert n is not None and n.kind == "kb"


def test_pending_nudges_returns_all_so_none_starves(monkeypatch):
    """Si solo se devolviera el de mayor prioridad, una alerta ya anunciada lo
    ocuparía siempre y el seguimiento personal nunca llegaría a darse."""
    _reset_caches()
    monkeypatch.setattr(settings, "proactive_web_enabled", True)
    monkeypatch.setattr(settings, "sst_alert_enabled", True)
    monkeypatch.setattr(settings, "concern_followup_enabled", True)
    _patch_sst(monkeypatch, _reading)
    monkeypatch.setattr(kbe, "KBEventStore", lambda: _KbStore())
    monkeypatch.setattr(cc, "ConcernStore", lambda: _Concerns())

    kinds = [n.kind for n in pro.pending_nudges("AGBXMBMQ")]

    assert kinds == ["sst", "kb", "followup"]  # los tres, por prioridad


def test_pending_nudges_disabled_returns_empty(monkeypatch):
    monkeypatch.setattr(settings, "proactive_web_enabled", False)
    assert pro.pending_nudges("AGBXMBMQ") == []


def test_next_nudge_disabled_returns_none(monkeypatch):
    monkeypatch.setattr(settings, "proactive_web_enabled", False)
    assert pro.next_nudge("AGBXMBMQ") is None


def test_nudge_as_dict_marks_pending(monkeypatch):
    monkeypatch.setattr(kbe, "KBEventStore", lambda: _KbStore())
    d = pro._kb_nudge().as_dict()
    assert d["pending"] is True and d["kind"] == "kb"
    assert d["source"] == "informe.pdf" and d["key"] == "kb:informe.pdf"
