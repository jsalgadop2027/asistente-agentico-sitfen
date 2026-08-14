"""Comprensión de imágenes entrantes vía Gemini multimodal (Vertex AI).

El usuario puede enviar una FOTO por WhatsApp (una planta con síntomas, una plaga,
una etiqueta, un documento, una factura). Gemini recibe la imagen como contenido
multimodal (base64 inline) y devuelve una descripción/análisis en español que el
agente usa como contexto para responder fundamentado en el corpus. Es el mismo
patrón que la transcripción de voz (`app/voice/stt.py`): media → texto → agente.
"""
from __future__ import annotations

import base64

from langchain_core.messages import HumanMessage

from app.observability import get_logger

logger = get_logger(__name__)


_DESCRIBE_PROMPT = (
    "Eres un asistente agrícola experto en el arándano peruano, en el contexto del "
    "Fenómeno de El Niño. Observa la IMAGEN adjunta y descríbela de forma útil y "
    "objetiva en español:\n"
    "- Si es una planta, fruto o cultivo: describe su estado y cualquier síntoma, "
    "plaga, enfermedad o deficiencia nutricional visible.\n"
    "- Si es un documento, factura, etiqueta o certificado: resume su contenido y "
    "los datos clave (números, fechas, montos, requisitos).\n"
    "- En otros casos: describe objetivamente lo relevante para una Mype agrícola.\n"
    "No inventes lo que no puedas ver; si no estás seguro, dilo. Sé conciso "
    "(3 a 6 frases). Devuelve solo la descripción, sin encabezados."
)


def describe_image(image_bytes: bytes, *, mime_type: str = "image/jpeg",
                   caption: str = "") -> str:
    """Describe/analiza una imagen vía Gemini. Devuelve '' si falla (fail-open).

    `caption` es el texto que el usuario envió junto a la imagen; guía el análisis
    hacia su intención (p. ej. "¿qué le pasa a mi planta?").
    """
    prompt = _DESCRIBE_PROMPT
    if caption.strip():
        prompt = (
            f"{prompt}\n\nEl usuario escribió junto a la imagen: "
            f"\"{caption.strip()}\". Ten en cuenta su intención al analizarla."
        )
    try:
        from app.agent.models import invoke_with_failover

        message = HumanMessage(content=[
            {"type": "text", "text": prompt},
            {
                "type": "file",
                "mime_type": mime_type or "image/jpeg",
                "base64": base64.b64encode(image_bytes).decode("ascii"),
            },
        ])
        response = invoke_with_failover([message], temperature=0.2)
        raw = getattr(response, "content", "") or ""
        text = raw.strip() if isinstance(raw, str) else str(raw).strip()
        logger.info("image_described", chars=len(text), mime=mime_type)
        return text
    except Exception as exc:  # noqa: BLE001
        logger.error("vision_failed", error=str(exc))
        return ""
