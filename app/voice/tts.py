"""Text-to-Speech: sintetiza la respuesta y la publica en GCS con URL firmada.

Twilio WhatsApp requiere una URL públicamente accesible para enviar media; por
eso se sube el MP3 a un bucket y se genera una URL firmada de corta duración
(privacidad: el objeto no es público y la URL expira).
"""
from __future__ import annotations

import uuid

from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)


def synthesize_speech(text: str, *, language: str | None = None,
                      voice_name: str | None = None) -> bytes | None:
    """Convierte texto a audio MP3. Devuelve bytes o None si falla."""
    language = language or settings.tts_language
    voice_name = voice_name or settings.tts_voice
    try:
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()
        synthesis_input = texttospeech.SynthesisInput(text=text[:1500])
        voice = texttospeech.VoiceSelectionParams(
            language_code=language, name=voice_name
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=1.0,
        )
        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        return response.audio_content
    except Exception as exc:  # noqa: BLE001
        logger.error("tts_failed", error=str(exc))
        return None


def synthesize_ssml_with_marks(ssml: str, *, language: str | None = None,
                               voice_name: str | None = None):
    """Sintetiza SSML y devuelve (audio_mp3_bytes, timepoints).

    Usa la API v1beta1 con time-pointing sobre marcas SSML, lo que permite al
    avatar web (TalkingHead.js) sincronizar los labios por palabra. Devuelve
    (b'', []) si falla.
    """
    language = language or settings.tts_language
    voice_name = voice_name or settings.tts_voice
    try:
        from google.cloud import texttospeech_v1beta1 as tts

        client = tts.TextToSpeechClient()
        request = tts.SynthesizeSpeechRequest(
            input=tts.SynthesisInput(ssml=ssml),
            voice=tts.VoiceSelectionParams(language_code=language, name=voice_name),
            audio_config=tts.AudioConfig(audio_encoding=tts.AudioEncoding.MP3),
            enable_time_pointing=[
                tts.SynthesizeSpeechRequest.TimepointType.SSML_MARK
            ],
        )
        response = client.synthesize_speech(request=request)
        timepoints = [{"markName": tp.mark_name, "timeSeconds": tp.time_seconds}
                      for tp in response.timepoints]
        return response.audio_content, timepoints
    except Exception as exc:  # noqa: BLE001
        logger.error("tts_ssml_failed", error=str(exc))
        return b"", []


def synthesize_to_signed_url(text: str) -> str | None:
    """Sintetiza voz, sube a GCS y devuelve una URL firmada temporal (o None)."""
    audio = synthesize_speech(text)
    if not audio:
        return None
    try:
        from datetime import timedelta

        import google.auth
        from google.auth.transport import requests as google_requests
        from google.cloud import storage

        client = storage.Client()
        bucket = client.bucket(settings.gcs_audio_bucket)
        blob = bucket.blob(f"responses/{uuid.uuid4().hex}.mp3")
        blob.upload_from_string(audio, content_type="audio/mpeg")

        # En Cloud Run las credenciales ambiente solo traen un token (sin
        # llave privada): generate_signed_url() no puede firmar localmente.
        # Se delega la firma a la API de IAM (signBlob) pasando el email y un
        # access token explícitos; requiere roles/iam.serviceAccountTokenCreator
        # sobre la propia SA.
        credentials, _ = google.auth.default()
        credentials.refresh(google_requests.Request())
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=settings.signed_url_ttl_seconds),
            method="GET",
            service_account_email=credentials.service_account_email,
            access_token=credentials.token,
        )
        logger.info("tts_uploaded", bytes=len(audio))
        return url
    except Exception as exc:  # noqa: BLE001
        logger.error("tts_upload_failed", error=str(exc))
        return None
