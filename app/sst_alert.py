"""Alerta de anomalía SST (#4) — señal temprana de El Niño Costero.

Un Cloud Scheduler invoca `/internal/sst-alert` (ver `app.main`) que corre
`run_sst_alert()`. El agente:
  1. Pide el **estado FEN vigente** al servicio satelital (`sst_monitor_base_url`,
     `GET /api/fen-status`) — la MISMA fuente que ya alimenta la insignia web
     (`web-sst-monitor/app.py`): la anomalía de TSM en la región oficial
     **Niño 1+2**, tomada de la anomalía diaria de Coral Reef Watch (NOAA) y, si
     falla, del índice semanal del CPC o del ICEN del IGP. Antes este módulo
     recalculaba su propia anomalía (SST de 3 puntos sueltos vía NOAA Blended
     5 km menos una climatología aproximada escrita a mano) — se retiró esa
     lógica para no tener dos fuentes de verdad distintas para el mismo
     fenómeno (ver discusión de credibilidad de fuentes).
  2. Traduce el nivel de 8 tramos (ICEN/ENFEN) a una severidad interna 0..4 —
     solo la fase CÁLIDA (El Niño costero) dispara esta alerta; Neutro y la fase
     Fría no cuentan como "riesgo" para este canal.
  3. Si el nivel es significativo **y sube** respecto al último estado difundido
     (Firestore), difunde una **plantilla aprobada** a los suscriptores.

El estado anti-repetición evita alertas diarias mientras la condición se mantiene:
solo se avisa cuando el nivel **escala**. Fail-open de punta a punta.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import httpx

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

# Traduce el nivel FEN/ICEN de 8 tramos (ver _ICEN_LEVELS en
# web-sst-monitor/app.py, la fuente única de esta clasificación) a la
# severidad 0..4 que usa esta alerta. Frío y Neutro no disparan: el riesgo que
# monitorea este canal es El Niño costero (fase cálida), no La Niña.
_LEVEL_SEVERITY = {
    "extraordinario": 4, "fuerte": 3, "moderado": 2, "debil": 1,
    "neutro": 0, "frio_debil": 0, "frio_moderado": 0, "frio_fuerte": 0,
}


@dataclass
class SSTReading:
    anomaly: float
    level: int          # severidad 0..4, ver _LEVEL_SEVERITY
    level_key: str       # nivel FEN/ICEN tal cual (p. ej. "moderado")
    label: str
    date: str
    source: str = ""


@dataclass
class SSTAlertResult:
    checked: bool = False
    anomaly: float = 0.0
    level: int = 0
    label: str = "normal"
    alerted: bool = False
    sent: int = 0
    failed: int = 0
    skipped_reason: str | None = None


def _fetch_fen_status() -> Optional[dict]:
    """Estado FEN vigente desde el propio servicio del sitio SST: la misma
    anomalía MUR L4/Niño 1+2 (con el ICEN del IGP como respaldo) que ya muestra
    la insignia web. None si el servicio no responde o no hay dato disponible."""
    base = (settings.sst_monitor_base_url or "").rstrip("/")
    if not base:
        logger.info("sst_monitor_not_configured")
        return None
    try:
        with httpx.Client(timeout=25.0) as client:
            r = client.get(f"{base}/api/fen-status")
            r.raise_for_status()
            data = r.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("fen_status_fetch_failed", error=str(exc))
        return None
    if not data.get("available"):
        return None
    return data


def compute_reading() -> Optional[SSTReading]:
    """Lee el estado FEN vigente y lo traduce a esta alerta. None si no hay dato."""
    data = _fetch_fen_status()
    if data is None:
        return None
    level_key = str(data.get("level", "neutro"))
    return SSTReading(
        anomaly=float(data.get("value", 0.0)),
        level=_LEVEL_SEVERITY.get(level_key, 0),
        level_key=level_key,
        label=str(data.get("label", "Neutro")),
        date=str(data.get("date", "")),
        source=str(data.get("source", "")),
    )


def is_significant(reading: SSTReading) -> bool:
    """¿Esta lectura merece alertar? ÚNICA definición para todos los canales.

    La usan `run_sst_alert` (difusión por WhatsApp) y `proactive._sst_nudge`
    (aviso del avatar web). Estaba duplicada literalmente en ambos sitios, de
    modo que tocar el umbral en uno dejaba el otro atrás y los dos canales
    acababan alertando por criterios distintos. Lo que SÍ difiere entre canales
    es la cadencia y el estado anti-repetición (Firestore global para WhatsApp,
    `localStorage` por navegador para el avatar), no el criterio.

    Solo la fase CÁLIDA dispara: `level` viene de `_LEVEL_SEVERITY`, donde
    Neutro y las fases frías valen 0.
    """
    return reading.anomaly >= settings.sst_anomaly_alert_c and reading.level >= 1


class SSTAlertStore:
    """La ALERTA VIGENTE: un único registro compartido por todos los canales.

    Antes cada canal decidía por su cuenta —WhatsApp solo al escalar de nivel, el
    avatar web mientras la anomalía fuera significativa—, así que el mismo día
    podían estar diciendo cosas distintas: el avatar anunciando "extraordinario"
    a cada visitante mientras por WhatsApp no salía nada. Ahora hay UN evento
    ("¿qué alerta está vigente?") y cada canal lo entrega una vez a su público:
    WhatsApp lo difunde, el avatar lo muestra a quien llegue después.

    El evento cambia cuando cambia el NIVEL, no cuando cambia el dato diario. Por
    eso `event_id` sirve de clave de deduplicación estable: el avatar dejó de
    repetir el aviso cada día al rotar la fecha del dato satelital.
    """

    def __init__(self, client=None) -> None:
        from google.cloud import firestore

        self._client = client or firestore.Client(project=settings.gcp_project_id)
        self._doc = (self._client
                     .collection(settings.firestore_sst_state_collection)
                     .document("current_alert"))

    def get_event(self) -> Optional[dict]:
        snap = self._doc.get()
        if not snap.exists:
            return None
        data = snap.to_dict() or {}
        return data if data.get("active") else None

    def save_event(self, event: dict) -> None:
        from google.cloud import firestore

        self._doc.set({**event, "active": True,
                       "updated_at": firestore.SERVER_TIMESTAMP})

    def mark_broadcast(self, event_id: str) -> None:
        from google.cloud import firestore

        self._doc.set({"event_id": event_id,
                       "broadcast_at": firestore.SERVER_TIMESTAMP}, merge=True)

    def clear_event(self) -> None:
        """La condición dejó de ser alertable: se cierra el evento vigente.

        No se borra el documento (sirve de traza); basta con desactivarlo para
        que una nueva entrada en zona de alerta genere un evento NUEVO y ambos
        canales vuelvan a avisar.
        """
        if self._doc.get().exists:
            self._doc.set({"active": False}, merge=True)


def current_alert(reading: SSTReading, store: Optional[SSTAlertStore] = None) -> Optional[dict]:
    """Evento de alerta vigente para esta lectura, creándolo si el nivel cambió.

    Devuelve None (y cierra el evento anterior) cuando la lectura ya no es
    alertable. Es la ÚNICA puerta por la que pasan los dos canales, de modo que
    ambos alertan del mismo hecho y con las mismas cifras.

    Sólo escribe en Firestore cuando cambia el nivel; en régimen normal es una
    lectura. Fail-open: si Firestore no responde se devuelve un evento efímero
    —el canal sigue avisando— pero sin memoria anti-repetición.
    """
    store = store or SSTAlertStore()
    if not is_significant(reading):
        try:
            store.clear_event()
        except Exception as exc:  # noqa: BLE001
            logger.warning("sst_event_clear_failed", error=str(exc))
        return None

    try:
        existing = store.get_event()
    except Exception as exc:  # noqa: BLE001
        logger.warning("sst_event_read_failed", error=str(exc))
        existing = None
    if existing and int(existing.get("level", -1)) == reading.level:
        return existing

    event = {
        "event_id": f"sst-{reading.level}-{reading.date or 'sin-fecha'}",
        "level": reading.level,
        "level_key": reading.level_key,
        "label": reading.label,
        "anomaly": reading.anomaly,
        "date": reading.date,
        "source": reading.source,
        "broadcast_at": None,
    }
    try:
        store.save_event(event)
    except Exception as exc:  # noqa: BLE001
        logger.warning("sst_event_save_failed", error=str(exc))
    logger.info("sst_event_opened", event_id=event["event_id"], level=reading.level)
    return event


def _broadcast(event: dict) -> tuple[int, int]:
    """Difunde el EVENTO (no la lectura en vivo): así el mensaje de WhatsApp cita
    exactamente las mismas cifras que el avatar web muestra para esa alerta."""
    from app.channels.twilio_whatsapp import send_whatsapp_template
    from app.user_registry import get_user_registry

    template_sid = settings.sst_alert_template_sid
    if not template_sid:
        logger.warning("sst_alert_no_template")
        return 0, 0
    recipients = get_user_registry().kb_summary_recipients()
    anomaly = float(event.get("anomaly", 0.0))
    anom = f"+{anomaly:.1f} °C" if anomaly >= 0 else f"{anomaly:.1f} °C"
    sent = failed = 0
    for u in recipients:
        to = u.whatsapp if u.whatsapp.startswith("whatsapp:") else f"whatsapp:{u.whatsapp}"
        try:
            ok = send_whatsapp_template(to, template_sid, {
                "1": anom, "2": str(event.get("label", "")),
                "3": str(event.get("date") or "reciente")})
        except Exception as exc:  # noqa: BLE001
            ok = False
            logger.warning("sst_alert_send_error", code=u.code, error=str(exc))
        sent += 1 if ok else 0
        failed += 0 if ok else 1
    logger.info("sst_alert_broadcast", sent=sent, failed=failed,
                anomaly=anomaly, level=event.get("level"))
    return sent, failed


def run_sst_alert(store: Optional[SSTAlertStore] = None) -> SSTAlertResult:
    """Difunde la alerta VIGENTE por WhatsApp, una sola vez por evento.

    El mismo evento lo muestra el avatar web (ver `proactive._sst_nudge`), así que
    ambos canales anuncian el mismo hecho con las mismas cifras.
    """
    result = SSTAlertResult()
    if not settings.sst_alert_enabled:
        result.skipped_reason = "alerta SST deshabilitada"
        return result
    reading = compute_reading()
    if reading is None:
        result.skipped_reason = "sin datos SST"
        return result
    result.checked = True
    result.anomaly, result.level, result.label = (
        reading.anomaly, reading.level, reading.label)

    store = store or SSTAlertStore()
    event = current_alert(reading, store=store)
    if event is None:
        result.skipped_reason = "sin anomalía significativa"
        return result
    if event.get("broadcast_at"):
        result.skipped_reason = "alerta ya difundida (el nivel no ha cambiado)"
        return result

    result.alerted = True
    result.sent, result.failed = _broadcast(event)
    # Marcar sólo si de verdad salió algo: si faltaba la plantilla o no había
    # destinatarios, `sent` es 0 y conviene reintentar mañana en vez de dar el
    # evento por difundido (fue el fallo silencioso del reenganche).
    if result.sent:
        try:
            store.mark_broadcast(event["event_id"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("sst_event_mark_failed", error=str(exc))
    else:
        logger.warning("sst_alert_nothing_sent", event_id=event.get("event_id"))
    return result
