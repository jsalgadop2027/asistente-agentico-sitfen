"""Confirmación DETERMINISTA de una derivación ofrecida (máquina de estados).

Por qué existe
--------------
Ofrecer canalizar un caso y ejecutarlo al recibir un "Sí" parecía algo que el LLM
podía manejar solo. No puede, y se rompió de dos formas distintas en producción:

1. **Callejón sin salida.** El agente ofrecía canalizar, el usuario respondía
   "Sí", y el LLM narraba el éxito sin invocar `derivar_solicitud_entidad`. La
   guardia antialucinación (`orchestrator._strip_unbacked_action_claim`) detectaba
   la mentira y pedía confirmación... que el usuario daba... y el ciclo se repetía.
   Cuatro veces seguidas en un caso real, sin que se canalizara nada.
2. **"Sí" amarrado a una solicitud vieja.** Tras una consulta no relacionada
   (costos portuarios), un "sí" disparó la derivación de un caso planteado nueve
   minutos antes. Las salvaguardas en el prompt no bastaron.

La raíz es la misma en ambos: la DECISIÓN de ejecutar una acción irreversible
estaba en manos del LLM. Aquí se saca de ahí. El LLM sigue redactando el
ofrecimiento (es lo que sabe hacer), pero quién ejecuta y sobre QUÉ caso lo
decide el código:

- Cuando la respuesta del agente es un ofrecimiento de canalizar, se guarda el
  caso pendiente (el último mensaje sustantivo del usuario, no un "Sí").
- Si el siguiente mensaje del usuario es una confirmación afirmativa, la
  derivación se ejecuta en código ANTES de invocar al LLM, sobre ese caso
  guardado. El LLM no participa en la decisión.
- Si el siguiente mensaje NO es una confirmación, el pendiente se descarta: el
  usuario cambió de tema y un "sí" posterior ya no puede resucitar el caso viejo.

Un pendiente caduca además por tiempo (`pending_derivation_ttl_minutes`), para que
un "Sí" de mañana no dispare el caso de hoy.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from google.cloud import firestore

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

# Ofrecimiento de canalizar: una PREGUNTA que propone la acción. Se exige el signo
# de interrogación para no confundirlo con una afirmación de hecho consumado
# ("He comunicado tu caso"), que es justo lo contrario y cubre la guardia
# antialucinación del orquestador.
#
# Ojo con el subjuntivo español, que cambia la raíz: comunicar -> comuni*qu*e,
# canalizar -> canali*c*e. Buscar "comunic"/"canaliz" NO encuentra las formas que
# el agente usa realmente al ofrecer ("¿quieres que le comunique...?"), y ese
# despiste dejaba sin detectar la mitad de los ofrecimientos reales.
_OFFER_VERB = r"(?:comuni(?:c|qu)|canali(?:c|z)|deriv|escal|env[íi]|transfer)\w*"

# "informar" va aparte y sólo con pronombre de tercera persona: "que LES informe
# a INDECI" es una derivación, pero "que TE informe sobre los requisitos" es
# ofrecer información y no debe disparar nada.
_OFFER_INFORM = r"les\s+inform\w*"

_OFFER_RE = re.compile(
    r"[¿?][^?¿]{0,200}?(?:"
    r"que\s+(?:se\s+|le\s+|les\s+|lo\s+|la\s+)?" + _OFFER_VERB
    + r"|que\s+" + _OFFER_INFORM
    # Forma directa en 1ª persona: "¿Lo canalizo a SENASA?".
    + r"|\b(?:lo\s+|la\s+|le\s+|les\s+)?"
      r"(?:canalizo|comunico|derivo|escalo|env[íi]o|transfiero)\b"
    r")[^?]{0,200}\?",
    re.IGNORECASE,
)


@dataclass
class Pending:
    caso: str
    created_at: datetime


class PendingDerivationStore:
    """Un documento por usuario con el caso ofrecido y aún sin confirmar."""

    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        self._client = client or firestore.Client(project=settings.gcp_project_id)
        self._collection = settings.firestore_pending_derivations_collection

    def _doc(self, user_id: str):
        return self._client.collection(self._collection).document(user_id)

    def get(self, user_id: str) -> Optional[Pending]:
        """Pendiente vigente, o None si no hay o ya caducó."""
        snap = self._doc(user_id).get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        caso = str(data.get("caso") or "").strip()
        created = data.get("created_at")
        if not caso or not isinstance(created, datetime):
            return None
        edad = datetime.now(timezone.utc) - created
        if edad > timedelta(minutes=settings.pending_derivation_ttl_minutes):
            logger.info("pending_derivation_expired", minutos=int(edad.total_seconds() // 60))
            return None
        return Pending(caso=caso, created_at=created)

    def set(self, user_id: str, caso: str) -> None:
        self._doc(user_id).set({
            "caso": caso[:2000],
            "created_at": datetime.now(timezone.utc),
        })

    def clear(self, user_id: str) -> None:
        self._doc(user_id).delete()


def is_offer(text: str) -> bool:
    """True si la respuesta del agente OFRECE canalizar el caso."""
    return bool(_OFFER_RE.search(text or ""))


def last_substantive_user_message(turns, current_text: str) -> str:
    """El caso real del usuario, saltando confirmaciones sueltas ("Sí", "OK").

    Sin esto, un ofrecimiento emitido justo después de un "Sí" guardaría "Sí"
    como caso a derivar.
    """
    from app.agent.guardrails import is_affirmative_confirmation

    if current_text and not is_affirmative_confirmation(current_text):
        return current_text
    for t in reversed(list(turns or [])):
        if getattr(t, "role", "") != "user":
            continue
        content = (getattr(t, "content", "") or "").strip()
        if content and not is_affirmative_confirmation(content):
            return content
    return ""
