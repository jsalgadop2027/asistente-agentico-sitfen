"""Tools de gráficos: imágenes PNG con datos REALES del proyecto (temperatura
del mar, precipitación NOAA) para enviar por WhatsApp.

A diferencia de las demás tools (que solo devuelven texto), estas ADEMÁS
publican el PNG en el mismo bucket privado que usa la voz de salida (URL
firmada temporal, mismo mecanismo que `app.voice.tts.synthesize_to_signed_url`)
y anexan la URL a su propio texto de retorno con el marcador
'[GRAFICO_URL: ...]', que `app.agent.translation.extract_chart_url` recupera
del `ToolMessage` real al final del turno para adjuntarla a
`AgentResponse.chart_url` (NO se usa un `contextvar`: LangGraph ejecuta cada
tool call en un hilo del pool con contexto copiado, así que una mutación hecha
dentro de la tool no es visible después de `agent.invoke()` — mismo motivo por
el que las fuentes de las tools RAG usan el marcador '[Fuentes: ...]' en vez
de estado compartido). La ENTREGA de la imagen (adjuntarla al mensaje de
WhatsApp) no es responsabilidad de la tool, igual que `consultar_clima` no
decide si la respuesta se locuta en voz.

matplotlib corre con el backend "Agg" (sin interfaz gráfica, apto para
servidor) — debe fijarse ANTES de importar `pyplot`.
"""
from __future__ import annotations

import io
from datetime import date, datetime

import httpx
import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from langchain_core.tools import tool  # noqa: E402

from app.agent.tools.media_upload import upload_image  # noqa: E402
from app.config import settings  # noqa: E402
from app.observability import get_logger  # noqa: E402

logger = get_logger(__name__)

_TIMEOUT = 20


def _render_chart(dates_: list[date], values: list[float], *, title: str,
                  ylabel: str, color: str, kind: str = "line") -> bytes:
    """Renderiza un PNG simple (línea o barras) a partir de una serie real."""
    fig, ax = plt.subplots(figsize=(7, 4), dpi=140)
    if kind == "bar":
        ax.bar(dates_, values, color=color, width=0.8)
    else:
        ax.plot(dates_, values, color=color, marker="o", markersize=3, linewidth=1.8)
        ax.fill_between(dates_, values, min(values) if values else 0,
                        color=color, alpha=0.12)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d-%b"))
    fig.autofmt_xdate(rotation=35)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def _publish_chart(png: bytes) -> str | None:
    """Sube el gráfico y devuelve su URL firmada (o None si falló)."""
    return upload_image(png, prefix="charts")


@tool
def graficar_temperatura_mar(ubicacion: str, dias: int = 15) -> str:
    """Genera y ENVÍA (como imagen) un gráfico de la evolución reciente de la
    temperatura superficial del mar (SST) cerca de una ciudad costera o zona
    productora de arándano del norte del Perú, con datos satelitales reales:
    útil para visualizar la tendencia asociada al Fenómeno de El Niño. Acepta
    `ubicacion` como NOMBRE de ciudad/zona (p. ej. "Trujillo", "Chao", "Piura")
    o como coordenadas "lat,lon"; `dias` (2-60, por defecto 15) es la ventana
    reciente a graficar. Úsala cuando el usuario pida explícitamente un
    gráfico, imagen o visual de la temperatura del mar."""
    base = (settings.sst_monitor_base_url or "").rstrip("/")
    if not base:
        return ("El servicio de monitoreo satelital no está configurado, así "
                "que no puedo generar el gráfico de temperatura del mar ahora.")
    from app.agent.tools.noaa_tools import _resolve_coords

    resolved = _resolve_coords(ubicacion)
    if not resolved:
        return (f"No reconozco «{ubicacion}» como zona costera o productora de "
                "arándano. Prueba con el nombre de una región (p. ej. «Trujillo», "
                "«Piura», «Chao») o con coordenadas «lat,lon».")
    lat, lon, nombre = resolved
    dias = max(2, min(60, dias))
    try:
        r = httpx.get(f"{base}/api/series",
                      params={"lat": lat, "lon": lon, "days": dias}, timeout=_TIMEOUT)
        r.raise_for_status()
        points = (r.json() or {}).get("points") or []
    except Exception as exc:  # noqa: BLE001
        logger.warning("sst_series_failed", error=str(exc))
        points = []
    if not points:
        return (f"No hay datos satelitales de temperatura del mar disponibles "
                f"cerca de {nombre} en este momento. Intenta de nuevo más tarde.")

    dates_: list[date] = []
    values: list[float] = []
    for p in points:
        try:
            dates_.append(datetime.fromisoformat(
                str(p["time"]).replace("Z", "+00:00")).date())
            values.append(float(p["sst"]))
        except (KeyError, ValueError, TypeError):
            continue
    if not values:
        return f"No pude interpretar los datos de temperatura del mar cerca de {nombre}."

    png = _render_chart(dates_, values,
                        title=f"Temperatura del mar cerca de {nombre}",
                        ylabel="°C", color="#c0392b", kind="line")
    url = _publish_chart(png)
    resumen = (f"de {min(values):.1f} °C a {max(values):.1f} °C "
              f"(promedio {sum(values) / len(values):.1f} °C)")
    if not url:
        return (f"Calculé la temperatura del mar cerca de {nombre} en los últimos "
                f"{len(values)} días ({resumen}), pero no pude generar la imagen "
                "del gráfico ahora mismo.")
    return (f"📈 Gráfico generado: temperatura del mar cerca de {nombre} en los "
           f"últimos {len(values)} días, {resumen}.\n\n[GRAFICO_URL: {url}]")


