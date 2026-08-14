"""Tests del reenganche (#7 fuerte) — sin GCP ni Twilio (fakes/monkeypatch)."""
from datetime import datetime, timedelta, timezone

import app.channels.twilio_whatsapp as tw
import app.reengagement as re_mod
import app.user_registry as ur
from app.config import settings
from app.user_registry import UserRecord, UserRegistry


def _rec(code, *, mins_seen=None, mins_reeng=None, active=True, opt=True):
    now = datetime.now(timezone.utc)
    return UserRecord(
        code=code, nombre="X", apellido="Y", direccion="", rubro="Comercio",
        whatsapp="+51900000000", email="x@e.pe", active=active, send_kb_summary=opt,
        last_seen_at=(now - timedelta(minutes=mins_seen)) if mins_seen is not None else None,
        last_reengaged_at=(now - timedelta(minutes=mins_reeng)) if mins_reeng is not None else None,
    )


class _StubReg:
    """Enlaza el método real de filtrado a una lista de usuarios en memoria."""
    def __init__(self, users):
        self._users = users

    def list_users(self):
        return self._users

    reengagement_candidates = UserRegistry.reengagement_candidates


def test_candidates_selects_inactive_respecting_cooldown_and_optin():
    """Umbral de 30 min de inactividad y enfriamiento de 3 h entre avisos."""
    users = [
        _rec("A", mins_seen=45),                    # 45 min sin escribir -> sí
        _rec("B", mins_seen=10),                     # escribió hace 10 min -> no
        _rec("C", mins_seen=120, mins_reeng=60),     # ya avisado hace 1 h (<3 h) -> no
        _rec("D", mins_seen=300, mins_reeng=240),    # último aviso hace 4 h -> sí
        _rec("E", mins_seen=None),                   # nunca escribió -> sí
        _rec("F", mins_seen=120, active=False),      # inactivo del sistema -> no
        _rec("G", mins_seen=120, opt=False),         # sin opt-in -> no
    ]
    got = {u.code for u in
           _StubReg(users).reengagement_candidates(inactive_minutes=30, cooldown_minutes=180)}
    assert got == {"A", "D", "E"}


def test_candidates_boundary_just_under_threshold_is_not_reengaged():
    """Quien escribió hace 29 min sigue en conversación: no se le interrumpe."""
    got = _StubReg([_rec("A", mins_seen=29)]).reengagement_candidates(
        inactive_minutes=30, cooldown_minutes=180)
    assert got == []


def test_candidates_respects_limit():
    users = [_rec(f"U{i}", mins_seen=60) for i in range(5)]
    out = _StubReg(users).reengagement_candidates(
        inactive_minutes=30, cooldown_minutes=180, limit=3)
    assert len(out) == 3


class _FakeRegistry:
    def __init__(self, candidates):
        self._c = candidates
        self.marked = []

    def reengagement_candidates(self, **kw):
        return self._c

    def mark_reengaged(self, code):
        self.marked.append(code)


def test_run_reengagement_sends_template_and_marks(monkeypatch):
    sent = []
    monkeypatch.setattr(settings, "reengage_template_sid", "HXRE")
    monkeypatch.setattr(re_mod, "_context_snippet", lambda code: "cómo va tu cultivo")
    monkeypatch.setattr(tw, "send_whatsapp_template",
                        lambda to, sid, variables: sent.append((to, sid, variables)) or True)
    reg = _FakeRegistry([_rec("A", mins_seen=30), _rec("B", mins_seen=30)])
    monkeypatch.setattr(ur, "get_user_registry", lambda: reg)

    res = re_mod.run_reengagement()

    assert res.candidates == 2 and res.sent == 2 and res.failed == 0
    assert reg.marked == ["A", "B"]
    assert sent[0][1] == "HXRE"
    assert sent[0][2] == {"1": "X", "2": "cómo va tu cultivo"}


# ------------------------------ _context_snippet -----------------------------
class _FakeGoalStore:
    def __init__(self, goal=None):
        self._goal = goal

    def get(self, user_id):
        return self._goal


class _FakeConcernStore:
    def __init__(self, rows=None):
        self._rows = rows or []

    def list_recent_open_for_user(self, user_id, *, days, limit):
        return self._rows[:limit]


def test_context_snippet_prefers_goal(monkeypatch):
    import app.user_goals as goals_mod

    monkeypatch.setattr(goals_mod, "GoalStore",
                        lambda: _FakeGoalStore("exportar arándano a China"))
    assert re_mod._context_snippet("AGB1") == "tu objetivo de exportar arándano a China"


