"""Tool de clima: consulta AccuWeather (ubicación + condiciones actuales).

Sigue la convención de secretos del proyecto: la API key NO se hardcodea; se lee de
`settings.accuweather_api_key` (variable de entorno ACCUWEATHER_API_KEY / .env en
local, o Secret Manager en producción, igual que las credenciales de Twilio).

AccuWeather usa un flujo en DOS pasos:
  1) Resolver la 'location key' a partir del nombre de la ciudad/localidad.
  2) Pedir las condiciones actuales con esa location key.
La resolución de ubicación se cachea (lru_cache) para no agotar la cuota del plan
gratuito de AccuWeather (~50 peticiones/día).
"""
from __future__ import annotations

import re
from functools import lru_cache

import httpx
from langchain_core.tools import tool

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

_BASE = "https://dataservice.accuweather.com"
_TIMEOUT = 12

# Detecta "lat,lon" (con o sin espacios/decimales/signo) para decidir el endpoint.
_COORD_RE = re.compile(r"^\s*-?\d{1,3}(?:\.\d+)?\s*,\s*-?\d{1,3}(?:\.\d+)?\s*$")


def _nombre_legible(top: dict, fallback: str) -> str:
    from app.agent.guardrails import sanitize_external_text

    nombre = ", ".join(
        p for p in [
            top.get("LocalizedName"),
            (top.get("AdministrativeArea") or {}).get("LocalizedName"),
            (top.get("Country") or {}).get("LocalizedName"),
        ] if p
    )
    # ASI01:2026 (Agent Goal Hijack vía contenido externo que el agente lee):
    # el nombre de ubicación viene de la base de datos de AccuWeather, no del
    # usuario directamente, pero es texto libre que entra al loop ReAct.
    return sanitize_external_text(nombre, fallback=fallback)


@lru_cache(maxsize=128)
def _resolve_location(query: str) -> tuple[str, str] | None:
    """Devuelve (location_key, nombre_legible) de una ciudad, o None si no se halla."""
    key = settings.accuweather_api_key
    if not key:
        return None
    try:
        resp = httpx.get(
            f"{_BASE}/locations/v1/cities/search",
            params={"apikey": key, "q": query, "language": "es-pe"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("accuweather_location_failed", error=str(exc))
        return None
    if not data:
        return None
    top = data[0]
    return top.get("Key"), _nombre_legible(top, query)


@lru_cache(maxsize=128)
def _resolve_geoposition(coords: str) -> tuple[str, str] | None:
    """Resuelve (location_key, nombre) desde "lat,lon" vía el endpoint geoposition.

    A diferencia de la búsqueda por ciudad, este endpoint devuelve un único objeto
    (no una lista). Se usa cuando el usuario comparte su ubicación por WhatsApp.
    """
    key = settings.accuweather_api_key
    if not key:
        return None
    try:
        resp = httpx.get(
            f"{_BASE}/locations/v1/cities/geoposition/search",
            params={"apikey": key, "q": coords, "language": "es-pe"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("accuweather_geoposition_failed", error=str(exc))
        return None
    if not data:
        return None
    top = data[0] if isinstance(data, list) else data
    return top.get("Key"), _nombre_legible(top, coords)


def _current_conditions(location_key: str) -> dict | None:
    """Condiciones actuales (details=true para humedad, sensación y viento)."""
    try:
        resp = httpx.get(
            f"{_BASE}/currentconditions/v1/{location_key}",
            params={"apikey": settings.accuweather_api_key,
                    "language": "es-pe", "details": "true"},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("accuweather_current_failed", error=str(exc))
        return None
    return data[0] if data else None


def _format(nombre: str, cond: dict) -> str:
    from app.agent.guardrails import sanitize_external_text

    # ASI01:2026: WeatherText es texto libre de AccuWeather, no un dato numérico
    # controlado; se neutraliza igual que el nombre de ubicación (ver arriba).
    texto = sanitize_external_text(cond.get("WeatherText", "—"), fallback="—")
    temp = (cond.get("Temperature") or {}).get("Metric", {}).get("Value")
    sensacion = (cond.get("RealFeelTemperature") or {}).get("Metric", {}).get("Value")
    humedad = cond.get("RelativeHumidity")
    viento = ((cond.get("Wind") or {}).get("Speed") or {}).get("Metric", {}).get("Value")

    partes = [f"🌤️ Clima en {nombre}: {texto}."]
    if temp is not None:
        sens = f" (sensación {sensacion} °C)" if sensacion is not None else ""
        partes.append(f"Temperatura: {temp} °C{sens}.")
    if humedad is not None:
        partes.append(f"Humedad: {humedad}%.")
    if viento is not None:
        partes.append(f"Viento: {viento} km/h.")
    return " ".join(partes)


@tool
def consultar_clima(ubicacion: str) -> str:
    """Devuelve el clima actual de una ubicación consultando AccuWeather.
    Acepta `ubicacion` como NOMBRE de ciudad/localidad (p. ej. "Trujillo",
    "La Libertad") o como COORDENADAS en formato "lat,lon" (p. ej.
    "-8.111,-79.028"); usa las coordenadas cuando el usuario comparta su ubicación
    por WhatsApp. Reporta temperatura, sensación térmica, humedad y viento, que
    afectan el cultivo y la cosecha del arándano."""
    if not settings.accuweather_api_key:
        return ("El servicio de clima no está configurado (falta la API key de "
                "AccuWeather). Defínela en la variable ACCUWEATHER_API_KEY.")
    q = (ubicacion or "").strip()
    if _COORD_RE.match(q):
        loc = _resolve_geoposition(q.replace(" ", ""))
    else:
        loc = _resolve_location(q)
    if not loc:
        return (f"No pude encontrar la ubicación «{ubicacion}». Prueba con el nombre "
                "de una ciudad, p. ej. «Trujillo, Perú».")
    location_key, nombre = loc
    cond = _current_conditions(location_key)
    if not cond:
        return (f"No pude obtener el clima de {nombre} ahora mismo. Intenta de nuevo "
                "en unos minutos.")
    return _format(nombre, cond)
