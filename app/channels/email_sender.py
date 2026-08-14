"""Envío de correo transaccional vía SendGrid (API v3).

Se usa para el informe diario de inquietudes (#8, ver `app.daily_report`). La API
key NO se hardcodea: se resuelve en runtime desde Secret Manager (o de la env
`SENDGRID_API_KEY` en desarrollo), igual que el resto de secretos.

Requisito de SendGrid: el remitente (`email_from`) debe ser un **sender
verificado** (Single Sender o dominio autenticado); de lo contrario la API
responde 403.
"""
from __future__ import annotations

import httpx

from app.config import get_secret, settings
from app.observability import get_logger

logger = get_logger(__name__)

_SENDGRID_URL = "https://api.sendgrid.com/v3/mail/send"


def send_email(*, to: str, subject: str, html: str,
               text: str | None = None, reply_to: str | None = None) -> bool:
    """Envía un correo por SendGrid. Devuelve True si fue aceptado (HTTP 2xx).

    `reply_to` (opcional) fija la dirección de respuesta (p. ej. el correo del
    usuario cuya solicitud se deriva, para que la entidad le responda directo).

    Nunca lanza: los errores se registran y se devuelve False (fail-open para que
    un fallo de correo no tumbe el job del informe diario).
    """
    api_key = get_secret(settings.secret_sendgrid_api_key,
                         fallback_env="SENDGRID_API_KEY")
    if not api_key:
        logger.error("sendgrid_api_key_missing")
        return False

    content = []
    if text:
        content.append({"type": "text/plain", "value": text})
    content.append({"type": "text/html", "value": html})

    payload = {
        "personalizations": [{"to": [{"email": to}]}],
        "from": {"email": settings.email_from, "name": settings.email_from_name},
        "subject": subject,
        "content": content,
    }
    if reply_to:
        payload["reply_to"] = {"email": reply_to}
    headers = {"Authorization": f"Bearer {api_key}",
               "Content-Type": "application/json"}
    try:
        resp = httpx.post(_SENDGRID_URL, json=payload, headers=headers, timeout=30)
        if 200 <= resp.status_code < 300:
            logger.info("email_sent", to=to, status=resp.status_code)
            return True
        logger.error("email_send_failed", to=to, status=resp.status_code,
                     body=(resp.text or "")[:300])
        return False
    except Exception as exc:  # noqa: BLE001
        logger.error("email_send_error", to=to, error=str(exc))
        return False
