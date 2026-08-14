"""Tests del router multimodelo Flash <-> Pro (no requieren GCP)."""
from app.agent.router import ModelTier, route_model
from app.config import settings


def test_simple_query_routes_to_flash():
    d = route_model("¿Qué documentos necesito para exportar arándano?")
    assert d.tier is ModelTier.FAST
    assert d.pro is False


def test_greeting_routes_to_flash():
    assert route_model("Hola, buenos días").tier is ModelTier.FAST


def test_reasoning_keyword_routes_to_pro():
    d = route_model("Analiza la competitividad del arándano peruano")
    assert d.tier is ModelTier.PRO
    assert d.reason.startswith("keyword:")


def test_comparison_routes_to_pro():
    assert route_model("Compara los mercados de EE.UU. y China").pro is True


def test_causal_why_routes_to_pro():
    assert route_model("¿Por qué Perú es competitivo en arándanos?").pro is True


def test_english_reasoning_routes_to_pro():
    assert route_model("Compare Peru vs Chile blueberry exports").pro is True


def test_multiple_questions_routes_to_pro():
    d = route_model("¿Qué mercados hay? ¿Cuál conviene más?")
    assert d.tier is ModelTier.PRO
    assert d.reason == "multi_question"


def test_long_query_routes_to_pro():
    text = " ".join(["arándano"] * (settings.router_pro_min_words + 5))
    d = route_model(text)
    assert d.tier is ModelTier.PRO
    assert d.reason.startswith("long_query:")


def test_empty_query_routes_to_flash():
    assert route_model("").tier is ModelTier.FAST
    assert route_model("   ").tier is ModelTier.FAST


def test_router_disabled_forces_flash(monkeypatch):
    monkeypatch.setattr(settings, "router_enabled", False)
    # Aun con verbo de razonamiento, si el router está deshabilitado -> Flash.
    d = route_model("Analiza y compara todo el mercado")
    assert d.tier is ModelTier.FAST
    assert d.reason == "router_disabled"
