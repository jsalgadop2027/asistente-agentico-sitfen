"""Captura y almacenamiento de inquietudes del usuario (#3).

Tras cada mensaje del usuario, un clasificador Flash determina si expresa un
"punto de dolor" accionable: **reclamo, pedido, sugerencia o recomendación**. Si
es relevante, se guarda en Firestore (colección `user_concerns`) para alimentar
el informe diario (#8, ver `app.daily_report`) y el reporte de atenciones
normales del Admin UI (`admin_ui/_atenciones.py`, cruzado contra `derivations`
para distinguir lo que el asistente resolvió por sí mismo de lo que canalizó a
una entidad pública).

Diseño:
  - **Fire-and-forget:** `capture_concern_async` lanza un hilo daemon; nunca añade
    latencia perceptible ni rompe la respuesta al usuario (fail-open).
  - **Minimización de PII:** se redacta el mensaje antes de persistir (igual que
    `app.agent.memory`), y se guarda además un resumen breve generado por el LLM.
  - **Sin índices compuestos:** las consultas por día usan un campo `day`
    (fecha local de Lima) con filtro de igualdad; el orden se hace en memoria.
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from google.cloud import firestore

from app.agent.guardrails import redact_pii
from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

# Tipos accionables que sí se registran (todo lo demás se descarta como "ninguno").
# "preocupacion" cubre el punto de dolor emocional (temor, inquietud, indecisión,
# desorientación) frente a los eventos que enfrenta el usuario; se canaliza al Estado.
CONCERN_TYPES = ("reclamo", "pedido", "sugerencia", "recomendacion", "preocupacion")

_CLASSIFY_PROMPT = (
    "Eres un analista de atención al cliente de un asistente de inteligencia "
    "comercial del arándano peruano (contexto: Fenómeno de El Niño, MYPES "
    "agrícolas del norte del Perú). Analiza el MENSAJE del usuario en dos ejes.\n\n"
    "1) TIPO (punto de dolor o interés accionable), UNA sola categoría:\n"
    "- reclamo: queja, molestia, problema, falla o insatisfacción.\n"
    "- pedido: solicitud concreta (un dato, una gestión, una funcionalidad).\n"
    "- sugerencia: propuesta de mejora del servicio.\n"
    "- recomendacion: consejo o recomendación que ofrece el usuario.\n"
    "- preocupacion: preocupación, temor, inquietud, indecisión o desorientación "
    "del usuario frente a los eventos que enfrenta (clima/FEN, cultivo, negocio, "
    "sustento), aunque no formule un pedido concreto.\n"
    "Si el mensaje NO es ninguno (saludo, agradecimiento, charla o una simple "
    "pregunta informativa), usa el tipo \"ninguno\".\n\n"
    "2) OBJETIVO: si el usuario expresa o actualiza una META u OBJETIVO de negocio "
    "(p. ej. \"quiero exportar arándano a China\", \"busco certificarme en "
    "GlobalGAP este año\", \"quiero aumentar mi producción\"), resúmela en UNA frase "
    "breve en español. Si NO declara ninguna meta, deja la cadena vacía.\n\n"
    "Devuelve EXCLUSIVAMENTE un JSON válido, sin texto adicional ni ```:\n"
    "{{\"tipo\": \"reclamo|pedido|sugerencia|recomendacion|ninguno\", "
    "\"resumen\": \"<frase breve del punto de dolor, vacía si ninguno>\", "
    "\"objetivo\": \"<meta de negocio en una frase, vacía si no aplica>\"}}\n\n"
    "MENSAJE:\n{message}"
)


def lima_day_str(when: Optional[datetime] = None) -> str:
    """Fecha (YYYY-MM-DD) en hora de Lima. Perú no tiene DST → offset fijo UTC-5."""
    now = when or datetime.now(timezone.utc)
    local = now.astimezone(timezone.utc) + timedelta(hours=settings.lima_utc_offset_hours)
    return local.date().isoformat()


@dataclass
class Concern:
    user_id: str
    tipo: str
    resumen: str
    message: str
    day: str


@dataclass
class Classification:
    """Resultado del análisis de un mensaje: inquietud accionable y/o objetivo.

    `tipo` es None si el mensaje no es una inquietud accionable; `objetivo` es ""
    si el usuario no declara ni actualiza una meta de negocio. Ambos ejes son
    independientes: un mensaje puede traer solo objetivo, solo inquietud, ambos o
    ninguno (en cuyo caso `classify_message` devuelve None).
    """
    tipo: Optional[str]
    resumen: str
    objetivo: str = ""


def _parse_classification(raw: str) -> Optional[Classification]:
    """Extrae la clasificación del JSON del LLM.

    Devuelve None solo si el JSON es inválido o si no hay NADA útil (ni inquietud
    accionable ni objetivo). `tipo` queda en None cuando no es una inquietud.
    """
    text = (raw or "").strip()
    if text.startswith("```"):
        # Quita cercos de código ```json ... ```
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    tipo_raw = str(data.get("tipo", "")).strip().lower()
    tipo = tipo_raw if tipo_raw in CONCERN_TYPES else None
    resumen = str(data.get("resumen", "")).strip()
    objetivo = str(data.get("objetivo", "")).strip()
    if tipo is None and not objetivo:
        return None
    return Classification(tipo=tipo, resumen=resumen, objetivo=objetivo)


def classify_message(message: str) -> Optional[Classification]:
    """Clasifica el mensaje con Flash. Devuelve `Classification` o None."""
    from app.agent.models import invoke_with_failover

    # Flash por defecto (determinista), con failover de ubicación: si el pool de
    # capacidad saturaba, la inquietud se perdía y la atención no aparecía en el
    # Admin UI aunque el usuario SÍ hubiera recibido su respuesta.
    resp = invoke_with_failover(
        _CLASSIFY_PROMPT.format(message=message[:1500]), temperature=0.0)
    content = getattr(resp, "content", "") or ""
    if isinstance(content, list):  # Gemini puede devolver bloques
        content = " ".join(
            b.get("text", "") for b in content if isinstance(b, dict)
        )
    return _parse_classification(str(content))


class ConcernStore:
    def __init__(self, client: Optional[firestore.Client] = None) -> None:
        self._client = client or firestore.Client(project=settings.gcp_project_id)
        self._collection = settings.firestore_concerns_collection

    def add(self, concern: Concern) -> None:
        self._client.collection(self._collection).add({
            "user_id": concern.user_id,
            "tipo": concern.tipo,
            "resumen": concern.resumen,
            "message": concern.message,
            "day": concern.day,
            "created_at": firestore.SERVER_TIMESTAMP,
        })

    def list_recent(self, limit: int = 2000) -> list[dict]:
        """Inquietudes más recientes, para el reporte de atenciones del Admin UI
        (ver `admin_ui/_atenciones.py`). Sin filtro de fecha en la consulta (evita
        requerir un índice compuesto): el recorte por rango se hace en memoria,
        igual que `DerivationStore.list_recent`."""
        docs = (self._client.collection(self._collection)
                .order_by("created_at", direction=firestore.Query.DESCENDING)
                .limit(limit).stream())
        return [d.to_dict() or {} for d in docs]

    def list_for_day(self, day: str) -> list[dict]:
        """Inquietudes de un día (fecha Lima). Filtro de igualdad; orden en memoria."""
        from google.cloud.firestore_v1.base_query import FieldFilter

        docs = (self._client.collection(self._collection)
                .where(filter=FieldFilter("day", "==", day)).stream())
        rows = [d.to_dict() or {} for d in docs]
        rows.sort(key=lambda r: r.get("created_at") or datetime.min.replace(
            tzinfo=timezone.utc))
        return rows

    def list_recent_open_for_user(
        self, user_id: str, *, days: int, limit: int,
        types: tuple[str, ...] = ("reclamo", "pedido", "preocupacion"),
    ) -> list[dict]:
        """Inquietudes 'abiertas' recientes de un usuario para el seguimiento.

        Devuelve las inquietudes accionables (por defecto reclamo/pedido/preocupación)
        del usuario en los últimos `days` días, más recientes primero. Usa un ÚNICO
        filtro de igualdad (`user_id`, auto-indexado) y filtra recencia/tipo en
        memoria para no requerir un índice compuesto.

        Se omiten las marcadas con `seguimiento_cerrado`: cerrar una inquietud
        apaga SOLO el seguimiento proactivo del avatar, sin borrar el dato — el
        informe diario (`list_for_day`) y las atenciones del Admin UI
        (`list_recent`) la siguen viendo. Es la salida para limpiar avisos
        pendientes sin perder el registro del punto de dolor del ciudadano
        (`scripts/close_concern_followups.py` lo hace en bloque).
        """
        from google.cloud.firestore_v1.base_query import FieldFilter

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        docs = (self._client.collection(self._collection)
                .where(filter=FieldFilter("user_id", "==", user_id)).stream())
        rows: list[dict] = []
        for d in docs:
            r = d.to_dict() or {}
            if r.get("tipo") not in types or r.get("seguimiento_cerrado"):
                continue
            created = r.get("created_at")
            if isinstance(created, datetime):
                c = created if created.tzinfo else created.replace(tzinfo=timezone.utc)
                if c < cutoff:
                    continue
            rows.append(r)
        rows.sort(
            key=lambda r: r.get("created_at") or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        return rows[:limit]


def record_concern(user_id: str, message: str,
                   store: Optional[ConcernStore] = None,
                   goal_store: Any = None) -> Optional[Concern]:
    """Clasifica y persiste inquietud y/o objetivo (síncrono). Fail-open: nunca lanza.

    Un mismo mensaje puede aportar una inquietud accionable, un objetivo de negocio,
    ambos o ninguno. El objetivo solo se guarda para usuarios registrados (código
    interno estable) vía `app.user_goals`. Devuelve la `Concern` si hubo inquietud.
    """
    try:
        if len(message.strip()) < settings.concern_min_chars:
            return None
        result = classify_message(message)
        if result is None:
            return None

        # Objetivo de negocio (#B): solo para usuarios con código interno estable.
        if (settings.goal_tracking_enabled and result.objetivo):
            from app.user_registry import looks_like_code

            if looks_like_code(user_id):
                from app.user_goals import record_goal

                record_goal(user_id, result.objetivo, store=goal_store)

        if result.tipo is None:
            return None  # había objetivo pero no una inquietud accionable

        concern = Concern(
            user_id=user_id,
            tipo=result.tipo,
            resumen=result.resumen or redact_pii(message)[:200],
            message=redact_pii(message)[:1000],
            day=lima_day_str(),
        )
        (store or ConcernStore()).add(concern)
        logger.info("concern_recorded", user_id=redact_pii(user_id), tipo=result.tipo)
        return concern
    except Exception as exc:  # noqa: BLE001
        logger.warning("concern_capture_failed", error=str(exc))
        return None


def capture_concern_async(user_id: str, message: str) -> None:
    """Lanza la captura en un hilo daemon (no bloquea la respuesta al usuario)."""
    if not settings.concern_capture_enabled:
        return
    if len(message.strip()) < settings.concern_min_chars:
        return
    threading.Thread(
        target=record_concern, args=(user_id, message), daemon=True,
    ).start()
