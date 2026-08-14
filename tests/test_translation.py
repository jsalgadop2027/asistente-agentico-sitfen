"""Tests de detección de idioma, idioma objetivo y fuentes (sin GCP/LLM)."""
from types import SimpleNamespace

from app.agent.translation import (
    detect_lang,
    extract_sources,
    get_target_lang,
    lang_name,
    set_target_lang,
    sources_label,
)


def _tool_msg(content: str):
    return SimpleNamespace(type="tool", content=content)


def _ai_msg(content: str):
    return SimpleNamespace(type="ai", content=content)


def test_detect_spanish():
    assert detect_lang("¿Qué requisitos necesito para exportar arándano a China?") == "es"


def test_detect_english():
    assert detect_lang("What documents do I need to export blueberries to China?") == "en"


def test_detect_short_or_empty_defaults_spanish():
    assert detect_lang("") == "es"
    assert detect_lang("ok") == "es"


def test_lang_name_known_and_unknown():
    assert lang_name("en") == "inglés"
    assert lang_name("es") == "español"
    assert lang_name("xx") == "xx"  # desconocido: devuelve el código tal cual


def test_target_lang_roundtrip():
    set_target_lang("en")
    assert get_target_lang() == "en"
    set_target_lang("ES")
    assert get_target_lang() == "es"  # se normaliza a minúsculas
    set_target_lang("")
    assert get_target_lang() == "es"  # vacío -> default


# ----------------------------- Fuentes ---------------------------------------
def test_extract_sources_dedup_and_order():
    msgs = [
        _ai_msg("razonamiento"),
        _tool_msg("[1] (Fuente: a.pdf)\ntexto\n\n[Fuentes disponibles: a.pdf, b.pdf]"),
        _tool_msg("contenido\n\n[Fuentes: b.pdf, c.pdf]"),
        _ai_msg("respuesta final sin fuentes"),
    ]
    assert extract_sources(msgs) == ["a.pdf", "b.pdf", "c.pdf"]


def test_extract_sources_singular_marker():
    msgs = [_tool_msg("Documento recién incorporado...\n[Fuente: nuevo.pdf]")]
    assert extract_sources(msgs) == ["nuevo.pdf"]


def test_extract_sources_ignores_non_tool_and_empty():
    # El marcador en un mensaje 'ai' no cuenta; solo los 'tool'.
    msgs = [_ai_msg("[Fuentes: no.pdf]"), _tool_msg("sin marcador aquí")]
    assert extract_sources(msgs) == []


def test_sources_label_by_language():
    assert sources_label("es") == "Fuentes"
    assert sources_label("en") == "Sources"
    assert sources_label("xx") == "Fuentes"  # desconocido -> default español
