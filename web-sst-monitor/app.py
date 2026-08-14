"""Backend del Monitor SST — fuente de la verdad: NOAA.

Sirve la página estática (index.html) y expone una API mínima que consulta, del
lado del servidor, el producto **NOAA CoastWatch Blended 5 km Global SST (NRT)**
vía ERDDAP. El navegador nunca habla con NOAA directamente (NOAA no envía CORS):
solo llama a /api/* del mismo origen.

Endpoints:
  GET /api/sst?lat&lon            -> SST actual (última) en la celda de mar más cercana
  GET /api/series?lat&lon&days    -> serie diaria observada (para el gráfico)
  GET /api/fen-status             -> nivel de alerta FEN vigente (índice semanal
                                      Niño 1+2 del CPC; anomalía diaria de Coral
                                      Reef Watch y ICEN del IGP como respaldos)
  GET /api/fen-levels             -> tabla estática de umbrales de clasificación FEN
  GET /health
"""
from __future__ import annotations

import csv
import datetime
import logging
import math
import os
import re
import threading
import urllib.parse
from pathlib import Path
from time import monotonic

import httpx
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse, Response

HERE = Path(__file__).parent
# NOAA CoastWatch ERDDAP — blended día/noche 5 km, casi-tiempo-real (~1–2 d latencia).
ERDDAP = "https://coastwatch.noaa.gov/erddap/griddap/noaacwBLENDEDCsstDaily.json"
SOURCE = "NOAA CoastWatch — Blended 5 km Global SST (NRT) · analysed_sst"
# ERDDAP rechaza (403) User-Agents de librería genéricos; identificarse es de buena educación.
UA = "arandano-sst-monitor/1.0 (UTEC capstone; contact jsalgadop2027@gmail.com)"

app = FastAPI(title="Monitor SST — fuente NOAA", docs_url=None, redoc_url=None)
_client = httpx.Client(headers={"User-Agent": UA}, timeout=25.0)
# La insignia del FEN degrada en cascada entre fuentes y es fail-open: sin log,
# una fuente caída es INVISIBLE. Fue exactamente lo que pasó con el ERDDAP de
# PFEG — meses sirviendo el respaldo del IGP sin que nadie se enterara.
logger = logging.getLogger("sst-monitor")

# Consola en vivo de WhatsApp: este servicio solo PROXYa /api/live/* al agente
# (que tiene Twilio + Firestore + secretos). El navegador llama mismo-origen; el
# token gatea el acceso; los secretos NO se duplican aquí.
AGENT_BASE = os.environ.get("AGENT_BASE_URL", "").rstrip("/")
LIVE_TOKEN = os.environ.get("LIVE_CONSOLE_TOKEN", "")

# Mapa interactivo (/mapa-google, ver mapa_google.html): clave de la Maps
# JavaScript API. No es secreta en el sentido tradicional (el SDK corre en el
# navegador) — se restringe por HTTP referrer en Google Cloud Console, no
# ocultándola. Si falta, la página lo indica en vez de intentar cargar el mapa.
GOOGLE_MAPS_API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# Caché en memoria por (consulta, coords redondeadas, día). El dato NOAA es diario,
# así que basta cachear por fecha; reduce las llamadas a ERDDAP a ~1 por celda/día.
_cache: dict = {}
_lock = threading.Lock()


def _today() -> str:
    return datetime.date.today().isoformat()


def _erddap(query: str):
    url = f"{ERDDAP}?{urllib.parse.quote(query, safe='=&')}"
    try:
        resp = _client.get(url)
        resp.raise_for_status()
    except httpx.HTTPError as exc:  # red, timeout, 4xx/5xx de NOAA
        raise HTTPException(status_code=502, detail=f"NOAA ERDDAP no disponible: {exc}") from exc
    return resp.json()["table"]["rows"]


# Última fecha publicada por NOAA (el timestamp del eje 'time'), sondeada con TTL
# corto. La caché de datos se keyea con este valor, así se invalida cuando NOAA
# saca un día nuevo — NO a medianoche del servidor. El sondeo (solo el eje time)
# es barato; si falla, se reusa el último valor conocido (o la fecha del servidor).
_LATEST_TTL = 1800.0  # s (30 min): a lo sumo se revisa ~2 veces/hora
_latest = {"stamp": None, "checked": 0.0}


