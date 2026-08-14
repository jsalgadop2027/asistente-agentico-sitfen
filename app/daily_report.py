"""Informe diario de inquietudes (#8).

A las 20:00 (hora de Lima), un Cloud Scheduler invoca `/internal/daily-report`
(ver `app.main`), que corre `send_daily_report()`. Este módulo:
  1. Recupera las inquietudes del día (colección `user_concerns`, ver
     `app.concerns`) — reclamos, pedidos, sugerencias y recomendaciones.
  2. Identifica al usuario de cada una (nombre + código) vía `user_registry`.
  3. Genera un resumen ejecutivo con el LLM.
  4. Compone un correo (HTML + texto) y lo envía por SendGrid a
     `settings.daily_report_to`.

Fail-open: si algo falla, se registra y no se propaga (el job nunca "revienta").
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from app.concerns import CONCERN_TYPES, ConcernStore, lima_day_str
from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

_TYPE_LABELS = {
    "reclamo": "Reclamos",
    "pedido": "Pedidos",
    "sugerencia": "Sugerencias",
    "recomendacion": "Recomendaciones",
    "preocupacion": "Preocupaciones",
}

_SUMMARY_PROMPT = (
    "Eres analista de atención al cliente del asistente de inteligencia comercial "
    "del arándano peruano. A partir de las inquietudes del día (ya clasificadas), "
    "redacta un RESUMEN EJECUTIVO breve en español (máx. 120 palabras): destaca los "
    "temas recurrentes, la urgencia y qué conviene atender primero. Prosa, sin "
    "viñetas ni encabezados.\n\nINQUIETUDES DEL DÍA:\n{items}"
)


@dataclass
class DailyReport:
    day: str
    total: int
    by_type: dict[str, list[dict]]
    subject: str
    html: str
    text: str


def _lima_hhmm(ts) -> str:
    """Hora local (12 h, con AM/PM) de un timestamp de Firestore; '' si no aplica."""
    if not isinstance(ts, datetime):
        return ""
    local = ts.astimezone(timezone.utc) + timedelta(
        hours=settings.lima_utc_offset_hours)
    return local.strftime("%I:%M %p")


def _identify(user_id: str, registry, cache: dict[str, str]) -> str:
    """Etiqueta legible del usuario: 'Nombre Apellido (CÓDIGO)' o el id crudo."""
    if user_id in cache:
        return cache[user_id]
    label = user_id
    try:
        rec = registry.get_by_code(user_id)
        if rec is not None:
            nombre = f"{rec.nombre} {rec.apellido}".strip()
            label = f"{nombre} ({user_id})" if nombre else user_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("concern_identify_failed", error=str(exc))
    cache[user_id] = label
    return label


def _build_summary(by_type: dict[str, list[dict]]) -> str:
    lines = []
    for tipo in CONCERN_TYPES:
        for c in by_type.get(tipo, []):
            lines.append(f"[{tipo}] {c['who']}: {c['resumen']}")
    if not lines:
        return "No se registraron inquietudes hoy."
    try:
        from app.agent.models import invoke_with_failover

        resp = invoke_with_failover(
            _SUMMARY_PROMPT.format(items="\n".join(lines)[:6000]),
            pro=True, temperature=0.3)
        text = getattr(resp, "content", "") or ""
        if isinstance(text, list):
            text = " ".join(b.get("text", "") for b in text if isinstance(b, dict))
        text = str(text).strip()
        if text:
            return text
    except Exception as exc:  # noqa: BLE001
        logger.warning("daily_report_summary_failed", error=str(exc))
    return f"Se registraron {len(lines)} inquietudes hoy (ver detalle abajo)."


def build_daily_report(day: Optional[str] = None,
                       store: Optional[ConcernStore] = None) -> DailyReport:
    day = day or lima_day_str()
    rows = (store or ConcernStore()).list_for_day(day)

    from app.user_registry import get_user_registry

    registry = get_user_registry()
    cache: dict[str, str] = {}

    by_type: dict[str, list[dict]] = {t: [] for t in CONCERN_TYPES}
    for r in rows:
        tipo = str(r.get("tipo", "")).lower()
        if tipo not in by_type:
            continue
        by_type[tipo].append({
            "who": _identify(str(r.get("user_id", "")), registry, cache),
            "resumen": r.get("resumen") or r.get("message") or "",
            "hora": _lima_hhmm(r.get("created_at")),
        })

    total = sum(len(v) for v in by_type.values())
    summary = _build_summary(by_type)
    subject = f"Informe diario de inquietudes — {day} ({total})"
    html = _render_html(day, total, by_type, summary)
    text = _render_text(day, total, by_type, summary)
    return DailyReport(day=day, total=total, by_type=by_type,
                       subject=subject, html=html, text=text)


def _render_html(day: str, total: int, by_type: dict[str, list[dict]],
                 summary: str) -> str:
    parts = [
        "<div style=\"font-family:Arial,Helvetica,sans-serif;color:#1a1a1a\">",
        "<h2 style=\"margin:0 0 4px\">Informe diario de inquietudes</h2>",
        f"<p style=\"color:#555;margin:0 0 16px\">{escape(day)} · "
        f"{total} registro(s)</p>",
        "<div style=\"background:#f4f7fb;border-left:4px solid #2b6cb0;"
        "padding:12px 16px;margin-bottom:20px;border-radius:4px\">"
        f"<strong>Resumen ejecutivo</strong><br>{escape(summary)}</div>",
    ]
    for tipo in CONCERN_TYPES:
        items = by_type.get(tipo, [])
        parts.append(
            f"<h3 style=\"margin:18px 0 6px\">{escape(_TYPE_LABELS[tipo])} "
            f"({len(items)})</h3>")
        if not items:
            parts.append("<p style=\"color:#888;margin:0\">—</p>")
            continue
        parts.append("<table style=\"width:100%;border-collapse:collapse\">")
        for it in items:
            hora = f" · {escape(it['hora'])}" if it["hora"] else ""
            parts.append(
                "<tr><td style=\"padding:6px 8px;border-bottom:1px solid #eee;"
                "vertical-align:top\">"
                f"<strong>{escape(it['who'])}</strong>{hora}<br>"
                f"{escape(it['resumen'])}</td></tr>")
        parts.append("</table>")
    parts.append("</div>")
    return "".join(parts)


def _render_text(day: str, total: int, by_type: dict[str, list[dict]],
                 summary: str) -> str:
    lines = [f"INFORME DIARIO DE INQUIETUDES — {day} ({total})", "",
             f"Resumen ejecutivo: {summary}", ""]
    for tipo in CONCERN_TYPES:
        items = by_type.get(tipo, [])
        lines.append(f"== {_TYPE_LABELS[tipo]} ({len(items)}) ==")
        if not items:
            lines.append("  —")
        for it in items:
            hora = f" [{it['hora']}]" if it["hora"] else ""
            lines.append(f"  - {it['who']}{hora}: {it['resumen']}")
        lines.append("")
    return "\n".join(lines)


def send_daily_report(day: Optional[str] = None) -> bool:
    """Construye y envía el informe. Devuelve True si el correo fue aceptado."""
    from app.channels.email_sender import send_email

    if not settings.daily_report_enabled:
        logger.info("daily_report_disabled")
        return False
    report = build_daily_report(day)
    ok = send_email(to=settings.daily_report_to, subject=report.subject,
                    html=report.html, text=report.text)
    logger.info("daily_report_done", day=report.day, total=report.total, sent=ok)
    return ok
