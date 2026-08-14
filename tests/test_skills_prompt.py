"""Tests del system prompt del orquestador (contrato de comportamiento).

Son aserciones de regresión sobre las reglas que el negocio exige de forma
explícita: si alguien reescribe una regla y deja fuera una entidad o un
requisito acordado, estos tests lo detectan.
"""
from app.agent.skills import ORCHESTRATOR_SYSTEM_PROMPT as PROMPT
from app.agent.skills import (OBJECTIVE_SECTION, REASONING_EXAMPLE,
                              SKILL_REGISTRY, TOOLS_SECTION)
from app.agent.tools.derivation_tools import derivar_solicitud_entidad


def test_prompt_incluye_gestores_tecnicos_cite():
    """CITEagroindustrial Chavimochic y la RedCITE deben estar en el mapa de
    entidades como gestores técnicos de soporte tecnológico."""
    assert "CITEagroindustrial Chavimochic" in PROMPT
    assert "RedCITE" in PROMPT
    assert "GESTORES TÉCNICOS" in PROMPT


def test_tool_de_derivacion_menciona_los_cite():
    """La descripción de la tool (lo que ve el LLM) también los considera."""
    desc = derivar_solicitud_entidad.description
    assert "CITEagroindustrial Chavimochic" in desc
    assert "RedCITE" in desc


def test_prompt_exige_todas_las_entidades_involucradas():
    assert "TODAS" in PROMPT and "MÁS DE UNA" in PROMPT


def test_prompt_exige_confirmacion_antes_de_canalizar():
    """El envío al Estado nunca ocurre sin el 'Sí' explícito del ciudadano."""
    assert "SOLO si el usuario" in PROMPT
    assert "CONFIRMA" in PROMPT


def test_prompt_mantiene_entidades_base():
    for entidad in ("SENASA", "SENAMHI", "INDECI", "MIDAGRI", "PROMPERÚ", "SUNAT"):
        assert entidad in PROMPT


# ------------------------------ TOOLS_SECTION -------------------------------
def test_tools_section_declara_todas_las_tools_con_su_descripcion():
    """Todas las tools deben quedar declaradas en el prompt (no solo en el
    schema automático de LangChain), para que el LLM sepa cuál preferir entre
    las que se solapan temáticamente (p. ej. las RAG especializadas vs. la
    general, o los gráficos vs. las tools de texto equivalentes)."""
    assert len(SKILL_REGISTRY) == 14
    for nombre, desc in SKILL_REGISTRY.items():
        assert nombre in TOOLS_SECTION
        assert desc in TOOLS_SECTION


def test_tools_section_no_esta_vacia_de_contenido_util():
    assert "HERRAMIENTAS DISPONIBLES" in TOOLS_SECTION
    assert "consultar_base_conocimiento" in TOOLS_SECTION
    assert "derivar_solicitud_entidad" in TOOLS_SECTION


# ------------------------------ OBJECTIVE_SECTION -----------------------------
def test_objective_section_declara_alcance_informativo_y_del_fen():
    assert "=== OBJETIVO ===" in OBJECTIVE_SECTION
    assert "exportación" in OBJECTIVE_SECTION
    assert "FEN" in OBJECTIVE_SECTION


def test_objective_section_declara_canalizacion_y_escalamiento():
    """Los objetivos operativos ya implícitos en las reglas (canalizar al
    Estado, escalar a humano) deben quedar declarados como parte del
    objetivo, no solo mencionados sueltos dentro de las reglas numeradas."""
    assert "Canaliza al Estado" in OBJECTIVE_SECTION
    assert "Escala a una persona" in OBJECTIVE_SECTION


def test_prompt_ya_no_repite_la_mision_como_prosa_suelta():
    """La antigua 'Tu misión es...' se reemplazó por el bloque declarado; no
    debe quedar duplicada dentro del prompt base."""
    assert "Tu misión es" not in PROMPT


# ----------------------------- REASONING_EXAMPLE -----------------------------
def test_reasoning_example_demuestra_cruce_de_señales_antes_de_decidir():
    """Patrón ART (Sesión 7): percibir -> cruzar señales de varias tools ->
    recién entonces decidir/responder, enseñado por un caso resuelto en vez de
    un nodo de Planning separado."""
    assert "consultar_datos_noaa" in REASONING_EXAMPLE
    assert "consultar_clima" in REASONING_EXAMPLE
    assert "consultar_base_conocimiento" in REASONING_EXAMPLE
    assert "derivar_solicitud_entidad" not in REASONING_EXAMPLE  # se sugiere en prosa
    assert "canalizarse al Estado" in REASONING_EXAMPLE