def _latest_noaa_time() -> str:
    now = monotonic()
    with _lock:
        stamp = _latest["stamp"]
        fresh = stamp is not None and (now - _latest["checked"]) < _LATEST_TTL
    if fresh:
        return stamp
    try:
        stamp = _erddap("time[last]")[0][0]
    except HTTPException:
        stamp = _latest["stamp"] or _today()
    with _lock:
        _latest["stamp"] = stamp
        _latest["checked"] = now
    return stamp


def _nearest_ocean(lat: float, lon: float):
    """Celda de mar (no enmascarada) más cercana al punto. Muchas coords costeras
    caen en píxeles de tierra (NaN); se pide una caja sesgada mar adentro (oeste)
    y se elige la celda válida más próxima."""
    key = ("cell", round(lat, 3), round(lon, 3), _latest_noaa_time())
    with _lock:
        if key in _cache:
            return _cache[key]
    query = (
        "analysed_sst[(last)]"
        f"[({lat + 0.2}):({lat - 0.2})]"
        f"[({lon - 0.8}):({lon + 0.1})]"
    )
    rows = _erddap(query)
    valid = [(r[1], r[2], r[3], r[0]) for r in rows if r[3] is not None]
    if not valid:
        raise HTTPException(status_code=404, detail="Sin celda de mar cercana en NOAA")
    best = min(valid, key=lambda c: (c[0] - lat) ** 2 + (c[1] - lon) ** 2)
    with _lock:
        _cache[key] = best
    return best  # (cell_lat, cell_lon, sst, iso_time)


@app.get("/api/sst")
def api_sst(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
):
    clat, clon, sst, time = _nearest_ocean(lat, lon)
    return {"sst": sst, "time": time, "cell": {"lat": clat, "lon": clon}, "source": SOURCE}


@app.get("/api/series")
def api_series(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    days: int = Query(10, ge=2, le=60),
):
    clat, clon, _, _ = _nearest_ocean(lat, lon)
    key = ("series", round(clat, 3), round(clon, 3), days, _latest_noaa_time())
    with _lock:
        if key in _cache:
            return _cache[key]
    query = f"analysed_sst[last-{days - 1}:last][({clat})][({clon})]"
    rows = _erddap(query)
    points = [{"time": r[0], "sst": r[3]} for r in rows if r[3] is not None]
    out = {"points": points, "cell": {"lat": clat, "lon": clon}, "source": SOURCE}
    with _lock:
        _cache[key] = out
    return out


@app.get("/api/status")
def api_status():
    """Frescura del dato NOAA: última fecha publicada y la próxima esperada. El
    producto es diario, así que la próxima = última + 1 día (con ~1–3 días de
    latencia hasta que NOAA la publique)."""
    last = _latest_noaa_time()
    last_date = next_date = None
    try:
        moment = datetime.datetime.fromisoformat(last.replace("Z", "+00:00"))
        last_date = moment.date().isoformat()
        next_date = (moment.date() + datetime.timedelta(days=1)).isoformat()
    except (ValueError, AttributeError):
        pass
    return {
        "last": last,
        "last_date": last_date,
        "next_date": next_date,
        "cadence": "daily",
        "source": SOURCE,
    }


# --- Estado de alerta FEN ----------------------------------------------------
# Las tres fuentes miden lo mismo: la anomalía de TSM en la región **Niño 1+2**
# (90°-80°W, 10°S-0°), la misma caja oceanográfica sobre la que el IGP calcula
# el ICEN oficial (media móvil trimestral con ERSSTv5; ver su nota técnica). Se
# usa esa caja a propósito, y NO la del visor satelital (REGION en
# satelital.html, pensada solo para el encuadre visual del mapa): así el número
# es comparable con lo que mide el ICEN, no una cifra de una zona distinta.
#
# El overlay animado de /satelital y /satelital-google sigue siendo GHRSST MUR
# L4 vía teselas WMS de NASA GIBS: son imágenes ya coloreadas, sin valores
# numéricos consultables, así que el número de la insignia se obtiene aparte.
# La cascada va por FRESCURA: para una señal TEMPRANA, el dato de anteayer vale
# más que el de la semana pasada, y más aún que el de hace tres meses. Las tres
# fuentes se contrastaron el 13-ago-2026 y coincidían (+4.39 satélite, +4.10
# semanal CPC, +1.98 el ICEN rezagado de mayo), así que preferir la más reciente
# no sacrifica exactitud.

