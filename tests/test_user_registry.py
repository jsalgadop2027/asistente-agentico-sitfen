"""Tests del registro de usuarios y control de sesión (Firestore falso, sin GCP)."""
import datetime as dt

import pytest
from google.cloud import firestore

from app.user_registry import (
    ECONOMIC_SECTORS,
    UserRegistry,
    UserRegistryError,
    normalize_whatsapp,
)


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

    def delete(self):
        self._coll.store.pop(self.id, None)


class _Query:
    def __init__(self, items):
        self._items = items

    def where(self, filter=None):
        field, value = filter.field_path, filter.value
        return _Query([(k, v) for k, v in self._items if v.get(field) == value])

    def limit(self, n):
        return _Query(self._items[:n])

    def stream(self):
        return [_Snap(k, v) for k, v in self._items]


class _Collection:
    def __init__(self):
        self.store = {}

    def document(self, doc_id):
        return _Doc(self, doc_id)

    def where(self, filter=None):
        return _Query(list(self.store.items())).where(filter=filter)

    def stream(self):
        return [_Snap(k, v) for k, v in self.store.items()]


class _FakeClient:
    def __init__(self):
        self._colls = {}

    def collection(self, name):
        return self._colls.setdefault(name, _Collection())


@pytest.fixture
def registry():
    return UserRegistry(client=_FakeClient())


# --------------------------- Normalización de número --------------------------
def test_normalize_whatsapp_variants():
    assert normalize_whatsapp("whatsapp:+51 987 654 321") == "+51987654321"
    assert normalize_whatsapp("987654321") == "+51987654321"  # asume Perú
    assert normalize_whatsapp("+1 (415) 523-8886") == "+14155238886"


def test_normalize_whatsapp_invalid():
    with pytest.raises(UserRegistryError):
        normalize_whatsapp("abc")


# --------------------------------- Alta ---------------------------------------
def _crear(reg, **over):
    data = dict(nombre="Ana", apellido="Torres", direccion="Av. Siempre Viva 123",
                rubro="Agroindustrial", whatsapp="987654321", email="ana@empresa.pe")
    data.update(over)
    return reg.create(**data)


def test_create_generates_8char_code_with_sector_prefix(registry):
    user = _crear(registry)
    assert len(user.code) == 8
    assert user.code.startswith("AG")  # Agroindustrial
    assert user.whatsapp == "+51987654321"


def test_create_rejects_duplicate_whatsapp(registry):
    _crear(registry)
    with pytest.raises(UserRegistryError):
        _crear(registry, whatsapp="+51987654321", email="otra@empresa.pe")


def test_create_rejects_bad_email_and_sector(registry):
    with pytest.raises(UserRegistryError):
        _crear(registry, email="no-es-correo")
    with pytest.raises(UserRegistryError):
        _crear(registry, rubro="Minero")


def test_all_sectors_have_prefix(registry):
    for i, rubro in enumerate(ECONOMIC_SECTORS):
        u = _crear(registry, rubro=rubro, whatsapp=f"98765{i:04d}",
                   email=f"u{i}@e.pe")
        assert len(u.code) == 8


# -------------------- Preferencia de resumen de novedades ---------------------
def test_send_kb_summary_default_true(registry):
    user = _crear(registry)
    assert user.send_kb_summary is True
    assert registry.get_by_code(user.code).send_kb_summary is True


def test_send_kb_summary_opt_out_on_create(registry):
    user = _crear(registry, send_kb_summary=False)
    assert user.send_kb_summary is False
    assert registry.get_by_code(user.code).send_kb_summary is False


def test_update_send_kb_summary(registry):
    user = _crear(registry)
    registry.update(user.code, send_kb_summary=False)
    assert registry.get_by_code(user.code).send_kb_summary is False


def test_kb_summary_recipients_filters_active_and_optin(registry):
    a = _crear(registry, whatsapp="987650001", email="a@e.pe")  # opt-in, activo
    b = _crear(registry, whatsapp="987650002", email="b@e.pe",
               send_kb_summary=False)                            # opt-out
    c = _crear(registry, whatsapp="987650003", email="c@e.pe")  # opt-in pero inactivo
    registry.set_active(c.code, False)

    codes = {u.code for u in registry.kb_summary_recipients()}
    assert a.code in codes
    assert b.code not in codes
    assert c.code not in codes


# ------------------------------ Edición / baja --------------------------------
def test_update_and_get(registry):
    user = _crear(registry)
    registry.update(user.code, nombre="Ana María", rubro="Comercio")
    fetched = registry.get_by_code(user.code)
    assert fetched.nombre == "Ana María"
    assert fetched.rubro == "Comercio"
    assert fetched.code == user.code  # el código es inmutable


def test_delete(registry):
    user = _crear(registry)
    registry.delete(user.code)
    assert registry.get_by_code(user.code) is None


# ------------------------- Control de sesión WhatsApp -------------------------
def test_resolve_session_registered_returns_code(registry):
    user = _crear(registry)
    assert registry.resolve_session("whatsapp:+51987654321") == user.code


def test_resolve_session_unregistered_pseudonymizes(registry):
    # Un número no registrado NO se usa en claro como clave de sesión: se
    # pseudonimiza (sin PII) de forma estable.
    token = registry.resolve_session("+51000111222")
    assert token != "+51000111222"
    assert "51000111222" not in token
    assert token == registry.resolve_session("+51000111222")  # estable


def test_resolve_session_inactive_pseudonymizes(registry):
    user = _crear(registry)
    registry.set_active(user.code, False)
    token = registry.resolve_session("+51987654321")
    assert token != user.code          # inactivo: no usa el código interno
    assert token != "+51987654321"     # ni el teléfono en claro
    assert "987654321" not in token


# --------------------------- Saludo por nombre --------------------------------
def test_registered_first_name(monkeypatch, registry):
    import app.user_registry as ur

    user = _crear(registry)
    monkeypatch.setattr(ur, "get_user_registry", lambda: registry)
    # Id de sesión = código interno de un usuario registrado -> devuelve su nombre.
    assert ur.registered_first_name(user.code) == "Ana"
    # Sesiones que NO son códigos: None sin tocar Firestore.
    assert ur.registered_first_name("web:abc123") is None
    assert ur.registered_first_name("+51987654321") is None
    assert ur.registered_first_name("anon") is None
    # Código bien formado pero inexistente -> None.
    assert ur.registered_first_name("ZZ999999") is None


def test_looks_like_code():
    from app.user_registry import looks_like_code

    assert looks_like_code("AG7K2M9Q") is True
    assert looks_like_code("web:abc") is False
    assert looks_like_code("+51987654321") is False
    assert looks_like_code("ag7k2m9q") is False  # debe ir en mayúsculas
