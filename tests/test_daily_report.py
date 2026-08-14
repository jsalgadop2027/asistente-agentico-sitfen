"""Tests del informe diario (#8) — sin GCP ni LLM (fakes/monkeypatch)."""
from datetime import datetime, timezone

import app.daily_report as dr
from app.daily_report import build_daily_report


class _FakeStore:
    def __init__(self, rows):
        self._rows = rows

    def list_for_day(self, day):
        return self._rows


class _FakeRec:
    def __init__(self, nombre, apellido):
        self.nombre = nombre
        self.apellido = apellido


class _FakeRegistry:
    def __init__(self, mapping):
        self._m = mapping

    def get_by_code(self, code):
        return self._m.get(code)


def _rows():
    return [
        {"user_id": "AGB1", "tipo": "reclamo", "resumen": "no carga la app",
         "created_at": datetime(2026, 7, 18, 14, 30, tzinfo=timezone.utc)},
        {"user_id": "AGB2", "tipo": "pedido", "resumen": "tarifa a China",
         "created_at": datetime(2026, 7, 18, 15, 0, tzinfo=timezone.utc)},
        {"user_id": "AGB1", "tipo": "sugerencia", "resumen": "agregar alertas SST",
         "created_at": None},
    ]


def _patch_registry(monkeypatch, mapping):
    from app import user_registry as ur
    monkeypatch.setattr(ur, "get_user_registry", lambda: _FakeRegistry(mapping))


def test_build_daily_report_groups_and_identifies(monkeypatch):
    monkeypatch.setattr(dr, "_build_summary", lambda by: "Resumen de prueba")
    _patch_registry(monkeypatch, {"AGB1": _FakeRec("Ana", "Lopez"),
                                  "AGB2": _FakeRec("Luis", "Diaz")})

    rep = build_daily_report(day="2026-07-18", store=_FakeStore(_rows()))

    assert rep.total == 3
    assert len(rep.by_type["reclamo"]) == 1
    assert len(rep.by_type["pedido"]) == 1
    assert len(rep.by_type["sugerencia"]) == 1
    assert len(rep.by_type["recomendacion"]) == 0
    assert "Ana Lopez (AGB1)" in rep.html
    assert "Resumen de prueba" in rep.html
    assert "2026-07-18" in rep.subject and "(3)" in rep.subject
    # 14:30 UTC -> 09:30 hora de Lima (UTC-5), en ciclo de 12 horas
    assert "09:30 AM" in rep.html


def test_build_daily_report_includes_preocupacion(monkeypatch):
    monkeypatch.setattr(dr, "_build_summary", lambda by: "Resumen")
    _patch_registry(monkeypatch, {"AGB1": _FakeRec("Ana", "Lopez")})
    rows = [{"user_id": "AGB1", "tipo": "preocupacion",
             "resumen": "teme perder su cosecha por el FEN", "created_at": None}]

    rep = build_daily_report(day="2026-07-18", store=_FakeStore(rows))

    assert len(rep.by_type["preocupacion"]) == 1
    assert "Preocupaciones" in rep.html
    assert "teme perder su cosecha" in rep.text


def test_build_daily_report_empty_no_llm(monkeypatch):
    _patch_registry(monkeypatch, {})
    rep = build_daily_report(day="2026-07-18", store=_FakeStore([]))
    assert rep.total == 0
    # Sin inquietudes NO llama al LLM y usa el texto fijo.
    assert "No se registraron inquietudes" in rep.text


def test_send_daily_report_sends_email(monkeypatch):
    captured = {}
    monkeypatch.setattr(dr, "build_daily_report", lambda day=None: dr.DailyReport(
        day="2026-07-18", total=1, by_type={}, subject="Asunto",
        html="<b>h</b>", text="t"))
    import app.channels.email_sender as es
    monkeypatch.setattr(es, "send_email",
                        lambda **kw: captured.update(kw) or True)

    assert dr.send_daily_report() is True
    # Contra el setting, no contra una dirección literal: el destinatario cambia
    # (p. ej. al migrar de cuenta) y el test no debe romperse por eso.
    assert captured["to"] == dr.settings.daily_report_to
    assert captured["subject"] == "Asunto"
