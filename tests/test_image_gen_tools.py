"""Tests de la tool de generación de imágenes — sin red ni GCP.

Igual que `chart_tools.py`, la llamada real a Vertex AI Imagen y la subida a GCS no
se testean aquí (infra externa, ver `tests/test_noaa_tools.py` para el mismo
criterio): solo se cubre la lógica pura y las ramas de guarda (kill switch, cupo).
"""
import app.agent.tools.image_gen_tools as igt
from app.agent.tools.image_gen_tools import _build_prompt, generar_imagen
from app.config import settings


def test_build_prompt_incluye_el_tema():
    prompt = _build_prompt("riego por goteo en arándano")
    assert "riego por goteo en arándano" in prompt
    assert "arándano" in prompt  # contexto de dominio siempre presente


def test_build_prompt_usa_fallback_si_vacio():
    prompt = _build_prompt("   ")
    assert "Tema: el sector arándano peruano" in prompt


def test_build_prompt_no_pide_texto_legible():
    """El prefijo de estilo evita pedir texto/logos: Imagen los renderiza mal."""
    prompt = _build_prompt("cualquier tema")
    assert "sin texto ni logotipos" in prompt


def test_generar_imagen_respeta_kill_switch(monkeypatch):
    monkeypatch.setattr(settings, "image_gen_enabled", False)
    out = generar_imagen.invoke({"descripcion": "poda de arándano"})
    assert "no está disponible" in out
    assert "GRAFICO_URL" not in out


def test_generar_imagen_respeta_cupo_diario(monkeypatch):
    monkeypatch.setattr(settings, "image_gen_enabled", True)
    monkeypatch.setattr(settings, "image_gen_max_per_day", 5)
    monkeypatch.setattr(igt, "_check_daily_quota", lambda user_id: False)
    out = generar_imagen.invoke({"descripcion": "esquema de riego"})
    assert "máximo de imágenes permitidas hoy" in out
    assert "5" in out
    assert "GRAFICO_URL" not in out
