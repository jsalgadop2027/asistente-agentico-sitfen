"""Integración con Twilio WhatsApp: validación, descarga de media y TwiML.

Seguridad: valida la firma X-Twilio-Signature para asegurar que el webhook
proviene de Twilio (anti-spoofing). Las credenciales se leen de Secret Manager.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

import httpx
from twilio.request_validator import RequestValidator
from twilio.twiml.messaging_response import MessagingResponse

from app.config import get_twilio_credentials
from app.observability import get_logger

logger = get_logger(__name__)


@dataclass
class IncomingMessage:
    from_number: str           # 'whatsapp:+51...'
    body: str
    num_media: int
    media_url: str | None
    media_content_type: str | None
    latitude: str | None = None     # presente si el usuario comparte su ubicación
    longitude: str | None = None
    address: str | None = None      # dirección aproximada (la da Twilio)

    @property
    def user_id(self) -> str:
        return self.from_number.replace("whatsapp:", "").strip()

    @property
    def is_voice(self) -> bool:
        return self.num_media > 0 and bool(
            self.media_content_type and self.media_content_type.startswith("audio")
        )

    @property
    def is_image(self) -> bool:
        return self.num_media > 0 and bool(
            self.media_content_type and self.media_content_type.startswith("image")
        )

    @property
    def is_location(self) -> bool:
        """True si el mensaje es una ubicación compartida (trae lat/lon)."""
        return bool(self.latitude and self.longitude)


def parse_incoming(form: dict[str, str]) -> IncomingMessage:
    num_media = int(form.get("NumMedia", "0") or 0)
    return IncomingMessage(
        from_number=form.get("From", ""),
        body=(form.get("Body", "") or "").strip(),
        num_media=num_media,
        media_url=form.get("MediaUrl0") if num_media else None,
        media_content_type=form.get("MediaContentType0") if num_media else None,
        # WhatsApp/Twilio entregan estas claves SOLO si el usuario comparte ubicación.
        latitude=(form.get("Latitude") or "").strip() or None,
        longitude=(form.get("Longitude") or "").strip() or None,
        address=(form.get("Address") or "").strip() or None,
    )


def validate_signature(url: str, params: dict[str, str], signature: str) -> bool:
    from app.config import settings

    creds = get_twilio_credentials()
    token = creds.get("auth_token")
    if not token:
        # Fail-closed: sin token no es posible verificar la firma → se rechaza
        # (anti-spoofing). Sólo en desarrollo (twilio_require_signature=False) se
        # permite continuar para no bloquear pruebas locales.
        if settings.twilio_require_signature:
            logger.error("twilio_token_missing_fail_closed")
            return False
        logger.warning("twilio_token_missing_skip_validation_dev")
        return True
    validator = RequestValidator(token)
    return validator.validate(url, params, signature or "")


def download_media(media_url: str) -> bytes | None:
    """Descarga media de Twilio (requiere auth básica con las credenciales)."""
    creds = get_twilio_credentials()
    sid, token = creds.get("account_sid"), creds.get("auth_token")
    if not (sid and token):
        logger.error("twilio_creds_missing_for_media")
        return None
    try:
        resp = httpx.get(media_url, auth=(sid, token), follow_redirects=True, timeout=30)
        resp.raise_for_status()
        return resp.content
    except Exception as exc:  # noqa: BLE001
        logger.error("media_download_failed", error=str(exc))
        return None


def build_text_response(text: str) -> str:
    resp = MessagingResponse()
    resp.message(text)
    return str(resp)


def build_voice_response(text: str, audio_url: str | None) -> str:
    """Responde con texto y, si hay audio, adjunta la nota de voz (media)."""
    resp = MessagingResponse()
    msg = resp.message(text)
    if audio_url:
        msg.media(audio_url)
    return str(resp)


def build_ack_response() -> str:
    """TwiML vacío: ack inmediato a Twilio. La respuesta real se envía aparte
    por la API REST (patrón asíncrono para no exceder el timeout del webhook)."""
    return str(MessagingResponse())


_WHATSAPP_MAX_CHARS = 1550  # margen bajo el límite real de Twilio (~1600 bytes UTF-8)


def _split_message(body: str, max_len: int = _WHATSAPP_MAX_CHARS) -> list[str]:
    """Divide un texto largo en varios mensajes de WhatsApp sin cortar a media frase.

    Prueba primero por párrafo ("\\n\\n"), luego por línea, y solo si un fragmento
    individual sigue excediendo `max_len` lo corta por palabra (nunca a mitad de
    una). Bug real: un `body[:1550]` cortaba la respuesta a mitad de frase sin
    avisar (ver `app.channels.twilio_whatsapp`); dividir en varios mensajes en
    vez de truncar preserva el contenido completo.
    """
    body = (body or "").strip()
    if not body:
        return [""]
    if len(body) <= max_len:
        return [body]

    chunks: list[str] = []
    current = ""
    for paragraph in body.split("\n\n"):
        candidate = f"{current}\n\n{paragraph}" if current else paragraph
        if len(candidate) <= max_len:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        if len(paragraph) <= max_len:
            current = paragraph
            continue
        # Un solo párrafo sigue excediendo el límite: se parte por palabra.
        words = paragraph.split(" ")
        piece = ""
        for word in words:
            candidate_piece = f"{piece} {word}" if piece else word
            if len(candidate_piece) <= max_len:
                piece = candidate_piece
            else:
                if piece:
                    chunks.append(piece)
                piece = word
        current = piece
    if current:
        chunks.append(current)
    return chunks or [body[:max_len]]


def send_whatsapp_message(to_number: str, body: str, audio_url: str | None = None,
                          image_url: str | None = None) -> bool:
    """Envía un mensaje saliente de WhatsApp por la API REST de Twilio.

    Se usa para responder de forma asíncrona tras procesar la consulta con el
    agente, evitando el límite de tiempo del webhook entrante. `image_url` es
    el gráfico (PNG con datos reales, ver `app.agent.tools.chart_tools`) que
    generó una tool en este turno, si la hubo; Twilio acepta varios
    `media_url` en el mismo mensaje, así que audio y gráfico pueden coexistir.

    Respuestas largas se dividen en varios mensajes secuenciales (ver
    `_split_message`) en vez de truncarse: el contenido completo del agente
    siempre debe llegar al usuario. El media (audio/gráfico) se adjunta solo
    al último fragmento, para que aparezca tras el texto completo.
    """
    creds = get_twilio_credentials()
    sid, token = creds.get("account_sid"), creds.get("auth_token")
    from_number = creds.get("whatsapp_number")
    if not (sid and token and from_number):
        logger.error("twilio_send_creds_missing")
        return False
    if from_number and not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"
    try:
        from twilio.base import values
        from twilio.rest import Client

        client = Client(sid, token)
        media = [u for u in (audio_url, image_url) if u]
        chunks = _split_message(body or "")
        ok = True
        for i, chunk in enumerate(chunks):
            is_last = i == len(chunks) - 1
            msg = client.messages.create(
                from_=from_number, to=to_number, body=chunk,
                media_url=media if (media and is_last) else values.unset,
            )
            logger.info("whatsapp_sent", sid=msg.sid, part=i + 1, parts=len(chunks))
        return ok
    except Exception as exc:  # noqa: BLE001
        logger.error("whatsapp_send_failed", error=str(exc))
        return False


def _sanitize_var(value: str, *, max_len: int = 600) -> str:
    """Adecúa un valor a las reglas de variables de plantilla de WhatsApp.

    WhatsApp no admite saltos de línea, tabuladores ni espacios múltiples dentro
    de una variable de plantilla; se colapsan a un espacio y se recorta la longitud.
    """
    text = re.sub(r"\s+", " ", value or "").strip()
    return text[:max_len]


def send_whatsapp_template(to_number: str, content_sid: str,
                           variables: dict[str, str]) -> bool:
    """Envía una plantilla de WhatsApp aprobada (Content API de Twilio).

    Necesario para mensajes de iniciativa (push) fuera de la ventana de 24 h: las
    reglas de WhatsApp solo permiten plantillas pre-aprobadas en ese caso. Las
    claves de `variables` son los índices de la plantilla ('1', '2', ...) y sus
    valores se sanitizan para cumplir las restricciones de formato.
    """
    creds = get_twilio_credentials()
    sid, token = creds.get("account_sid"), creds.get("auth_token")
    from_number = creds.get("whatsapp_number")
    if not (sid and token and from_number):
        logger.error("twilio_send_creds_missing")
        return False
    if not from_number.startswith("whatsapp:"):
        from_number = f"whatsapp:{from_number}"
    clean = {k: _sanitize_var(v) for k, v in variables.items()}
    try:
        from twilio.rest import Client

        client = Client(sid, token)
        msg = client.messages.create(
            from_=from_number,
            to=to_number,
            content_sid=content_sid,
            content_variables=json.dumps(clean, ensure_ascii=False),
        )
        logger.info("whatsapp_template_sent", sid=msg.sid)
        return True
    except Exception as exc:  # noqa: BLE001
        logger.error("whatsapp_template_send_failed", error=str(exc))
        return False
