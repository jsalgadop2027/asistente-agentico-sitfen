"""Persistencia de memoria conversacional en Firestore (corto + largo plazo).

Cumple "Persistencia de la memoria con Firestore" y soporta concurrencia
multiusuario (cada usuario = un documento de conversación).

Dos capas por usuario, en el MISMO documento (colección `conversations`):
  - Corto plazo: `history` = ventana móvil de las últimas `memory_max_turns`
    entradas (user+assistant), literales, para continuidad inmediata.
  - Largo plazo (resumen progresivo): `summary` = resumen condensado de TODO lo
    que ya salió de la ventana. Cuando el historial rebasa la ventana, el exceso
    se pliega en el resumen con el LLM (no se pierde el contexto antiguo).

La memoria semántica de largo plazo (recuerdos recuperables por similitud) vive
aparte, en `app.agent.semantic_memory`.

Cumplimiento de datos (Ley 29733 / GDPR):
  - Se redacta PII antes de persistir (minimización).
  - TTL lógico vía 'updated_at' (se puede purgar con política de retención).
  - `forget(user_id)` implementa el derecho de supresión.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from google.cloud import firestore

from app.agent.guardrails import redact_pii
from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

# Compatibilidad: valor por defecto histórico. La ventana real se lee de settings.
MAX_TURNS = 20

_SUMMARY_PROMPT = (
    "Eres un asistente que mantiene una memoria de largo plazo de un usuario del "
    "chatbot de inteligencia comercial del arándano peruano. Actualiza el RESUMEN "
    "previo integrando los intercambios ANTIGUOS que se listan (los que salen de la "
    "ventana reciente). Conserva hechos duraderos y útiles para futuras respuestas: "
    "quién es el usuario, su rubro/negocio, intereses, preguntas recurrentes, datos "
    "que compartió y decisiones/preferencias. Sé conciso (máximo {max_words} "
    "palabras), en español, en prosa. Devuelve SOLO el resumen actualizado.\n\n"
    "RESUMEN PREVIO:\n{summary}\n\nINTERCAMBIOS ANTIGUOS A INTEGRAR:\n{overflow}"
)


@dataclass
class Turn:
    role: str  # "user" | "assistant"
    content: str


def _max_turns() -> int:
    return max(2, settings.memory_max_turns or MAX_TURNS)


class ConversationMemory:
    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        self._client = client or firestore.Client(project=settings.gcp_project_id)
        self._collection = settings.firestore_memory_collection

    def _ref(self, user_id: str):
        return self._client.collection(self._collection).document(user_id)

    def load(self, user_id: str) -> list[Turn]:
        snap = self._ref(user_id).get()
        if not snap.exists:
            return []
        history = (snap.to_dict() or {}).get("history", [])
        return [Turn(role=h["role"], content=h["content"]) for h in history]

    def load_summary(self, user_id: str) -> str:
        """Resumen progresivo de largo plazo (vacío si no hay)."""
        snap = self._ref(user_id).get()
        if not snap.exists:
            return ""
        return (snap.to_dict() or {}).get("summary", "") or ""

    def load_state(self, user_id: str) -> tuple[list[Turn], str]:
        """Devuelve (historial reciente, resumen de largo plazo) en una sola lectura."""
        snap = self._ref(user_id).get()
        if not snap.exists:
            return [], ""
        data = snap.to_dict() or {}
        history = [Turn(role=h["role"], content=h["content"])
                   for h in data.get("history", [])]
        return history, data.get("summary", "") or ""

    def append(self, user_id: str, user_msg: str, assistant_msg: str) -> None:
        """Añade un turno y mantiene la ventana + el resumen progresivo.

        Si tras añadir el turno el historial rebasa la ventana, el exceso más
        antiguo se condensa en el `summary` (largo plazo) antes de recortarlo.
        """
        history, summary = self.load_state(user_id)
        history.append(Turn("user", redact_pii(user_msg)))
        history.append(Turn("assistant", assistant_msg))

        window = _max_turns()
        if len(history) > window:
            overflow = history[:-window]
            history = history[-window:]
            if settings.ltm_enabled and settings.ltm_summary_enabled:
                summary = self._summarize(summary, overflow)

        self._ref(user_id).set(
            {
                "history": [{"role": t.role, "content": t.content} for t in history],
                "summary": summary,
                "updated_at": firestore.SERVER_TIMESTAMP,
            },
            merge=True,
        )

    def _summarize(self, summary: str, overflow: list[Turn]) -> str:
        """Pliega los turnos antiguos en el resumen de largo plazo con el LLM.

        Fail-open: ante cualquier error mantiene el resumen previo (no pierde lo
        ya acumulado) y no interrumpe el flujo de respuesta.
        """
        if not overflow:
            return summary
        lines = "\n".join(
            f"{'Usuario' if t.role == 'user' else 'Asistente'}: {t.content}"
            for t in overflow
        )
        try:
            from app.agent.guardrails import detect_injection
            from app.agent.models import invoke_with_failover

            prompt = _SUMMARY_PROMPT.format(
                max_words=settings.ltm_summary_max_words,
                summary=summary or "(sin resumen previo)",
                overflow=lines,
            )
            resp = invoke_with_failover(prompt, temperature=0.2)
            content = getattr(resp, "content", "") or ""
            text = content.strip() if isinstance(content, str) else str(content).strip()
            if not text:
                return summary
            # ASI06:2026 (Memory & Context Poisoning): este resumen se reinyecta
            # como contexto CONFIABLE en el system prompt de TODOS los turnos
            # futuros (`orchestrator._augment_with_ltm`), sin volver a pasar por
            # `check_input`. `check_input` ya bloquea los turnos con inyección
            # detectable antes de que lleguen a `append()`, pero el propio LLM
            # resumidor podría, ante un intento más sutil que evadió esa
            # detección, terminar redactando una instrucción persistente. Si el
            # resumen recién generado matchea el mismo detector, se descarta y
            # se conserva el previo: preferible un resumen desactualizado a uno
            # potencialmente contaminado.
            if detect_injection(text):
                logger.warning("ltm_summary_injection_blocked")
                return summary
            return text
        except Exception as exc:  # noqa: BLE001
            logger.warning("ltm_summarize_failed", error=str(exc))
            return summary

    def forget(self, user_id: str) -> None:
        """Derecho al olvido (Ley 29733 / GDPR): borra historial y resumen."""
        self._ref(user_id).delete()
        logger.info("memory_forgotten", user_id=redact_pii(user_id))

    @staticmethod
    def as_prompt(history: list[Turn]) -> str:
        if not history:
            return ""
        lines = [f"{'Usuario' if t.role == 'user' else 'Asistente'}: {t.content}"
                 for t in history]
        return "Historial reciente de la conversación:\n" + "\n".join(lines)
