"""Tests del catálogo cerrado de entidades y su clasificador — sin GCP."""
from app.entity_catalog import (ENTITY_CATALOG, URGENCY_LEVELS,
                                _build_classification_prompt, _parse_ids,
                                evaluar_urgencia, identificar_entidades,
                                match_known_entities)


def test_catalog_has_exactly_ten_entities():
    assert len(ENTITY_CATALOG) == 10


def test_catalog_entries_have_unique_ids_and_fifteen_examples():
    ids = [e.id for e in ENTITY_CATALOG]
    assert len(ids) == len(set(ids))  # sin ids duplicados
    for e in ENTITY_CATALOG:
        assert e.nombre and e.dominio
        assert len(e.ejemplos) == 15


def test_classification_prompt_includes_every_entity_and_examples():
    prompt = _build_classification_prompt("Perdí mi cosecha por una plaga")
    for e in ENTITY_CATALOG:
        assert e.id in prompt
        for ejemplo in e.ejemplos:
            assert ejemplo in prompt


def test_classification_prompt_omits_urgency_clause_by_default():
    prompt = _build_classification_prompt("Perdí mi cosecha por una plaga")
    assert "URGENCIA" not in prompt


def test_classification_prompt_adds_urgency_clause_when_high():
    prompt = _build_classification_prompt(
        "El río está creciendo cerca de mi parcela", urgencia="critica")
    assert 'URGENCIA "critica"' in prompt
    assert '"indeci"' in prompt.split("URGENCIA")[1].split("CATÁLOGO")[0]


def test_classification_prompt_ignores_low_urgency():
    prompt = _build_classification_prompt("Consulta general", urgencia="baja")
    assert "URGENCIA" not in prompt


# ------------------------------- _parse_ids -------------------------------
def test_parse_ids_filters_unknown_and_dedups():
    out = _parse_ids('["senasa", "senasa", "entidad_inventada", "sunat"]')
    assert out == ["senasa", "sunat"]


def test_parse_ids_case_insensitive():
    assert _parse_ids('["SENASA"]') == ["senasa"]


def test_parse_ids_empty_list():
    assert _parse_ids("[]") == []


def test_parse_ids_garbage_returns_empty():
    assert _parse_ids("esto no es json") == []


def test_parse_ids_non_list_json_returns_empty():
    assert _parse_ids('{"tipo": "senasa"}') == []


def test_parse_ids_fenced_json():
    raw = '```json\n["indeci", "senamhi"]\n```'
    assert _parse_ids(raw) == ["indeci", "senamhi"]


# --------------------------- identificar_entidades --------------------------
def test_identificar_entidades_empty_resumen_short_circuits(monkeypatch):
    import app.agent.models as models

    called = []

    def spy(**kw):
        called.append(kw)
        raise AssertionError("no debería invocar el LLM con resumen vacío")

    monkeypatch.setattr(models, "get_llm", spy)
    assert identificar_entidades("") == []
    assert identificar_entidades("   ") == []
    assert called == []  # ni siquiera intenta llamar al LLM


def test_identificar_entidades_maps_ids_to_display_names(monkeypatch):
    class _FakeResp:
        content = '["senasa", "cite_chavimochic"]'

    class _FakeLLM:
        def invoke(self, prompt):
            return _FakeResp()

    import app.agent.models as models

    monkeypatch.setattr(models, "get_llm", lambda **kw: _FakeLLM())

    out = identificar_entidades("Plaga y baja calidad poscosecha")
    assert out == ["SENASA", "CITEagroindustrial Chavimochic"]


def test_identificar_entidades_is_fail_open_on_llm_error(monkeypatch):
    import app.agent.models as models

    def boom(**kw):
        raise RuntimeError("Vertex AI no disponible")

    monkeypatch.setattr(models, "get_llm", boom)
    assert identificar_entidades("Cualquier caso") == []


def test_identificar_entidades_fail_open_on_garbage_llm_output(monkeypatch):
    class _FakeResp:
        content = "no es json"

    class _FakeLLM:
        def invoke(self, prompt):
            return _FakeResp()

    import app.agent.models as models

    monkeypatch.setattr(models, "get_llm", lambda **kw: _FakeLLM())
    assert identificar_entidades("Cualquier caso") == []


# ------------------------------ evaluar_urgencia -----------------------------
def test_evaluar_urgencia_empty_resumen_short_circuits(monkeypatch):
    import app.agent.models as models

    def spy(**kw):
        raise AssertionError("no debería invocar el LLM con resumen vacío")

    monkeypatch.setattr(models, "get_llm", spy)
    assert evaluar_urgencia("") == "media"
    assert evaluar_urgencia("   ") == "media"


def test_evaluar_urgencia_parses_quoted_level(monkeypatch):
    class _FakeResp:
        content = '"critica"'

    class _FakeLLM:
        def invoke(self, prompt):
            return _FakeResp()

    import app.agent.models as models

    monkeypatch.setattr(models, "get_llm", lambda **kw: _FakeLLM())
    assert evaluar_urgencia("El río está inundando mi parcela") == "critica"


def test_evaluar_urgencia_fail_open_on_llm_error(monkeypatch):
    import app.agent.models as models

    def boom(**kw):
        raise RuntimeError("Vertex AI no disponible")

    monkeypatch.setattr(models, "get_llm", boom)
    assert evaluar_urgencia("Cualquier caso") == "media"


def test_evaluar_urgencia_fail_open_on_invalid_level(monkeypatch):
    class _FakeResp:
        content = "no sé"

    class _FakeLLM:
        def invoke(self, prompt):
            return _FakeResp()

    import app.agent.models as models

    monkeypatch.setattr(models, "get_llm", lambda **kw: _FakeLLM())
    assert evaluar_urgencia("Cualquier caso") == "media"


def test_evaluar_urgencia_only_returns_known_levels():
    assert set(URGENCY_LEVELS) == {"baja", "media", "alta", "critica"}


# --------------------------- match_known_entities ----------------------------
def test_match_known_entities_exact_names():
    out = match_known_entities(["SENASA", "CITEagroindustrial Chavimochic"])
    assert out == ["SENASA", "CITEagroindustrial Chavimochic"]


def test_match_known_entities_accepts_partial_variant():
    # El LLM a veces abrevia el nombre completo del catálogo.
    assert match_known_entities(["Chavimochic"]) == \
        ["CITEagroindustrial Chavimochic"]


def test_match_known_entities_case_insensitive():
    assert match_known_entities(["senasa"]) == ["SENASA"]


def test_match_known_entities_discards_unknown_names():
    # Nunca se inventa ni se deja pasar una entidad fuera del catálogo.
    out = match_known_entities(["Entidad Inventada", "SUNAT"])
    assert out == ["SUNAT"]


def test_match_known_entities_dedups():
    out = match_known_entities(["SENASA", "senasa", "SENASA"])
    assert out == ["SENASA"]


def test_match_known_entities_empty_input():
    assert match_known_entities([]) == []
    assert match_known_entities([""]) == []
