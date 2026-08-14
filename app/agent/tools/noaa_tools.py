"""Tool de monitoreo climático NOAA: precipitación reciente en la estación
meteorológica más cercana a una zona productora de arándano, como señal
temprana adicional del Fenómeno de El Niño (FEN) en la costa peruana.

Sigue la convención de secretos del proyecto (ver weather_tools.py): el token
NO se hardcodea; se lee de `settings.noaa_api_token` (variable de entorno
NOAA_API_TOKEN / .env en local, o Secret Manager `noaa-api-token` inyectado
como env var en Cloud Run).

Fuente: Climate Data Online (CDO) API v2 del NCEI/NOAA
(https://www.ncei.noaa.gov/cdo-web/api/v2), autenticada con el header `token`.

Flujo en DOS pasos, igual que AccuWeather:
  1) Resolver la estación GHCND más cercana a la ubicación (endpoint /stations,
     búsqueda por caja geográfica alrededor del punto).
  2) Pedir observaciones diarias de precipitación de esa estación (endpoint
     /data) de los últimos días y resumirlas.

NOAA suele publicar datos de estaciones internacionales con varios días o
semanas de rezago (a veces sin datos recientes en absoluto); la tool reporta
el rango real de fechas con datos, no el rango solicitado, y lo informa con
claridad cuando no hay observaciones disponibles.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from functools import lru_cache

import httpx
from langchain_core.tools import tool

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

_BASE = "https://www.ncei.noaa.gov/cdo-web/api/v2"
_TIMEOUT = 15

# Detecta "lat,lon" (con o sin espacios/decimales/signo), igual que weather_tools.
_COORD_RE = re.compile(r"^\s*-?\d{1,3}(?:\.\d+)?\s*,\s*-?\d{1,3}(?:\.\d+)?\s*$")

# Coordenadas de referencia de las principales zonas productoras de arándano en
# Perú y ciudades costeras cercanas. La API de NOAA no ofrece geocodificación
# por nombre de lugar (solo por coordenadas/estación), así que se resuelve con
# esta tabla curada en vez de depender de un geocodificador externo.
_PERU_REGIONS: dict[str, tuple[float, float]] = {
    "trujillo": (-8.1116, -79.0290),
    "la libertad": (-8.1116, -79.0290),
    "viru": (-8.4167, -78.7500),
    "chao": (-8.5833, -78.7500),
    "chiclayo": (-6.7714, -79.8409),
    "lambayeque": (-6.7014, -79.9061),
    "olmos": (-5.9989, -79.7500),
    "piura": (-5.1945, -80.6328),
    "chincha": (-13.4103, -76.1308),
    "ica": (-14.0678, -75.7286),
    "lima": (-12.0464, -77.0428),
}


def _resolve_coords(ubicacion: str) -> tuple[float, float, str] | None:
    """Devuelve (lat, lon, nombre_legible) desde coordenadas o un nombre de zona
    productora/ciudad costera conocida."""
    q = (ubicacion or "").strip()
    if _COORD_RE.match(q):
        lat_s, lon_s = q.split(",")
        return float(lat_s), float(lon_s), q
    key = q.lower()
    for name, (lat, lon) in _PERU_REGIONS.items():
        if name in key or key in name:
            return lat, lon, ubicacion
    return None


@lru_cache(maxsize=64)
def _nearest_station(lat: float, lon: float) -> tuple[str, str, date] | None:
    """Busca la estación GHCND más cercana dentro de una caja de ~1.5° alrededor
    del punto y devuelve (station_id, nombre, maxdate).

    `maxdate` es la fecha del dato más reciente que NOAA tiene publicado para esa
    estación (a menudo con meses de rezago para estaciones fuera de EE. UU.): se
    usa como ancla de la ventana de consulta en vez de la fecha de hoy, porque
    pedir "los últimos N días desde hoy" casi siempre cae fuera de rango y
    devuelve vacío.
    """
    from app.agent.guardrails import sanitize_external_text

    token = settings.noaa_api_token
    if not token:
        return None
    margin = 0.75
    extent = f"{lat - margin},{lon - margin},{lat + margin},{lon + margin}"
    try:
        resp = httpx.get(
            f"{_BASE}/stations",
            headers={"token": token},
            params={"datasetid": "GHCND", "extent": extent, "limit": 25},
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        results = (resp.json() or {}).get("results") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("noaa_station_search_failed", error=str(exc))
        return None
    if not results:
        return None

    def _dist(st: dict) -> float:
        return (st.get("latitude", lat) - lat) ** 2 + (st.get("longitude", lon) - lon) ** 2

    nearest = min(results, key=_dist)
    station_id = nearest.get("id")
    if not station_id:
        return None
    # ASI01:2026 (Agent Goal Hijack vía contenido externo): el nombre de
    # estación es texto libre de la base de datos de NOAA, no un dato numérico
    # controlado; se neutraliza antes de que entre al loop ReAct como observación.
    station_name = sanitize_external_text(
        nearest.get("name", "estación cercana"), fallback="estación cercana")
    maxdate_s = nearest.get("maxdate")
    try:
        maxdate = date.fromisoformat(maxdate_s) if maxdate_s else date.today()
    except ValueError:
        maxdate = date.today()
    maxdate = min(maxdate, date.today())
    return station_id, station_name, maxdate


def _fetch_daily_precip(station_id: str, end: date, days: int = 120) -> list[dict]:
    """Observaciones diarias CRUDAS de precipitación (date/value tal como las
    devuelve NOAA), de los `days` días hasta `end` (inclusive).

    Extraído de `_recent_precipitation` para que también lo use el gráfico de
    precipitación (`app.agent.tools.chart_tools`), sin duplicar la llamada HTTP.
    Lista vacía si falla o no hay observaciones (ambos casos indistinguibles
    hacia el llamador: en ambos no hay señal que reportar).
    """
    token = settings.noaa_api_token
    start = end - timedelta(days=days)
    try:
        resp = httpx.get(
            f"{_BASE}/data",
            headers={"token": token},
            params={
                "datasetid": "GHCND",
                "stationid": station_id,
                "datatypeid": "PRCP",
                "units": "metric",
                "startdate": start.isoformat(),
                "enddate": end.isoformat(),
                "limit": 1000,
            },
            timeout=_TIMEOUT,
        )
        resp.raise_for_status()
        return (resp.json() or {}).get("results") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("noaa_data_failed", error=str(exc), station=station_id)
        return []


def _recent_precipitation(station_id: str, end: date, days: int = 120) -> dict:
    """Precipitación diaria (mm) de los `days` días hasta `end` (inclusive) con
    dato disponible.

    Devuelve dict con dias_con_dato/total_mm/desde/hasta; dias_con_dato=0 si la
    estación no tiene observaciones en la ventana (falla o vacío, sin distinguir
    ambos casos hacia el LLM: en ambos casos no hay señal que reportar).
    """
    results = _fetch_daily_precip(station_id, end, days)
    values = [r["value"] for r in results if r.get("value") is not None]
    if not values:
        return {"dias_con_dato": 0, "total_mm": 0.0, "desde": None, "hasta": None}
    fechas = sorted(r["date"][:10] for r in results if r.get("date"))
    return {
        "dias_con_dato": len(values),
        "total_mm": sum(values),
        "desde": fechas[0],
        "hasta": fechas[-1],
    }


def _format(nombre_lugar: str, estacion: str, resumen: dict) -> str:
    if resumen["dias_con_dato"] == 0:
        return (f"🌧️ NOAA no tiene observaciones de precipitación recientes para la "
                f"estación {estacion} (la más cercana a {nombre_lugar}). Es habitual "
                "en estaciones internacionales por el rezago de publicación de NOAA; "
                "intenta con otra zona cercana o vuelve a consultar más adelante.")
    total = resumen["total_mm"]
    partes = [
        f"🌧️ Precipitación NOAA cerca de {nombre_lugar} (estación {estacion}), "
        f"del {resumen['desde']} al {resumen['hasta']}: {total:.1f} mm acumulados "
        f"en {resumen['dias_con_dato']} día(s) con dato.",
    ]
    if total > 20:
        partes.append("Nivel notablemente alto para la costa peruana (normalmente "
                       "árida): posible señal de lluvias asociadas a El Niño costero, "
                       "con riesgo de exceso hídrico para la floración/cosecha del "
                       "arándano.")
    return " ".join(partes)


@tool
def consultar_datos_noaa(ubicacion: str) -> str:
    """Consulta la API de NOAA (Climate Data Online) para obtener la precipitación
    reciente registrada por la estación meteorológica más cercana a `ubicacion`.
    Úsala como señal temprana adicional del Fenómeno de El Niño (FEN) en la costa
    peruana: lluvias muy por encima de lo normal indican posible El Niño costero,
    con riesgo para la floración y cosecha del arándano. Acepta `ubicacion` como
    NOMBRE de una zona productora o ciudad costera conocida (p. ej. "Trujillo",
    "Piura", "Chiclayo", "Ica", "Lima") o como COORDENADAS "lat,lon"."""
    if not settings.noaa_api_token:
        return ("El servicio de datos NOAA no está configurado (falta el token de "
                "la API). Defínelo en la variable NOAA_API_TOKEN o en el secreto "
                "'noaa-api-token' de Secret Manager.")
    resolved = _resolve_coords(ubicacion)
    if not resolved:
        return (f"No reconozco «{ubicacion}» como zona productora de arándano o "
                "ciudad costera. Prueba con el nombre de una región (p. ej. "
                "«Trujillo», «Piura», «Chiclayo», «Ica») o con coordenadas «lat,lon».")
    lat, lon, nombre = resolved
    station = _nearest_station(lat, lon)
    if not station:
        return (f"No pude encontrar una estación NOAA cercana a «{ubicacion}» "
                "ahora mismo. Intenta de nuevo en unos minutos.")
    station_id, station_name, maxdate = station
    resumen = _recent_precipitation(station_id, end=maxdate)
    return _format(nombre, station_name, resumen)