# Fuente PRIMARIA (la más actualizada: diaria, ~2 días de latencia): anomalía de
# SST de NOAA Coral Reef Watch, 5 km, promediada por nosotros (ponderada por
# coseno de latitud) sobre la caja Niño 1+2.
#
# Antes salía del ERDDAP de PFEG (`jplMURSST41anom1day` en
# coastwatch.pfeg.noaa.gov). Ese servidor dejó de aceptar conexiones (443
# rechazado, verificado desde dos redes independientes, igual que
# upwell.pfeg.noaa.gov), así que la insignia llevaba tiempo cayendo en silencio
# al ICEN del IGP —con 3 meses de rezago— y mostrando un estado del FEN mucho
# más benigno que el real. El dataset de CRW vive en coastwatch.noaa.gov, el
# MISMO host que ya sirve el resto de la API de este servicio.
CRW_ANOM_DATASET = "noaacrwsstanomalyDaily"
CRW_ANOM_VAR = "sea_surface_temperature_anomaly"
CRW_ANOM_ERDDAP = f"https://coastwatch.noaa.gov/erddap/griddap/{CRW_ANOM_DATASET}.json"
CRW_SOURCE = ("NOAA Coral Reef Watch — anomalía diaria de SST 5 km "
              "en la región Niño 1+2 (vía ERDDAP)")

# Fuente SECUNDARIA: el índice semanal oficial de la NOAA para la región Niño
# 1+2 (CPC, sobre OISSTv2.1, base 1991-2020). Es el mismo dato que publica el
# CPC en su boletín ENSO, ya calculado sobre la región estándar — no lo
# promediamos nosotros —, pero se actualiza solo los lunes. Texto plano, sin
# ERDDAP de por medio: si ERDDAP falla, esta fuente sigue en pie.
CPC_WEEKLY_URL = "https://www.cpc.ncep.noaa.gov/data/indices/wksst9120.for"
CPC_SOURCE = "NOAA CPC — índice semanal Niño 1+2 (OISSTv2.1, base 1991-2020)"
# OJO: el archivo hermano wksst8110.for (base 1981-2010) quedó congelado en
# enero de 2021; no usarlo.
CRW_ANOM_DATASET = "noaacrwsstanomalyDaily"
CRW_ANOM_VAR = "sea_surface_temperature_anomaly"
CRW_ANOM_ERDDAP = f"https://coastwatch.noaa.gov/erddap/griddap/{CRW_ANOM_DATASET}.json"
CRW_SOURCE = ("NOAA Coral Reef Watch — anomalía diaria de SST 5 km "
              "en la región Niño 1+2 (vía ERDDAP)")
FEN_REGION = {"min_lat": -10.0, "max_lat": 0.0, "min_lon": -90.0, "max_lon": -80.0}
# Salto de índice al muestrear la grilla nativa (0.01°): 20 → ~0.2° (~22 km) de
# separación — de sobra para un promedio regional estable sin descargar la
# grilla completa (la insignia solo necesita un número, no el detalle del mapa).
FEN_REGION_STRIDE = 20
# La anomalía de un solo día es ruidosa (huecos de nubes, picos costeros
# puntuales de una sola pasada satelital) y puede saltar de categoría de un
# día para otro sin que cambie el fenómeno de fondo. Promediar los últimos N
# días la estabiliza, a costa de un pequeño rezago adicional — sigue siendo
# muchísimo más temprano que el ICEN mensual del IGP.
FEN_SMOOTH_DAYS = 5

