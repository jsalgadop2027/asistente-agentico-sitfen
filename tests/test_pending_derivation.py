# -*- coding: utf-8 -*-
"""Confirmación determinista de derivaciones (app/pending_derivation.py).

Regresión de dos bugs reales de producción, ambos por dejar en manos del LLM la
decisión de EJECUTAR la derivación:

1. Callejón sin salida: el agente ofrecía canalizar, el usuario respondía "Sí"
   cuatro veces seguidas, y no se canalizaba nada porque el LLM narraba el éxito
   sin invocar la tool.
2. "Sí" amarrado a un caso viejo: tras preguntar por costos portuarios, un "sí"
   disparó la derivación de un caso planteado nueve minutos antes.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.pending_derivation import (Pending, PendingDerivationStore, is_offer,
                                    last_substantive_user_message)


class T:
    """Doble de Turn (role/content)."""
    def __init__(self, role, content):
        self.role, self.content = role, content


# --------------------------------- is_offer -----------------------------------
@pytest.mark.parametrize("texto", [
    # Subjuntivo con cambio de raíz: comunicar -> comunique, canalizar -> canalice.
    # Buscar "comunic"/"canaliz" NO los encuentra (fallo real del primer intento).
    "¿quieres que le comunique tu interés en capacitación a SENASA y al CITE?",
    "¿Deseas que comunique tu caso a SENASA?",
    "¿Te gustaría que canalice tu solicitud a MIDAGRI?",
    "¿Quieres que derive tu caso a la municipalidad?",
    "Julio, ¿quieres que les informe a INDECI y al Gobierno Regional?",
    "¿Confirmas que lo envíe a las entidades correspondientes?",
    "¿Lo canalizo a SENASA?",
])
def test_detecta_ofrecimientos(texto):
    assert is_offer(texto)


@pytest.mark.parametrize("texto", [
    "Puedo ayudarte con eso. ¿Tienes alguna otra pregunta?",
    "SENASA es la autoridad en sanidad agraria del Perú.",
    "Los costos portuarios son S/ 450. ¿Te ayudo con algo más?",
    "¿Qué variedad de arándano cultivas?",
    # Ofrecer INFORMACIÓN al usuario no es derivar: "te informe"/"te comunique"
    # van dirigidos a él, no a una entidad.
    "¿Quieres que te informe sobre los requisitos de exportación?",
    "¿Deseas que te comunique los resultados cuando los tenga?",
    # Afirmación de hecho consumado: es lo contrario de un ofrecimiento.
    "He comunicado tu caso a SENASA.",
])
def test_no_confunde_otros_textos(texto):
    assert not is_offer(texto)


# ------------------- last_substantive_user_message ----------------------------
def test_ignora_confirmaciones_al_buscar_el_caso():
    """Si el ofrecimiento se emite justo tras un "Sí", el caso a derivar sigue
    siendo el mensaje real del usuario, no el "Sí"."""
    hist = [
        T("user", "Necesito capacitar a mi personal en buenas prácticas agrícolas."),
        T("assistant", "¿Quieres que lo comunique a SENASA?"),
        T("user", "Sí"),
    ]
    assert "capacitar" in last_substantive_user_message(hist, "Sí")


def test_prefiere_el_mensaje_actual_si_es_sustantivo():
    hist = [T("user", "Necesito capacitación en BPA.")]
    assert "trocha" in last_substantive_user_message(hist, "La trocha regional colapsó.")


def test_sin_caso_devuelve_vacio():
    assert last_substantive_user_message([T("user", "Sí"), T("user", "OK")], "Sí") == ""


# ------------------------------ store + TTL -----------------------------------
class _Doc:
    def __init__(self, store, key):
        self._store, self._key = store, key

    def get(self):
        data = self._store.get(self._key)

        class _Snap:
            exists = data is not None

            def to_dict(self_inner):
                return data
        return _Snap()

    def set(self, data):
        self._store[self._key] = data

    def delete(self):
        self._store.pop(self._key, None)


class _Coll:
    def __init__(self, store):
        self._store = store

    def document(self, key):
        return _Doc(self._store, key)


class _FakeClient:
    def __init__(self):
        self.data = {}

    def collection(self, name):
        return _Coll(self.data)


def test_guarda_y_recupera_el_caso():
    store = PendingDerivationStore(client=_FakeClient())
    store.set("U1", "La trocha regional colapsó.")
    p = store.get("U1")
    assert isinstance(p, Pending) and "trocha" in p.caso


def test_clear_descarta_el_pendiente():
    store = PendingDerivationStore(client=_FakeClient())
    store.set("U1", "caso")
    store.clear("U1")
    assert store.get("U1") is None


def test_pendiente_caduca_por_tiempo():
    """Un "Sí" tardío no debe resucitar un caso planteado mucho antes."""
    client = _FakeClient()
    store = PendingDerivationStore(client=client)
    store.set("U1", "caso viejo")
    client.data["U1"]["created_at"] = (
        datetime.now(timezone.utc) - timedelta(hours=5))
    assert store.get("U1") is None


def test_sin_pendiente_devuelve_none():
    assert PendingDerivationStore(client=_FakeClient()).get("desconocido") is None


# ------------------- la tool rechaza el "Sí" huérfano -------------------------
def test_tool_rechaza_confirmacion_sin_ofrecimiento_vivo(monkeypatch):
    """Un "sí" afirmativo NO basta: si no hay un ofrecimiento vigente, esa
    confirmación no está anclada a ningún caso.

    Bug real: tras ofrecer canalizar una vía colapsada, el usuario preguntó por
    costos portuarios (lo que descarta el pendiente) y luego dijo "sí"; el LLM
    invocó la tool igualmente y derivó el caso viejo.
    """
    import app.agent.tools.derivation_tools as dt
    import app.agent.turn_context as tc
    import app.pending_derivation as pd

    monkeypatch.setattr(tc, "get_current_user_text", lambda: "sí")
    monkeypatch.setattr(tc, "get_current_user_id", lambda: "U1")
    # Sin ofrecimiento vivo para ese usuario.
    monkeypatch.setattr(pd, "PendingDerivationStore",
                        lambda *a, **k: PendingDerivationStore(client=_FakeClient()))

    ejecutado = []
    monkeypatch.setattr(dt, "ejecutar_derivacion",
                        lambda *a, **k: ejecutado.append(1) or "no deberia")

    out = dt.derivar_solicitud_entidad.func(
        entidades="INDECI", resumen_solicitud="La trocha regional colapsó.")

    assert not ejecutado, "no debio derivar sin un ofrecimiento vigente"
    assert "no tengo claro" in out.lower()
    # El rechazo no debe leerse como un nuevo ofrecimiento: si lo fuera, un "sí"
    # posterior quedaria anclado al caso equivocado.
    assert not is_offer(out)
