"""Tests del difusor de novedades por WhatsApp (sin GCP: summary por plantilla)."""
import app.kb_events as kbe
import app.channels.twilio_whatsapp as tw
import app.user_registry as ur
from app.kb_broadcast import broadcast_event, broadcast_new_document
from app.user_registry import UserRecord


def _rec(code, nombre, whatsapp):
    return UserRecord(code=code, nombre=nombre, apellido="X", direccion="",
                      rubro="Comercio", whatsapp=whatsapp, email="x@e.pe")


class _FakeRegistry:
    def __init__(self, recipients):
        self._recipients = recipients

    def kb_summary_recipients(self):
        return self._recipients


def _patch(monkeypatch, recipients, sender):
    monkeypatch.setattr(ur, "get_user_registry", lambda: _FakeRegistry(recipients))
    monkeypatch.setattr(tw, "send_whatsapp_message", sender)


def test_broadcast_sends_to_all_recipients(monkeypatch):
    calls = []

    def sender(to, body, audio_url=None):
        calls.append((to, body))
        return True

    recipients = [_rec("AG111111", "Ana", "+51987654321"),
                  _rec("CO222222", "Luis", "+51900000000")]
    _patch(monkeypatch, recipients, sender)

    res = broadcast_new_document("doc.pdf", title="Reporte 2026", generate_summary=False)

    assert res.recipients == 2
    assert res.sent == 2 and res.failed == 0
    assert res.skipped_reason is None
    # Personalización + destino con prefijo whatsapp:
    tos = [c[0] for c in calls]
    assert "whatsapp:+51987654321" in tos
    assert any("Hola Ana" in body and "Reporte 2026" in body for _, body in calls)


def test_broadcast_counts_failures(monkeypatch):
    def sender(to, body, audio_url=None):
        return to != "whatsapp:+51900000000"  # este falla

    recipients = [_rec("AG111111", "Ana", "+51987654321"),
                  _rec("CO222222", "Luis", "+51900000000")]
    _patch(monkeypatch, recipients, sender)

    res = broadcast_new_document("doc.pdf", title="T", generate_summary=False)
    assert res.sent == 1 and res.failed == 1
    assert res.failures == ["CO222222"]


def test_broadcast_no_recipients_skips(monkeypatch):
    def sender(to, body, audio_url=None):  # no debe llamarse
        raise AssertionError("no debería enviar sin destinatarios")

    _patch(monkeypatch, [], sender)
    res = broadcast_new_document("doc.pdf", title="T", generate_summary=False)
    assert res.recipients == 0 and res.sent == 0
    assert res.skipped_reason is not None


def test_broadcast_send_exception_is_contained(monkeypatch):
    def sender(to, body, audio_url=None):
        raise RuntimeError("twilio caído")

    _patch(monkeypatch, [_rec("AG111111", "Ana", "+51987654321")], sender)
    res = broadcast_new_document("doc.pdf", title="T", generate_summary=False)
    assert res.sent == 0 and res.failed == 1
    assert res.failures == ["AG111111"]


class _FakeStore:
    """Simula KBEventStore: 'gana' el claim una sola vez (idempotencia)."""

    def __init__(self, data):
        self._data = data
        self.claims = 0

    def claim_broadcast(self, doc_id):
        self.claims += 1
        return self._data if self.claims == 1 else None


def test_broadcast_event_sends_once_then_skips(monkeypatch):
    """El primer claim difunde; el segundo (reintento/manual) se omite."""
    sent = []

    def sender(to, body, audio_url=None):
        sent.append(to)
        return True

    store = _FakeStore({"source": "doc.pdf", "title": "Reporte"})
    monkeypatch.setattr(kbe, "KBEventStore", lambda: store)
    _patch(monkeypatch, [_rec("AG111111", "Ana", "+51987654321")], sender)

    first = broadcast_event("abc123")
    assert first is not None and first.sent == 1
    assert len(sent) == 1

    # Segunda invocación (p. ej. eco del write o envío manual): no reenvía.
    second = broadcast_event("abc123")
    assert second is None
    assert len(sent) == 1


def test_broadcast_uses_template_when_configured(monkeypatch):
    """Con plantilla configurada, usa la Content API (no texto libre)."""
    from app.config import settings

    calls = []

    def tmpl(to, content_sid, variables):
        calls.append((to, content_sid, variables))
        return True

    def no_freeform(*a, **k):
        raise AssertionError("no debería usar texto libre con plantilla activa")

    monkeypatch.setattr(settings, "whatsapp_kb_template_sid", "HX123")
    monkeypatch.setattr(tw, "send_whatsapp_template", tmpl)
    monkeypatch.setattr(ur, "get_user_registry",
                        lambda: _FakeRegistry([_rec("AG111111", "Ana", "+51987654321")]))
    monkeypatch.setattr(tw, "send_whatsapp_message", no_freeform)

    res = broadcast_new_document("doc.pdf", title="Reporte 2026", generate_summary=False)

    assert res.sent == 1 and res.failed == 0
    to, sid, variables = calls[0]
    assert to == "whatsapp:+51987654321" and sid == "HX123"
    assert variables["1"] == "Ana" and variables["2"] == "Reporte 2026"


def test_broadcast_event_no_event_returns_none(monkeypatch):
    store = _FakeStore(None)
    monkeypatch.setattr(kbe, "KBEventStore", lambda: store)
    _patch(monkeypatch, [_rec("AG111111", "Ana", "+51987654321")],
           lambda to, body, audio_url=None: True)

    assert broadcast_event("missing") is None