@tool
def graficar_precipitacion(ubicacion: str, dias: int = 30) -> str:
    """Genera y ENVÍA (como imagen) un gráfico de barras de la precipitación
    diaria reciente (mm) registrada por la estación NOAA real más cercana a
    una zona productora de arándano o ciudad costera del norte del Perú,
    señal temprana del Fenómeno de El Niño. Acepta `ubicacion` como NOMBRE de
    zona (p. ej. "Trujillo", "Piura", "Chiclayo", "Ica") o "lat,lon"; `dias`
    (7-120, por defecto 30) es la ventana a graficar. Úsala cuando el usuario
    pida explícitamente un gráfico, imagen o visual de la lluvia/precipitación
    (para solo el dato en texto, usa "consultar_datos_noaa")."""
    if not settings.noaa_api_token:
        return ("El servicio de datos NOAA no está configurado, así que no "
                "puedo generar el gráfico de precipitación ahora.")
    from app.agent.tools.noaa_tools import (_fetch_daily_precip, _nearest_station,
                                            _resolve_coords)

    resolved = _resolve_coords(ubicacion)
    if not resolved:
        return (f"No reconozco «{ubicacion}» como zona productora de arándano o "
                "ciudad costera. Prueba con el nombre de una región (p. ej. "
                "«Trujillo», «Piura», «Chiclayo», «Ica») o con coordenadas «lat,lon».")
    lat, lon, nombre = resolved
    station = _nearest_station(lat, lon)
    if not station:
        return f"No pude encontrar una estación NOAA cercana a «{ubicacion}» ahora mismo."
    station_id, station_name, maxdate = station
    dias = max(7, min(120, dias))
    results = _fetch_daily_precip(station_id, end=maxdate, days=dias)
    if not results:
        return (f"NOAA no tiene observaciones de precipitación recientes para la "
                f"estación {station_name} (la más cercana a {nombre}).")

    by_day: dict[date, float] = {}
    for r in results:
        try:
            d = date.fromisoformat(str(r["date"])[:10])
            by_day[d] = by_day.get(d, 0.0) + float(r["value"])
        except (KeyError, ValueError, TypeError):
            continue
    if not by_day:
        return f"No pude interpretar los datos de precipitación cerca de {nombre}."
    dates_ = sorted(by_day.keys())
    values = [by_day[d] for d in dates_]

    png = _render_chart(dates_, values,
                        title=f"Precipitación diaria cerca de {nombre}",
                        ylabel="mm", color="#2e74b5", kind="bar")
    url = _publish_chart(png)
    total = sum(values)
    if not url:
        return (f"Calculé {total:.1f} mm acumulados cerca de {nombre} "
                f"({dates_[0]} a {dates_[-1]}), pero no pude generar la imagen "
                "del gráfico ahora mismo.")
    return (f"📊 Gráfico generado: precipitación diaria cerca de {nombre} "
           f"del {dates_[0]} al {dates_[-1]}, {total:.1f} mm acumulados."
           f"\n\n[GRAFICO_URL: {url}]")
