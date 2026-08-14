"""Admin UI (Streamlit): host de navegación del panel de administración.

Define el menú lateral con tres secciones (títulos explícitos vía st.navigation):
  - «Ingesta de contenidos» (admin_ui/_ingesta.py): carga de documentos y URLs
    al corpus (RAG) y notificación de novedades.
  - «Control de Usuarios» (admin_ui/_control_usuarios.py): registro y control de
    usuarios finales y de su sesión individual de WhatsApp.
  - «Atenciones Normales» (admin_ui/_atenciones.py): CADA consulta de WhatsApp
    que el asistente resolvió por sí mismo, sin derivar a una entidad pública,
    con foco en las consultas recurrentes de un mismo usuario (colección
    Firestore `attentions`, cruzada con `user_concerns` y `derivations`).
  - «Estadísticas de Derivaciones» (admin_ui/_derivaciones.py): volumen, entidad
    de destino, urgencia y éxito de envío de las canalizaciones de casos de
    ciudadanos a entidades públicas (colección Firestore `derivations`).

Entrypoint estable (no renombrar: lo usa Dockerfile.admin).
Ejecutar local:  streamlit run admin_ui/app.py
"""
from __future__ import annotations

import os
import sys

# admin_ui/ queda en sys.path al ejecutar este script; como el archivo se llama
# app.py, tapaba al paquete 'app' del proyecto. Insertamos la raíz primero para que
# 'app.*' resuelva al paquete. La raíz es un nivel arriba de admin_ui/.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st

# Única llamada a set_page_config de toda la app (las secciones no la repiten).
# El icono NO usa 🫐 (arándano, U+1FAD0) pese a ser el emoji obvio para el dominio:
# es Emoji 13.0 (2020), el más reciente de todo el repo, y en la pestaña del
# navegador se veía como glifo roto. 🍇 es Emoji 1.0 (2015) — no hay plataforma en
# uso que no lo tenga— y mantiene la identidad frutal del panel. Mismo criterio en
# web/index.html, web/flujo.html y desktop/renderer/index.html.
st.set_page_config(page_title="Admin · Chatbot Arándano", page_icon="🍇", layout="centered")

_HERE = os.path.dirname(os.path.abspath(__file__))

_paginas = [
    st.Page(os.path.join(_HERE, "_ingesta.py"), title="Ingesta de contenidos",
            icon="📥", default=True),
    st.Page(os.path.join(_HERE, "_control_usuarios.py"), title="Control de Usuarios",
            icon="👤"),
    st.Page(os.path.join(_HERE, "_atenciones.py"), title="Atenciones Normales",
            icon="💬"),
    st.Page(os.path.join(_HERE, "_derivaciones.py"), title="Estadísticas de Derivaciones",
            icon="📊"),
]

st.navigation(_paginas).run()

# Crédito de autoría, visible en TODAS las páginas del panel (misma firma que el
# avatar web, el portal SST y la app móvil).
st.sidebar.divider()
st.sidebar.markdown(
    "<div style='text-align:center;font-size:.85rem;opacity:.75'>"
    "Desarrollado por el <b>Ing. Julio Salgado</b></div>",
    unsafe_allow_html=True,
)
