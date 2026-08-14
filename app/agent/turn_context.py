"""Contexto de la petición en curso, propagado del orquestador a las tools.

Algunas tools (p. ej. la derivación de solicitudes a entidades públicas) necesitan
saber QUIÉN es el usuario del turno para adjuntar sus datos de contacto. El id de
sesión no viaja como argumento de la tool (el LLM no debe manejarlo), así que se
propaga con un `contextvar` — seguro entre peticiones concurrentes: cada invocación
tiene su propio contexto (mismo patrón que `app.agent.translation`).

`current_user_text` guarda el texto SANEADO (ya normalizado por los guardrails) del
turno actual del usuario. Sirve como ancla determinística para tools de alta
agencia (acciones consecuentes/irreversibles, p. ej. enviar un correo a una entidad
pública): en vez de confiar en que el LLM decidió correctamente que hubo
confirmación explícita, la tool verifica en CÓDIGO que el texto real del usuario en
este turno es una confirmación afirmativa (ver
`app.agent.guardrails.is_affirmative_confirmation`). Mitiga OWASP LLM06 (Excessive
Agency): una inyección de prompt no puede disparar la acción sin que el usuario
realmente haya escrito una confirmación.

Nota: este mecanismo solo sirve para propagar valores DEL orquestador HACIA las
tools (se fijan antes de `agent.invoke()`). No sirve en sentido inverso — una
tool que hiciera `ContextVar.set(...)` durante su ejecución no lo dejaría visible
después de que `agent.invoke()` retorna: LangGraph ejecuta cada tool call en un
hilo del pool con `contextvars.copy_context()` propio (`ToolNode._func`), así que
la mutación queda aislada en esa copia. Por eso la URL de un gráfico generado por
una tool (`app.agent.tools.chart_tools`) NO se propaga por aquí, sino con el
mismo marcador determinista que las fuentes RAG (ver
`app.agent.translation.extract_chart_url`).
"""
from __future__ import annotations

import contextvars
from typing import Optional

_current_user_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_user_id", default=None)
_current_user_text: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "current_user_text", default=None)
# Medio de entrada del turno actual ("texto" | "voz" | "imagen"). El canal
# WhatsApp lo fija a partir de si el mensaje entrante era una nota de voz
# (transcrita) o una imagen (descrita); por defecto "texto" para los demás
# canales (web, CLI). Lo usa `derivar_solicitud_entidad` para que la
# derivación (y el correo a la entidad) quede etiquetada con el canal real de
# origen, en vez de perderse tras la transcripción/descripción a texto plano.
_current_medio: contextvars.ContextVar[str] = contextvars.ContextVar(
    "current_medio", default="texto")


def set_current_user_id(user_id: Optional[str]) -> None:
    _current_user_id.set(user_id)


def get_current_user_id() -> Optional[str]:
    return _current_user_id.get()


def set_current_user_text(text: Optional[str]) -> None:
    _current_user_text.set(text)


def get_current_user_text() -> Optional[str]:
    return _current_user_text.get()


def set_current_medio(medio: str) -> None:
    _current_medio.set(medio or "texto")


def get_current_medio() -> str:
    return _current_medio.get()