def test_context_snippet_falls_back_to_concern(monkeypatch):
    import app.concerns as concerns_mod
    import app.user_goals as goals_mod

    monkeypatch.setattr(goals_mod, "GoalStore", lambda: _FakeGoalStore(None))
    monkeypatch.setattr(concerns_mod, "ConcernStore",
                        lambda: _FakeConcernStore([{"resumen": "teme perder su cosecha"}]))
    out = re_mod._context_snippet("AGB1")
    assert out == "tu consulta sobre teme perder su cosecha"


def test_context_snippet_default_when_nothing(monkeypatch):
    import app.concerns as concerns_mod
    import app.user_goals as goals_mod

    monkeypatch.setattr(goals_mod, "GoalStore", lambda: _FakeGoalStore(None))
    monkeypatch.setattr(concerns_mod, "ConcernStore", lambda: _FakeConcernStore([]))
    assert re_mod._context_snippet("AGB1") == re_mod._DEFAULT_CONTEXT


def test_context_snippet_is_fail_open(monkeypatch):
    import app.concerns as concerns_mod
    import app.user_goals as goals_mod

    def boom():
        raise RuntimeError("Firestore caido")

    monkeypatch.setattr(goals_mod, "GoalStore", boom)
    monkeypatch.setattr(concerns_mod, "ConcernStore", boom)
    assert re_mod._context_snippet("AGB1") == re_mod._DEFAULT_CONTEXT


def test_run_reengagement_skips_without_template(monkeypatch):
    monkeypatch.setattr(settings, "reengage_template_sid", None)
    res = re_mod.run_reengagement()
    assert res.sent == 0 and res.skipped_reason is not None


def test_run_reengagement_does_not_mark_on_failure(monkeypatch):
    monkeypatch.setattr(settings, "reengage_template_sid", "HXRE")
    monkeypatch.setattr(tw, "send_whatsapp_template",
                        lambda to, sid, variables: False)
    reg = _FakeRegistry([_rec("A", mins_seen=30)])
    monkeypatch.setattr(ur, "get_user_registry", lambda: reg)

    res = re_mod.run_reengagement()

    assert res.sent == 0 and res.failed == 1 and res.failures == ["A"]
    assert reg.marked == []  # no se marca si no se envió


# ---------------- Observabilidad: ninguna salida puede quedar muda -------------
def _capture_done(monkeypatch):
    """Captura los eventos `reengage_done` emitidos durante la ejecución."""
    eventos = []

    class _Log:
        def info(self, event, **kw):
            eventos.append((event, kw))

        def warning(self, event, **kw):
            eventos.append((event, kw))

    monkeypatch.setattr(re_mod, "logger", _Log())
    return eventos


def test_siempre_registra_el_cierre_aunque_no_envie_nada(monkeypatch):
    """El job salía en silencio por tres caminos distintos y desde fuera los tres
    se veían igual: imposible distinguir "no había a quién escribir" de "la
    plantilla se perdió en un despliegue y esto lleva semanas muerto"."""
    # 1) sin plantilla configurada
    eventos = _capture_done(monkeypatch)
    monkeypatch.setattr(settings, "reengage_template_sid", None)
    re_mod.run_reengagement()
    nombres = [e for e, _ in eventos]
    assert "reengage_done" in nombres
    assert "reengage_template_missing" in nombres  # mala config, no estado normal

    # 2) sin candidatos (el caso normal en operación)
    eventos = _capture_done(monkeypatch)
    monkeypatch.setattr(settings, "reengage_template_sid", "HXRE")
    monkeypatch.setattr(ur, "get_user_registry", lambda: _FakeRegistry([]))
    re_mod.run_reengagement()
    cierres = [kw for e, kw in eventos if e == "reengage_done"]
    assert cierres and cierres[0]["candidates"] == 0
    assert "sin usuarios" in cierres[0]["motivo"]

    # 3) deshabilitado
    eventos = _capture_done(monkeypatch)
    monkeypatch.setattr(settings, "reengage_enabled", False)
    re_mod.run_reengagement()
    cierres = [kw for e, kw in eventos if e == "reengage_done"]
    assert cierres and "deshabilitado" in cierres[0]["motivo"]


def test_cierre_del_camino_normal_reporta_enviados(monkeypatch):
    eventos = _capture_done(monkeypatch)
    monkeypatch.setattr(settings, "reengage_enabled", True)
    monkeypatch.setattr(settings, "reengage_template_sid", "HXRE")
    monkeypatch.setattr(tw, "send_whatsapp_template",
                        lambda to, sid, variables: True)
    monkeypatch.setattr(ur, "get_user_registry",
                        lambda: _FakeRegistry([_rec("A", mins_seen=30)]))

    re_mod.run_reengagement()

    cierres = [kw for e, kw in eventos if e == "reengage_done"]
    assert cierres and cierres[0]["sent"] == 1 and cierres[0]["motivo"] == "ok"