# Respaldo: copia de datasets/icen_igp.csv (Índice Costero El Niño, Instituto
# Geofísico del Perú — clasificación oficial de 8 niveles, la misma escala que
# se usa abajo). Se copia aparte porque el build de este microservicio solo
# empaqueta esta carpeta (ver Dockerfile); actualizar reemplazando el archivo
# cuando el IGP publique un mes nuevo. Solo se consulta si el dato satelital en
# vivo no está disponible (ERDDAP caído, o la caja sin datos válidos): el ICEN
# oficial se publica con ~2-3 meses de rezago por control de calidad, por eso
# ya no es la fuente primaria de la insignia.
ICEN_CSV = HERE / "icen_igp.csv"
ICEN_SOURCE = "IGP — Índice Costero El Niño (ICEN)"

_MESES_ABBR = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]

# Umbrales oficiales ICEN/ENFEN (°C), de mayor a menor: el primero que cumpla
# "valor >= umbral" gana. Cálido = fase El Niño costero; frío = fase La Niña
# costera. color/text_color ya vienen listos para pintar la insignia sin lógica
# de contraste en el frontend. Se reutiliza tanto para el ICEN oficial (°C, ver
# respaldo arriba) como para la anomalía satelital en vivo (también en °C):
# ambas comparten unidad y orden de magnitud, así que la misma escala aplica.
_ICEN_LEVELS = [
    (3.0, "extraordinario", "Cálido extraordinario", "#7c3aad", "#ffffff"),
    (1.7, "fuerte", "Cálido fuerte", "#dc2626", "#ffffff"),
    (1.0, "moderado", "Cálido moderado", "#f97316", "#ffffff"),
    (0.4, "debil", "Cálido débil", "#eab308", "#1a1c1e"),
    (-0.4, "neutro", "Neutro", "#6b7280", "#ffffff"),
    (-1.2, "frio_debil", "Frío débil", "#93c5fd", "#1a1c1e"),
    (-1.7, "frio_moderado", "Frío moderado", "#3b82f6", "#ffffff"),
]
_ICEN_FRIO_FUERTE = ("frio_fuerte", "Frío fuerte", "#1d4ed8", "#ffffff")


def _classify_fen_level(value: float) -> tuple[str, str, str, str]:
    for threshold, key, label, color, text_color in _ICEN_LEVELS:
        if value >= threshold:
            return key, label, color, text_color
    return _ICEN_FRIO_FUERTE


def _fen_levels_table() -> list[dict]:
    """Resuelve _ICEN_LEVELS/_ICEN_FRIO_FUERTE al rango [min, max) de cada nivel,
    para que el frontend pinte la leyenda "qué es normal / qué es anomalía" sin
    duplicar los umbrales a mano en cada página."""
    ordered = list(_ICEN_LEVELS) + [(None, *_ICEN_FRIO_FUERTE)]
    table = []
    for i, (threshold, key, label, color, text_color) in enumerate(ordered):
        table.append(
            {
                "level": key,
                "label": label,
                "color": color,
                "text_color": text_color,
                "min": threshold,
                "max": ordered[i - 1][0] if i > 0 else None,
            }
        )
    return table


@app.get("/api/fen-levels")
def fen_levels():
    """Leyenda estática (no depende de ningún dato en vivo) de los 8 niveles de
    clasificación FEN/ICEN: qué anomalía de TSM en la región Niño 1+2 cuenta
    como "normal" (Neutro) y cuáles se consideran anomalía, cálida o fría."""
    return {
        "region": "Niño 1+2 (90°-80°W, 10°S-0°)",
        "unit": "°C",
        "normal_level": "neutro",
        "levels": _fen_levels_table(),
    }


