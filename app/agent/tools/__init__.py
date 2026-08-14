"""Tools del agente: funcionalidades ejecutables del chatbot RAG agéntico.

Cada tool encapsula una capacidad y devuelve contexto fundamentado en el corpus.
El orquestador (LangGraph) decide cuál invocar según la intención del usuario.
"""
from __future__ import annotations

from app.agent.tools.rag_tools import (
    consultar_base_conocimiento,
    consultar_documento_mas_reciente,
    consultar_inteligencia_comercial,
    consultar_requisitos_exportacion,
    consultar_tarifas_y_costos,
    presentar_documento_nuevo,
    resumir_contenido,
)
from app.agent.tools.chart_tools import graficar_precipitacion, graficar_temperatura_mar
from app.agent.tools.derivation_tools import derivar_solicitud_entidad
from app.agent.tools.handoff_tools import escalar_a_humano
from app.agent.tools.image_gen_tools import generar_imagen
from app.agent.tools.noaa_tools import consultar_datos_noaa
from app.agent.tools.weather_tools import consultar_clima

ALL_TOOLS = [
    consultar_base_conocimiento,
    consultar_requisitos_exportacion,
    consultar_tarifas_y_costos,
    consultar_inteligencia_comercial,
    resumir_contenido,
    presentar_documento_nuevo,
    consultar_documento_mas_reciente,
    consultar_clima,
    consultar_datos_noaa,
    graficar_temperatura_mar,
    graficar_precipitacion,
    generar_imagen,
    derivar_solicitud_entidad,
    escalar_a_humano,
]

__all__ = ["ALL_TOOLS"]
