"""Speech-to-Text: transcribe audio a texto vía Gemini (Vertex AI Model Garden).

Antes usaba Cloud Speech-to-Text v1, pero ese API solo soporta el modelo
"default" (el más básico) para es-PE -"latest_long" devuelve HTTP 400 para ese
locale- y exige sample_rate_hertz explícito para OGG_OPUS: una combinación
frágil ante variaciones del audio real entregado por Twilio/el navegador.
Gemini recibe el audio directamente como contenido multimodal (base64 inline),
transcribe en un solo paso y no tiene esa restricción de modelo por locale.

Dos orígenes:
- WhatsApp (Twilio) entrega notas de voz como audio/ogg (codec Opus).
- La UI web/escritorio graba con MediaRecorder (audio/webm, codec Opus).
"""
from __future__ import annotations

import base64

from langchain_core.messages import HumanMessage

from app.agent.models import invoke_with_failover
from app.observability import get_logger

logger = get_logger(__name__)

_MIME_BY_ENCODING = {
    "ogg_opus": "audio/ogg",
    "webm_opus": "audio/webm",
}

_TRANSCRIBE_PROMPT = (
    "Transcribe literalmente el audio adjunto. Probablemente está en español "
    "(variante peruana), pero puede estar en otro idioma. Devuelve ÚNICAMENTE "
    "el texto transcrito tal cual se dijo -sin traducir, sin resumir, sin "
    "comentarios ni encabezados-. Si no logras entender nada, devuelve una "
    "cadena vacía."
)


def transcribe_audio(audio_bytes: bytes, *, encoding: str = "ogg_opus") -> str:
    """Transcribe audio Opus (OGG o WEBM) a texto vía Gemini. Devuelve '' si falla.

    encoding: "ogg_opus" (WhatsApp) o "webm_opus" (MediaRecorder del navegador).
    """
    mime_type = _MIME_BY_ENCODING.get(encoding, "audio/ogg")
    try:
        message = HumanMessage(content=[
            {"type": "text", "text": _TRANSCRIBE_PROMPT},
            {
                "type": "file",
                "mime_type": mime_type,
                "base64": base64.b64encode(audio_bytes).decode("ascii"),
            },
        ])
        response = invoke_with_failover([message], temperature=0.0)
        raw = getattr(response, "content", "") or ""
        text = raw.strip() if isinstance(raw, str) else str(raw).strip()
        logger.info("stt_transcribed", chars=len(text), encoding=encoding)
        return text
    except Exception as exc:  # noqa: BLE001
        logger.error("stt_failed", error=str(exc), encoding=encoding)
        return ""
