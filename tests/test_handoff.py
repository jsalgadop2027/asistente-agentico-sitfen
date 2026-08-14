"""Tests del escalamiento a humano (#C) — sin GCP ni SendGrid (fakes)."""
import app.channels.email_sender as es
import app.handoff as ho
import app.user_registry as ur
from app.agent.tools.handoff_tools import escalar_a_humano
from app.agent.turn_context import set_current_user_id
from app.config import settings
from app.handoff import HandoffResult, send_handoff
from app.user_registry import UserRecord


class _FakeHandoffStore:
    def __init__(self):
        self.added = []

    def add(self, **kw):
        self.added.append(kw)


def _rec():
    return UserRecord(code="AGBXMBMQ", nombre="Julio", apellido="Salgado",
                      direccion="", rubro="Agroindustrial", whatsapp="+51947323775",
                      email="julio@ejemplo.pe")


def test_send_handoff_records_and_emails(monkeypatch):
    captured = {}
    store = _FakeHandoffStore()
    monkeypatch.setattr(settings, "handoff_to", "admin@ejemplo.pe")
    monkeypatch.setattr(es, "send_email", lambda **kw: captured.update(kw) or True)

    res = send_handoff("Usuario molesto por demora", "Pidio tarifa y no llego",
                       user_id="AGBXMBMQ", nombre="Julio", whatsapp="+51947323775",
                       email="julio@ejemplo.pe", store=store)

    assert res.ok
    assert store.added and store.added[0]["motivo"].startswith("Usuario molesto")
    assert captured["to"] == "admin@ejemplo.pe"
    assert captured["reply_to"] == "julio@ejemplo.pe"
    assert "ESCALAMIENTO" in captured["subject"]
    assert "Pidio tarifa" in captured["text"]


def test_send_handoff_email_fail_returns_not_ok(monkeypatch):
    monkeypatch.setattr(es, "send_email", lambda **kw: False)
    res = send_handoff("m", "r", store=_FakeHandoffStore())
    assert res.ok is False


def test_send_handoff_record_failure_still_emails(monkeypatch):
    class _Boom:
        def add(self, **kw):
            raise RuntimeError("firestore down")

    monkeypatch.setattr(es, "send_email", lambda **kw: True)
    res = send_handoff("m", "r", store=_Boom())
    assert res.ok is True  # el registro falla pero el aviso al equipo sí se envía


def test_tool_disabled(monkeypatch):
    monkeypatch.setattr(settings, "handoff_enabled", False)
    out = escalar_a_humano.invoke({"motivo": "x", "resumen_conversacion": "y"})
    assert "no puedo transferirte" in out.lower()


def test_tool_requires_motivo(monkeypatch):
    monkeypatch.setattr(settings, "handoff_enabled", True)
    set_current_user_id("web:sin-codigo")  # evita tocar el registro real
    out = escalar_a_humano.invoke({"motivo": "", "resumen_conversacion": "y"})
    assert "motivo" in out.lower()


def test_tool_happy_path_uses_user_context(monkeypatch):
    monkeypatch.setattr(settings, "handoff_enabled", True)
    calls = {}

    def fake_send(motivo, resumen, *, user_id, nombre, whatsapp, email):
        calls.update(motivo=motivo, resumen=resumen, user_id=user_id, nombre=nombre,
                     whatsapp=whatsapp, email=email)
        return HandoffResult(ok=True, motivo=motivo)

    monkeypatch.setattr(ho, "send_handoff", fake_send)

    class _Reg:
        def get_by_code(self, code):
            return _rec() if code == "AGBXMBMQ" else None

    monkeypatch.setattr(ur, "get_user_registry", lambda: _Reg())
    set_current_user_id("AGBXMBMQ")

    out = escalar_a_humano.invoke({
        "motivo": "Quiere hablar con una persona",
        "resumen_conversacion": "El usuario tiene una queja compleja",
    })

    assert "avis" in out.lower()
    assert calls["nombre"] == "Julio" and calls["email"] == "julio@ejemplo.pe"
    assert calls["user_id"] == "AGBXMBMQ"
