"""Iniciativa proactiva del canal web (avatar 3D).

El avatar deja de ser puramente reactivo: consulta periódicamente si el agente
tiene algo que decir por iniciativa propia. `next_nudge()` decide el SIGUIENTE
aviso para una sesión, por prioridad:

  1. **Alerta SST (FEN)** — anomalía significativa del mar del norte (global).
  2. **Novedad de la base de conocimiento** — documento nuevo vectorizado (global).
  3. **Seguimiento personal** — una inquietud abierta del usuario, SOLO si la
     sesión está identificada con su código interno.

Rendimiento: el avatar sondea cada ~20 s **por visitante**. La lectura SST es una
llamada HTTP al servicio satelital (`GET /api/fen-status`) y el seguimiento es una
consulta a Firestore, así que ambos se cachean en proceso con TTL. El cliente
deduplica por `key`, de modo que cada aviso se anuncia una sola vez por sesión.

Fail-open de punta a punta: cualquier fallo devuelve "sin aviso", nunca rompe la
conversación.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


@dataclass
class Nudge:
    """Aviso proactivo listo para mostrar y locutar en el avatar."""
    kind: str          # "sst" | "kb" | "followup"
    key: str           # clave estable; el cliente la usa para no repetir
    text: str          # lo que se muestra en el chat (admite emoji)
    speak: str         # lo que se locuta (sin emoji ni markdown)
    source: str = ""   # solo kb: identificador del documento (para el ack)
    title: str = ""    # solo kb: título legible

    def as_dict(self) -> dict[str, Any]:
        return {
            "pending": True, "kind": self.kind, "key": self.key,
            "text": self.text, "speak": self.speak,
            "source": self.source, "title": self.title,
        }


# --- Cachés en proceso (TTL) --------------------------------------------------
_sst_cache: dict[str, Any] = {"ts": 0.0, "event": None}
_followup_cache: dict[str, tuple[float, Optional[dict]]] = {}


def _cached_sst_alert():
    """Evento de alerta SST vigente, con caché TTL.

    El avatar sondea cada ~20 s POR VISITANTE, así que sin caché esto sería una
    llamada HTTP al servicio satelital más una lectura de Firestore por sondeo.
    Se cachea el evento ya resuelto, no la lectura cruda: es el mismo registro
    que difunde WhatsApp (ver `sst_alert.current_alert`), de modo que ambos
    canales alertan del mismo hecho y con las mismas cifras.
    """
    now = time.time()
    if now - float(_sst_cache["ts"]) < settings.proactive_sst_ttl_seconds:
        return _sst_cache["event"]
    try:
        from app.sst_alert import compute_reading, current_alert

        reading = compute_reading()
        event = current_alert(reading) if reading is not None else None
    except Exception as exc:  # noqa: BLE001
        logger.warning("proactive_sst_failed", error=str(exc))
        event = None
    _sst_cache["ts"] = now
    _sst_cache["event"] = event
    return event


def _source_label(source: str) -> str:
    """Etiqueta corta y CORRECTA de la fuente del dato SST.

    `GET /api/fen-status` degrada en cascada entre TRES fuentes (ver
    `web-sst-monitor/app.py`): el índice semanal Niño 1+2 de la NOAA/CPC, la
    anomalía satelital diaria de Coral Reef Watch y, como red de seguridad, el
    ICEN oficial del IGP. El aviso decía "dato NOAA" fijo en el texto, así que
    con el respaldo activo le atribuía a la NOAA un índice que publica el IGP.
    Se deriva de `SSTReading.source`, que ya viaja en la lectura.
    """
    s = (source or "").upper()
    if "ICEN" in s or "IGP" in s:
        return "ICEN oficial del IGP"
    if "CPC" in s:
        return "índice semanal Niño 1+2 de la NOAA"
    if "CORAL REEF WATCH" in s or "CRW" in s:
        return "satélite NOAA Coral Reef Watch"
    if "MUR" in s or "GHRSST" in s:
        return "satélite GHRSST MUR"
    return "monitoreo satelital"


def _sst_nudge() -> Optional[Nudge]:
    """Aviso del avatar para la alerta SST VIGENTE (el mismo evento que WhatsApp).

    La clave es el `event_id`, no la fecha del dato: mientras el nivel no cambie
    es la misma alerta, así que el navegador (que deduplica por clave en
    `localStorage`) no la repite aunque el satélite publique un dato nuevo cada
    día. Cambia de nivel el FEN → evento nuevo → los dos canales vuelven a avisar.
    """
    if not settings.sst_alert_enabled:
        return None
    event = _cached_sst_alert()
    if not event:
        return None
    anomaly = float(event.get("anomaly", 0.0))
    label = str(event.get("label", ""))
    anom = f"+{anomaly:.1f}" if anomaly >= 0 else f"{anomaly:.1f}"
    fecha = str(event.get("date") or "reciente")
    fuente = _source_label(str(event.get("source", "")))
    return Nudge(
        kind="sst",
        key=str(event.get("event_id") or f"sst:{fecha}"),
        text=(f"⚠️ Señal temprana del Fenómeno de El Niño: la temperatura del mar "
              f"en el norte está {anom} °C sobre lo normal, un nivel {label} "
              f"({fuente}, dato de {fecha}). Conviene anticiparse. ¿Quieres que revisemos "
              f"qué medidas tomar para proteger tu cultivo?"),
        speak=(f"Atención: la temperatura del mar en el norte está {anom} grados "
               f"sobre lo normal, un nivel {label}. Conviene anticiparse. "
               f"¿Quieres que revisemos qué medidas tomar para proteger tu cultivo?"),
    )


def _kb_nudge() -> Optional[Nudge]:
    try:
        from app.kb_events import KBEventStore

        event = KBEventStore().latest_pending()
    except Exception as exc:  # noqa: BLE001
        logger.warning("proactive_kb_failed", error=str(exc))
        return None
    if not event:
        return None
    nombre = event.title or event.source
    return Nudge(
        kind="kb",
        key=f"kb:{event.source}",
        text=(f"📚 ¡Buenas noticias! Acabo de incorporar un documento nuevo a mi base "
              f"de conocimiento: «{nombre}». ¿Quieres que te presente su contenido? "
              f"Responde *Sí* y te lo muestro."),
        speak=(f"Buenas noticias. Acabo de incorporar un documento nuevo a mi base de "
               f"conocimiento: {nombre}. ¿Quieres que te presente su contenido?"),
        source=event.source,
        title=nombre,
    )


def _followup_nudge(session_id: str) -> Optional[Nudge]:
    """Retoma UNA inquietud abierta del usuario identificado (código interno)."""
    if not settings.concern_followup_enabled:
        return None
    from app.user_registry import looks_like_code

    if not looks_like_code(session_id):
        return None

    now = time.time()
    cached = _followup_cache.get(session_id)
    if cached and now - cached[0] < settings.proactive_followup_ttl_seconds:
        row = cached[1]
    else:
        try:
            from app.concerns import ConcernStore

            rows = ConcernStore().list_recent_open_for_user(
                session_id, days=settings.concern_followup_days, limit=1)
            row = rows[0] if rows else None
        except Exception as exc:  # noqa: BLE001
            logger.warning("proactive_followup_failed", error=str(exc))
            row = None
        _followup_cache[session_id] = (now, row)

    if not row:
        return None
    resumen = str(row.get("resumen") or "").strip()
    if not resumen:
        return None
    return Nudge(
        kind="followup",
        key=f"followup:{session_id}:{resumen[:40]}",
        text=(f"Por cierto, quería retomar algo que me comentaste: «{resumen}». "
              f"¿Cómo va eso? ¿Sigues necesitando ayuda?"),
        speak=(f"Por cierto, quería retomar algo que me comentaste: {resumen}. "
               f"¿Cómo va eso? ¿Sigues necesitando ayuda?"),
    )


def pending_nudges(session_id: str) -> list[Nudge]:
    """TODOS los avisos pendientes para la sesión, en orden de prioridad.

    Se devuelven todos (no solo el primero) porque el cliente deduplica por `key`:
    si solo se enviara el de mayor prioridad, una alerta ya anunciada lo ocuparía
    indefinidamente y los avisos de menor prioridad —como el seguimiento personal—
    nunca llegarían a darse. Cada fuente es fail-open por separado.
    """
    if not settings.proactive_web_enabled:
        return []
    out: list[Nudge] = []
    builders = (_sst_nudge, _kb_nudge, lambda: _followup_nudge(session_id))
    for build in builders:
        try:
            nudge = build()
        except Exception as exc:  # noqa: BLE001
            logger.warning("proactive_nudge_failed", error=str(exc))
            nudge = None
        if nudge is not None:
            out.append(nudge)
    return out


def next_nudge(session_id: str) -> Optional[Nudge]:
    """Aviso de mayor prioridad para la sesión, o None si no hay nada que decir."""
    nudges = pending_nudges(session_id)
    return nudges[0] if nudges else None
