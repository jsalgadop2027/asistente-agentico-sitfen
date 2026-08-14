"""Subida de imágenes generadas por tools al bucket privado de media.

Compartido por `chart_tools.py` (gráficos con datos reales) e `image_gen_tools.py`
(ilustraciones generadas por IA): ambos producen un PNG en memoria y necesitan
publicarlo como una URL temporal que Twilio pueda descargar para adjuntarla al
mensaje de WhatsApp saliente.
"""
from __future__ import annotations

import uuid

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


def upload_image(png: bytes, *, prefix: str) -> str | None:
    """Sube el PNG al bucket privado (mismo que la voz) y devuelve una URL
    firmada temporal. Fail-open: None si algo falla (no rompe el turno)."""
    try:
        from datetime import timedelta

        import google.auth
        from google.auth.transport import requests as google_requests
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(settings.gcs_audio_bucket)
        blob = bucket.blob(f"{prefix}/{uuid.uuid4().hex}.png")
        blob.upload_from_string(png, content_type="image/png")

        # Igual que en tts.py: en Cloud Run las credenciales ambiente solo
        # traen un token (sin llave privada); se delega la firma a la API de
        # IAM (signBlob) con el email y access token explícitos.
        credentials, _ = google.auth.default()
        credentials.refresh(google_requests.Request())
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=settings.signed_url_ttl_seconds),
            method="GET",
            service_account_email=credentials.service_account_email,
            access_token=credentials.token,
        )
        logger.info("image_uploaded", bytes=len(png), prefix=prefix)
        return url
    except Exception as exc:  # noqa: BLE001
        logger.error("image_upload_failed", error=str(exc), prefix=prefix)
        return None