_CPC_MESES = {"JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
              "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12}


def parse_cpc_weekly(text: str) -> tuple[datetime.date, float] | None:
    """(fecha de la última semana, anomalía Niño 1+2 en °C) del archivo del CPC.

    Formato de cada línea: fecha centrada de la semana y luego CUATRO pares
    (SST, anomalía), uno por región — Niño 1+2, 3, 3.4 y 4:

        05AUG2026     25.3 4.1     28.4 3.1     29.5 2.6     29.8 1.1
        27JAN2021     24.6-0.4     25.7-0.2     25.9-0.7     27.1-1.1

    Las anomalías negativas quedan PEGADAS al valor de SST (`24.6-0.4`), así que
    no se puede partir por espacios: se extraen los números por regex. El mes va
    en inglés y se mapea a mano (no con %b) para no depender del locale.
    """
    for line in reversed(text.splitlines()):
        line = line.strip()
        match = re.match(r"^(\d{2})([A-Z]{3})(\d{4})\s+(.*)$", line)
        if not match:
            continue
        day, mon, year, rest = match.groups()
        if mon not in _CPC_MESES:
            continue
        numbers = re.findall(r"-?\d+\.\d+", rest)
        if len(numbers) < 2:
            continue
        try:
            fecha = datetime.date(int(year), _CPC_MESES[mon], int(day))
        except ValueError:
            continue
        return fecha, float(numbers[1])  # [0]=SST Niño 1+2, [1]=su anomalía
    return None


def _cpc_weekly_reading() -> tuple[datetime.date, float] | None:
    """Última anomalía semanal oficial de Niño 1+2, o None si el CPC no responde."""
    try:
        resp = _client.get(CPC_WEEKLY_URL)
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        logger.warning("CPC semanal no disponible: %s", exc)
        return None
    reading = parse_cpc_weekly(resp.text)
    if reading is None:
        logger.warning("CPC semanal: no se pudo parsear ninguna línea de datos")
    return reading


def _crw_anomaly_reading() -> tuple[str, float] | None:
    """(fecha_iso más reciente, anomalía_°C promedio de los últimos
    FEN_SMOOTH_DAYS días) sobre la caja norte de Perú, o None si ERDDAP no
    responde o la ventana queda sin ninguna celda válida (nubes/tierra
    enmascaran todo el muestreo).

    El recorte temporal va por ÍNDICE (`[last-4:last]`), no por valor
    (`[(last-4):(last)]`): entre paréntesis ERDDAP interpreta el número en las
    unidades del eje — segundos desde 1970 — así que la forma anterior pedía los
    últimos 4 SEGUNDOS y devolvía un solo día. El promedio de FEN_SMOOTH_DAYS
    días nunca llegó a promediar nada.
    """
    query = (
        f"{CRW_ANOM_VAR}[last-{FEN_SMOOTH_DAYS - 1}:last]"
        f"[({FEN_REGION['min_lat']}):{FEN_REGION_STRIDE}:({FEN_REGION['max_lat']})]"
        f"[({FEN_REGION['min_lon']}):{FEN_REGION_STRIDE}:({FEN_REGION['max_lon']})]"
    )
    url = f"{CRW_ANOM_ERDDAP}?{urllib.parse.quote(query, safe='=&')}"
    try:
        resp = _client.get(url)
        resp.raise_for_status()
        rows = resp.json()["table"]["rows"]  # cada fila: [time, latitude, longitude, anom]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning("Anomalía satelital CRW no disponible: %s", exc)
        return None
    weighted_sum = weight_total = 0.0
    latest_time = None
    for time_iso, lat, _lon, value in rows:
        if value is None:
            continue
        weight = math.cos(math.radians(lat))
        weighted_sum += value * weight
        weight_total += weight
        if latest_time is None or time_iso > latest_time:
            latest_time = time_iso
    if weight_total == 0.0 or latest_time is None:
        return None
    return latest_time, weighted_sum / weight_total


def _status_from_cpc(fecha: datetime.date, anomaly: float) -> dict:
    """Insignia a partir del índice semanal oficial del CPC (fuente primaria)."""
    key, label, color, text_color = _classify_fen_level(anomaly)
    days_behind = max((datetime.date.today() - fecha).days, 0)
    signo = "+" if anomaly >= 0 else ""
    texto_fecha = f"semana del {fecha.day} {_MESES_ABBR[fecha.month - 1]}"
    lag = f" (hace {days_behind} día{'s' if days_behind != 1 else ''})" if days_behind else ""
    return {
        "available": True,
        "level": key,
        "label": label,
        "color": color,
        "text_color": text_color,
        "value": anomaly,
        "date": texto_fecha,
        "display": (f"Estado del FEN (Costa Norte Perú): {label} · "
                    f"Anom. SST {signo}{anomaly:.2f}°C ({texto_fecha})"),
        "tooltip": (
            "Anomalía satelital diaria no disponible en este momento — se muestra el "
            "índice semanal oficial de la NOAA (CPC) para la región Niño 1+2 — la "
            "misma región que usa el ICEN del IGP —, sobre OISSTv2.1 con base "
            f"1991-2020. Dato de la {texto_fecha}{lag}; el CPC lo actualiza los lunes."
        ),
        "source": CPC_SOURCE,
    }


def _status_from_satellite(time_iso: str, anomaly: float) -> dict:
    key, label, color, text_color = _classify_fen_level(anomaly)
    try:
        moment = datetime.datetime.fromisoformat(time_iso.replace("Z", "+00:00")).date()
    except (ValueError, AttributeError):
        moment = datetime.date.today()
    days_behind = max((datetime.date.today() - moment).days, 0)
    signo = "+" if anomaly >= 0 else ""
    fecha = f"{moment.day} {_MESES_ABBR[moment.month - 1]}"
    lag = f" (hace {days_behind} día{'s' if days_behind != 1 else ''})" if days_behind > 0 else ""
    return {
        "available": True,
        "level": key,
        "label": label,
        "color": color,
        "text_color": text_color,
        # "value"/"date" en crudo, además de "display": para consumidores que no
        # quieran parsear el texto ya armado (p. ej. la alerta por WhatsApp de
        # app.sst_alert, que reusa este mismo endpoint como fuente única).
        "value": anomaly,
        "date": fecha,
        # Una sola línea a propósito: es una "píldora" bajo el <h1>, no un
        # párrafo — el detalle va en el tooltip (title), no en el texto visible.
        "display": f"Estado del FEN (Costa Norte Perú): {label} · Anom. SST {signo}{anomaly:.2f}°C ({fecha})",
        "tooltip": (
            "Estado del FEN para la costa norte, según la anomalía satelital diaria "
            "de temperatura del mar (NOAA Coral Reef Watch, 5 km) en la región "
            "Niño 1+2 — la misma región que usa el ICEN del IGP —, promedio de los "
            f"últimos {FEN_SMOOTH_DAYS} días (para no reaccionar a un solo día "
            f"ruidoso). Dato más reciente del {fecha}{lag}."
        ),
        "source": CRW_SOURCE,
    }


def _status_from_icen(year: int, month: int, value: float) -> dict:
    key, label, color, text_color = _classify_fen_level(value)
    today = datetime.date.today()
    months_behind = max((today.year - year) * 12 + (today.month - month), 0)
    signo = "+" if value >= 0 else ""
    mes = f"{_MESES_ABBR[month - 1]} {year}"
    lag = (
        f", el más reciente publicado (hace {months_behind} mes{'es' if months_behind != 1 else ''}) "
        "— el ICEN oficial del IGP se publica con rezago por control de calidad"
        if months_behind > 0
        else ""
    )
    return {
        "available": True,
        "level": key,
        "label": label,
        "color": color,
        "text_color": text_color,
        "value": value,
        "date": mes,
        "display": f"Estado del FEN (Costa Norte Perú): {label} · ICEN {signo}{value:.2f} ({mes})",
        "tooltip": (
            "Dato satelital en vivo no disponible en este momento — se muestra el ICEN "
            f"oficial del IGP como respaldo. Estado del FEN para la costa norte, dato de {mes}{lag}."
        ),
        "source": ICEN_SOURCE,
    }


def _latest_icen() -> tuple[int, int, float] | None:
    try:
        with open(ICEN_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
    except OSError:
        return None
    if not rows:
        return None
    last = rows[-1]
    try:
        return int(last["year"]), int(last["month"]), float(last["icen"])
    except (KeyError, ValueError):
        return None


# TTL generoso a propósito: el dato satelital es ~diario (~1-2 d de latencia),
# así que refrescar cada hora ya sigue de cerca cualquier cambio real, sin
# golpear ERDDAP en cada carga de página.
_FEN_STATUS_TTL = 3600.0  # s
_fen_status_cache = {"data": None, "checked": 0.0}


def _fen_status() -> dict:
    now = monotonic()
    with _lock:
        cached = _fen_status_cache["data"]
        fresh = cached is not None and (now - _fen_status_cache["checked"]) < _FEN_STATUS_TTL
    if fresh:
        return cached
    # Cascada por FRESCURA: la anomalía satelital diaria (~2 días de latencia),
    # luego el índice semanal oficial del CPC (lunes) y, como última red, el ICEN
    # del IGP (oficial peruano, pero con ~3 meses de rezago: red de seguridad, no
    # fuente habitual). Es una señal TEMPRANA: el dato de anteayer vale más que el
    # de la semana pasada.
    satelital = _crw_anomaly_reading()
    if satelital is not None:
        result = _status_from_satellite(*satelital)
    else:
        cpc = _cpc_weekly_reading()
        if cpc is not None:
            result = _status_from_cpc(*cpc)
        else:
            icen = _latest_icen()
            logger.warning("FEN: sin satélite ni CPC; %s",
                           "se usa el ICEN del IGP" if icen else "sin dato alguno")
            result = _status_from_icen(*icen) if icen else {"available": False}
    with _lock:
        _fen_status_cache["data"] = result
        _fen_status_cache["checked"] = now
    return result


@app.get("/api/fen-status")
def fen_status():
    """Nivel de alerta FEN vigente para la costa norte. Fuente primaria: anomalía
    de SST en vivo (satélite GHRSST MUR L4 — el mismo producto que NASA GIBS
    pinta en /satelital y /satelital-google). Si ERDDAP no responde o la caja
    queda sin datos válidos, cae al ICEN oficial del IGP (con su rezago propio
    de ~2-3 meses) como respaldo. Fail-open: {"available": false} si ninguna de
    las dos fuentes tiene dato, para que el frontend simplemente no muestre
    la insignia."""
    return _fen_status()


@app.get("/health")
def health():
    return {"status": "ok", "source": SOURCE}


@app.api_route("/api/live/{path:path}", methods=["GET", "POST"])
async def live_proxy(path: str, request: Request):
    """Proxy mismo-origen → agente. Gatea por token (query ?token= o X-Live-Token)
    y reenvía con la cabecera X-Live-Token que el agente valida."""
    token = request.query_params.get("token") or request.headers.get("x-live-token", "")
    if not LIVE_TOKEN or token != LIVE_TOKEN:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if not AGENT_BASE:
        return JSONResponse({"error": "backend no configurado (AGENT_BASE_URL)"}, status_code=503)
    url = f"{AGENT_BASE}/api/live/{path}"
    headers = {"X-Live-Token": LIVE_TOKEN}
    try:
        if request.method == "GET":
            params = {k: v for k, v in request.query_params.items() if k != "token"}
            resp = _client.get(url, params=params, headers=headers)
        else:
            headers["content-type"] = "application/json"
            resp = _client.post(url, content=await request.body(), headers=headers)
    except httpx.HTTPError as exc:
        return JSONResponse({"error": f"agente no disponible: {exc}"}, status_code=502)
    return Response(
        content=resp.content,
        status_code=resp.status_code,
        media_type=resp.headers.get("content-type", "application/json"),
    )


_CSP = (
    "default-src 'self'; connect-src 'self'; "
    # La vista satelital (/satelital) carga teselas WMS y leyendas como <img> desde
    # NASA GIBS (imágenes públicas, sin API key). Solo se permite img-src a ese host.
    "img-src 'self' data: https://gibs.earthdata.nasa.gov; "
    "style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; "
    "base-uri 'self'; frame-ancestors 'none'"
)

# El mapa interactivo (/mapa-google) incrusta el widget real de Google Maps JS
# (calles/satélite/Street View) para el detalle de geolocalización que no da un
# mapa SVG propio: necesita permitir los hosts que sirven su script, teselas y
# fuentes. 'unsafe-eval' lo exige el propio bundle de Maps JS, no código nuestro.
_CSP_GMAPS = (
    "default-src 'self'; "
    "connect-src 'self' https://maps.googleapis.com https://*.googleapis.com; "
    "img-src 'self' data: https://*.googleapis.com https://*.gstatic.com https://*.ggpht.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://maps.googleapis.com; "
    "base-uri 'self'; frame-ancestors 'none'"
)

# El visor satelital sobre Google Maps (/satelital-google) es el mismo caso que
# /mapa-google (necesita los hosts de Maps JS) MÁS los fotogramas WMS de NASA
# GIBS que sigue pintando encima como overlay animado (igual que /satelital).
_CSP_GMAPS_SAT = (
    "default-src 'self'; "
    "connect-src 'self' https://maps.googleapis.com https://*.googleapis.com; "
    "img-src 'self' data: https://*.googleapis.com https://*.gstatic.com https://*.ggpht.com "
    "https://gibs.earthdata.nasa.gov; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://maps.googleapis.com; "
    "base-uri 'self'; frame-ancestors 'none'"
)

_CSP_BY_PATH = {"/mapa-google": _CSP_GMAPS, "/satelital-google": _CSP_GMAPS_SAT}

# Todas las páginas HTML (no /api/*, /map.json, etc.): un ETag + "no-cache" no
# evitó confusión real más de una vez (un navegador o proxy intermedio sirviendo
# el JS de una versión vieja mientras la API ya devuelve datos nuevos, dando la
# falsa impresión de un bug — pasó con la clave de Google Maps y con el ancho
# de la insignia ICEN). El sitio es de bajo tráfico: el costo de "no-store" en
# banda ancha es irrelevante frente a evitar esa clase de confusión de nuevo.
_NO_STORE_PATHS = {"/", "/satelital", "/satelital-google", "/mapa-google", "/consola"}


@app.middleware("http")
async def _security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Content-Security-Policy"] = _CSP_BY_PATH.get(request.url.path, _CSP)
    resp.headers["Cache-Control"] = (
        "no-store" if request.url.path in _NO_STORE_PATHS else "no-cache"
    )
    return resp


@app.get("/map.json")
def map_data():
    # Geometría del mapa (departamentos del Perú, Ecuador, océano, proyección),
    # generada offline. Se sirve aparte para no inflar index.html.
    return FileResponse(HERE / "map.json", media_type="application/json")


@app.get("/satelital")
def satelital():
    # Vista satelital animada (NASA GIBS / GHRSST MUR): anomalía y SST en un loop
    # temporal sobre el norte de Perú. El navegador pide las teselas WMS directo a
    # GIBS (por eso el img-src del CSP incluye ese host); este servicio solo la sirve.
    return FileResponse(HERE / "satelital.html", media_type="text/html")


@app.get("/satelital-google")
def satelital_google():
    # Copia de /satelital con el mapa base propio (BlueMarble + costas + límites
    # departamentales dibujados a mano) reemplazado por un mapa real de Google
    # (calles/satélite/relieve/Street View, con nombres y límites reales) para
    # mayor detalle de geolocalización; el fotograma animado de anomalía/SST de
    # NASA GIBS se sigue pintando encima como overlay, ahora sincronizado al
    # viewport real de Google en vez de a un estado de zoom/pan propio. La clave
    # se inyecta igual que en /mapa-google (ver esa ruta).
    html = (HERE / "satelital_google.html").read_text(encoding="utf-8")
    html = html.replace("__GOOGLE_MAPS_API_KEY__", GOOGLE_MAPS_API_KEY)
    return Response(content=html, media_type="text/html")


@app.get("/mapa-google")
def mapa_google():
    # Copia de index.html con el mapa de calor SVG propio reemplazado por un mapa
    # real de Google Maps (calles/satélite/relieve/Street View): mayor detalle de
    # geolocalización que la proyección estilizada. La clave se inyecta aquí (no
    # vive en el HTML del repo) a partir de GOOGLE_MAPS_API_KEY; si falta, la
    # página lo indica en vez de intentar cargar un mapa roto.
    html = (HERE / "mapa_google.html").read_text(encoding="utf-8")
    html = html.replace("__GOOGLE_MAPS_API_KEY__", GOOGLE_MAPS_API_KEY)
    return Response(content=html, media_type="text/html")


@app.get("/consola")
def consola():
    # Copia de /satelital + consola de WhatsApp bidireccional (texto y voz),
    # de un solo usuario. La sincronización en vivo la sirve el backend del
    # agente (Twilio + Firestore); esta ruta solo entrega la página.
    return FileResponse(HERE / "consola.html", media_type="text/html")


@app.get("/")
def index():
    return FileResponse(HERE / "index.html", media_type="text/html")
