"""Tool de generación de imágenes por IA (Vertex AI Imagen).

A diferencia de `chart_tools.py` (gráficos con datos REALES: temperatura del mar,
precipitación NOAA), esta tool genera una imagen ILUSTRATIVA a partir de una
descripción textual — útil para explicar visualmente una idea o técnica, nunca para
representar un dato real. Comparte con `chart_tools.py` el mismo mecanismo de
entrega: publica el PNG en el bucket privado (`media_upload.upload_image`) y anexa
la URL a su propio texto de retorno con el marcador '[GRAFICO_URL: ...]', que
`app.agent.translation.extract_chart_url` recupera del `ToolMessage` real al cierre
del turno (ver el porqué del marcador — LangGraph copia el contexto por hilo — en el
docstring de `chart_tools.py`). Al reusar el mismo marcador, todo el pipeline de
entrega a WhatsApp (`app.main`, `app.channels.twilio_whatsapp.send_whatsapp_message`)
funciona sin cambios: no necesita saber si la imagen es un gráfico de datos o una
ilustración generada.

Control de costo (OWASP LLM10, Unbounded Consumption — Imagen cobra por imagen
generada, a diferencia de matplotlib que es gratis): kill switch
(`settings.image_gen_enabled`) + cupo diario por usuario en Firestore
(`_check_daily_quota`, mismo patrón transaccional que `RateLimiter.allow` en
`app.agent.guardrails`, pero con ventana de día en hora de Lima en vez de minuto).

Seguridad de contenido: el filtro de Imagen (`safety_filter_level`,
`person_generation`) es la primera capa, igual que `SAFETY_SETTINGS` para Gemini en
`app.agent.models`; el prefijo de estilo fijo en `_build_prompt` acota el resultado a
una ILUSTRACIÓN del dominio agrícola/FEN, no una foto realista de personas o lugares.
"""
from __future__ import annotations

import functools

from langchain_core.tools import tool

from app.agent.tools.media_upload import upload_image
from app.config import settings
from app.observability import get_logger

logger = get_logger(__name__)

_ESTILO_PROMPT = (
    "Ilustración digital limpia y profesional para una Mype agrícola peruana del "
    "sector arándano, en el contexto del Fenómeno de El Niño. Tema: {tema}. Estilo "
    "esquemático/editorial, colores naturales, sin texto ni logotipos en la imagen."
)


def _build_prompt(descripcion: str) -> str:
    """Envuelve el tema pedido en un prefijo de estilo fijo (función pura).

    Mantiene el resultado como ILUSTRACIÓN (no foto realista de personas/lugares
    reales) y evita pedirle texto legible a Imagen (suele renderizarlo mal).
    """
    tema = (descripcion or "").strip() or "el sector arándano peruano"
    return _ESTILO_PROMPT.format(tema=tema)


@functools.lru_cache(maxsize=1)
def _usage_db():
    from google.cloud import firestore

    return firestore.Client(project=settings.gcp_project_id)


def _check_daily_quota(user_id: str | None) -> bool:
    """True si el usuario aún tiene cupo de imágenes hoy (hora de Lima).

    Fail-open (True) si Firestore falla o no hay `user_id` (sesión web anónima) —
    mismo criterio que `RateLimiter.allow` (`app.agent.guardrails`): un problema de
    infraestructura ajeno al usuario no debe romper la conversación.
    """
    if not user_id:
        return True
    from google.cloud import firestore

    from app.concerns import lima_day_str

    doc_id = f"{user_id}:{lima_day_str()}"
    try:
        ref = (_usage_db().collection(settings.firestore_image_gen_usage_collection)
               .document(doc_id))

        @firestore.transactional
        def _txn(txn):
            snap = ref.get(transaction=txn)
            count = (snap.to_dict() or {}).get("count", 0) if snap.exists else 0
            if count >= settings.image_gen_max_per_day:
                return False
            txn.set(ref, {"count": count + 1, "day": lima_day_str()}, merge=True)
            return True

        return _txn(_usage_db().transaction())
    except Exception as exc:  # noqa: BLE001
        logger.warning("image_gen_quota_check_failed", error=str(exc))
        return True


@tool
def generar_imagen(descripcion: str) -> str:
    """Genera y ENVÍA (como imagen) una ilustración creada por IA —NO un dato
    real— para explicar visualmente una idea, técnica o concepto del ámbito
    agrícola/comercial del arándano peruano o del Fenómeno de El Niño (p. ej. un
    diagrama de poda, un esquema de riego por goteo, una ilustración
    motivacional). NO la uses para datos reales de clima o mar (usa
    "graficar_temperatura_mar" o "graficar_precipitacion") ni para analizar una
    foto real que haya enviado el usuario. Úsala solo cuando el usuario pida
    explícitamente una imagen, ilustración o diagrama generado por IA.
    `descripcion` es el tema a ilustrar, en pocas palabras."""
    if not settings.image_gen_enabled:
        return "La generación de imágenes por IA no está disponible en este momento."

    from app.agent.turn_context import get_current_user_id

    if not _check_daily_quota(get_current_user_id()):
        return (f"Ya generaste el máximo de imágenes permitidas hoy "
                f"({settings.image_gen_max_per_day}). Intenta de nuevo mañana.")

    prompt = _build_prompt(descripcion)
    try:
        from vertexai.preview.vision_models import ImageGenerationModel

        from app.agent.models import init_vertex

        init_vertex()
        model = ImageGenerationModel.from_pretrained(settings.imagen_model)
        result = model.generate_images(
            prompt=prompt,
            number_of_images=1,
            aspect_ratio="1:1",
            safety_filter_level="block_some",
            person_generation="allow_adult",
            add_watermark=True,
        )
        if not result.images:
            raise ValueError("Imagen no devolvió ninguna imagen")
        png = result.images[0]._image_bytes  # noqa: SLF001 (API pública indirecta del SDK)
    except Exception as exc:  # noqa: BLE001
        logger.warning("image_generation_failed", error=str(exc))
        return ("No pude generar la imagen ahora mismo. ¿Quieres que lo intente "
                "de nuevo o prefieres que te lo explique en texto?")

    url = upload_image(png, prefix="images")
    if not url:
        return ("Generé la imagen pero no pude publicarla ahora mismo. ¿Quieres "
                "que lo intente de nuevo?")
    return f"🖼️ Imagen generada: {descripcion.strip()}.\n\n[GRAFICO_URL: {url}]"
