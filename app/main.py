"""Servicio FastAPI: webhook de WhatsApp (Twilio) + health checks.

Despliega en Cloud Run. Patrón ASÍNCRONO (clave para no exceder el timeout del
webhook de Twilio, ~10-15 s, frente al tiempo del RAG agéntico + arranque en frío):

  1. Valida la firma de Twilio (seguridad).
  2. Responde de inmediato con un ack (TwiML vacío) -> Twilio queda satisfecho.
  3. En segundo plano: transcribe voz (si aplica), ejecuta el orquestador agéntico
     y ENVÍA la respuesta por la API REST de Twilio (texto y, si hubo voz, audio).
"""
from __future__ import annotations

import base64
import os
from contextlib import asynccontextmanager
from functools import lru_cache

from fastapi import BackgroundTasks, FastAPI, Header, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.channels.twilio_whatsapp import (
    build_ack_response,
    download_media,
    parse_incoming,
    send_whatsapp_message,
    validate_signature,
)
from app.config import settings
from app.kb_broadcast import SIGNATURE
from app.observability import configure_observability, get_logger

configure_observability()
logger = get_logger(__name__)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    # Índice BM25 (Hybrid Search del retriever): tarda decenas de segundos en
    # construirse (pagina ~20 000 chunks de Firestore), así que se lanza en un
    # hilo de fondo AQUÍ (arranque del contenedor) en vez de al vuelo en la
    # primera petición — el health check y las primeras consultas no esperan
    # por él; mientras no esté listo, el retriever sigue solo con búsqueda
    # vectorial (ver app.agent.bm25_index).
    from app.agent import bm25_index

    bm25_index.ensure_index_building()
    yield


app = FastAPI(title="Chatbot Agéntico RAG - Arándano Peruano", version="0.1.0",
              lifespan=_lifespan)

# Firma de autoría al pie de cada respuesta de texto (web y WhatsApp). No se
# incluye en la voz/TTS para no leerla en voz alta. Definida en app.kb_broadcast
# (fuente única) y reexportada aquí.

# Encabezado institucional al inicio de CADA respuesta del bot por WhatsApp
# (texto Y voz/TTS, a diferencia de SIGNATURE que solo va en el texto).
WHATSAPP_INTRO = "ITP y Red CITE a tu disposición."


# --- Modelos de request (validación idiomática de FastAPI/pydantic) ---
class ChatRequest(BaseModel):
    """Cuerpo del endpoint /api/chat del canal web."""
    message: str = Field(default="", max_length=4000)
    session_id: str = Field(default="anon", max_length=64)


class KbAckRequest(BaseModel):
    """Cuerpo del endpoint /api/kb/ack."""
    source: str = Field(default="", max_length=512)


class IdentifyRequest(BaseModel):
    """Cuerpo del endpoint /api/identify (código interno de 8 caracteres)."""
    code: str = Field(default="", max_length=16)

# CORS para el canal web (avatar). El avatar se sirve desde /app/ (MISMO origen
# que la API), por lo que no requiere CORS. Se restringe a una allowlist explícita
# (env CORS_ALLOW_ORIGINS, coma-separada); vacío = sin cross-origin. Se elimina el
# comodín "*" y las credenciales para minimizar la superficie de ataque.
_cors_origins = [o.strip() for o in (settings.cors_allow_origins or "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    allow_credentials=False,
)


@app.get("/health")
def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "service": "arandano-agent",
                         "env": settings.environment})


@app.get("/")
def root() -> JSONResponse:
    return JSONResponse({"service": "Chatbot Agéntico RAG - Arándano Peruano",
                         "version": "0.1.0", "web": "/app/"})


# --------------------------------------------------------------------------
#  Canal WEB (presentador virtual con avatar 3D)
# --------------------------------------------------------------------------
@app.post("/api/chat")
async def api_chat(req: ChatRequest) -> JSONResponse:
    """Conversación por web: usa el mismo orquestador agéntico que WhatsApp."""
    message = req.message.strip()
    session = (req.session_id or "anon")[:64]
    if not message:
        return JSONResponse({"reply": "Escribe una consulta, por favor.",
                             "blocked": True, "footer": SIGNATURE})
    from app.agent.orchestrator import get_orchestrator
    from app.user_registry import looks_like_code

    # Si el visitante se identificó con su código interno, la sesión se ancla a
    # ese código (igual que en WhatsApp): eso habilita memoria, personalización y
    # seguimiento de sus inquietudes. Si no, sesión anónima con prefijo "web:".
    user_id = session if looks_like_code(session) else f"web:{session}"
    resp = get_orchestrator().answer(user_id, message)
    return JSONResponse({"reply": resp.text, "blocked": resp.blocked,
                         "footer": SIGNATURE, "chart_url": resp.chart_url})


@app.get("/api/kb/pending")
async def api_kb_pending() -> JSONResponse:
    """Novedad pendiente de anunciar: último documento vectorizado no anunciado.

    El canal web (avatar) consulta este endpoint periódicamente; si hay un
    documento nuevo, lo anuncia por texto y voz y ofrece presentarlo.
    """
    try:
        from app.kb_events import KBEventStore

        event = KBEventStore().latest_pending()
    except Exception as exc:  # noqa: BLE001
        logger.warning("kb_pending_failed", error=str(exc))
        return JSONResponse({"pending": False})
    if not event:
        return JSONResponse({"pending": False})
    return JSONResponse({
        "pending": True,
        "source": event.source,
        "title": event.title,
        "chunks": event.chunks,
    })


@app.post("/api/kb/ack")
async def api_kb_ack(req: KbAckRequest) -> JSONResponse:
    """Marca una novedad como ya anunciada para no repetir el aviso."""
    source = req.source.strip()
    if not source:
        return JSONResponse({"ok": False}, status_code=400)
    try:
        from app.kb_events import KBEventStore

        KBEventStore().mark_announced(source)
    except Exception as exc:  # noqa: BLE001
        logger.warning("kb_ack_failed", error=str(exc))
        return JSONResponse({"ok": False})
    return JSONResponse({"ok": True})


@app.get("/api/proactive/pending")
async def api_proactive_pending(session_id: str = "") -> JSONResponse:
    """Siguiente aviso que el agente da por INICIATIVA PROPIA en el avatar.

    Unifica las señales proactivas: alerta temprana del FEN (anomalía SST),
    novedad de la base de conocimiento y seguimiento de una inquietud abierta
    del usuario identificado. Ver `app.proactive`. Fail-open.
    """
    try:
        from app.proactive import pending_nudges

        nudges = pending_nudges((session_id or "")[:64])
    except Exception as exc:  # noqa: BLE001
        logger.warning("proactive_pending_failed", error=str(exc))
        return JSONResponse({"pending": False, "items": []})
    # Se devuelven TODOS los pendientes: el cliente anuncia el primero que aún no
    # haya dado (deduplica por `key`), de modo que un aviso ya anunciado no
    # bloquee a los de menor prioridad.
    return JSONResponse({"pending": bool(nudges),
                         "items": [n.as_dict() for n in nudges]})


@lru_cache(maxsize=1)
def _identify_limiter():
    from app.agent.guardrails import RateLimiter

    return RateLimiter()


@app.post("/api/fen-briefing")
async def api_fen_briefing(request: Request) -> JSONResponse:
    """Boletín bajo demanda sobre el FEN (botón de proactividad del avatar).

    Consulta la web abierta vía Grounding con Google Search de Gemini (ver
    `app.agent.fen_briefing`) y devuelve SIEMPRE la fuente junto al texto.
    Aislado del orquestador conversacional (no pasa por `AgentOrchestrator`).
    Limitado por IP (mismo limitador que /api/identify, distinto prefijo de
    clave) porque cada llamada dispara una consulta a un LLM con búsqueda.
    """
    fwd = (request.headers.get("x-forwarded-for", "") or "").split(",")[0].strip()
    ip = fwd or (request.client.host if request.client else "desconocida")
    if not _identify_limiter().allow(f"fenbrief:{ip}"):
        logger.warning("fen_briefing_rate_limited")
        return JSONResponse({"text": "Demasiadas solicitudes seguidas. Espera un momento.",
                             "sources": []}, status_code=429)
    from app.agent.fen_briefing import generate_fen_briefing

    briefing = generate_fen_briefing()
    return JSONResponse({
        "text": briefing.text,
        "sources": [{"title": s.title, "uri": s.uri, "domain": s.domain}
                    for s in briefing.sources],
    })


@app.post("/api/identify")
async def api_identify(req: IdentifyRequest, request: Request) -> JSONResponse:
    """Identifica al visitante del avatar con su código interno de 8 caracteres.

    Ancla la sesión web a ese código y habilita el acompañamiento personalizado
    (memoria, objetivo de negocio, seguimiento de inquietudes), igual que en
    WhatsApp. Limitado por IP para encarecer la enumeración de códigos.
    """
    code = (req.code or "").strip().upper()
    fwd = (request.headers.get("x-forwarded-for", "") or "").split(",")[0].strip()
    ip = fwd or (request.client.host if request.client else "desconocida")
    if not _identify_limiter().allow(f"identify:{ip}"):
        logger.warning("identify_rate_limited")
        return JSONResponse({"ok": False, "error": "demasiados intentos"},
                            status_code=429)

    from app.user_registry import get_user_registry, looks_like_code

    if not looks_like_code(code):
        return JSONResponse({"ok": False})
    try:
        user = get_user_registry().get_by_code(code)
    except Exception as exc:  # noqa: BLE001
        logger.warning("identify_lookup_failed", error=str(exc))
        return JSONResponse({"ok": False})
    if user is None or not user.active:
        logger.info("identify_failed")
        return JSONResponse({"ok": False})
    logger.info("identify_ok", code=user.code)
    return JSONResponse({"ok": True, "session_id": user.code,
                         "nombre": user.nombre})


@app.post("/api/tts")
async def api_tts(request: Request) -> JSONResponse:
    """Proxy de Google TTS en formato compatible con TalkingHead.js.

    Recibe el cuerpo que envía el avatar (input.ssml con marcas + voice) y
    devuelve {audioContent (base64 MP3), timepoints}. Mantiene las credenciales
    en el servidor (no se expone API key en el navegador).
    """
    body = await request.json()
    ssml = (body.get("input") or {}).get("ssml")
    if not ssml:
        text = (body.get("input") or {}).get("text", "")
        ssml = f"<speak>{text}</speak>"
    voice = body.get("voice") or {}
    from app.voice.tts import synthesize_ssml_with_marks

    audio, timepoints = synthesize_ssml_with_marks(
        ssml, language=voice.get("languageCode"), voice_name=voice.get("name"))
    return JSONResponse({
        "audioContent": base64.b64encode(audio).decode("ascii"),
        "timepoints": timepoints,
    })


@app.post("/api/voice")
async def api_voice(request: Request) -> Response:
    """Fallback: devuelve MP3 plano de un texto (si el avatar 3D no carga)."""
    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return PlainTextResponse("texto vacío", status_code=400)
    from app.voice.tts import synthesize_speech

    audio = synthesize_speech(text)
    if not audio:
        return PlainTextResponse("tts no disponible", status_code=503)
    return Response(content=audio, media_type="audio/mpeg")


@app.post("/api/stt")
async def api_stt(request: Request) -> JSONResponse:
    """Transcribe audio grabado en la UI (MediaRecorder → audio/webm Opus).

    Permite la voz de entrada en web y escritorio sin depender de la Web Speech
    API del navegador (que no funciona en Electron). El cliente envía los bytes
    crudos del audio; el Content-Type indica el contenedor (webm u ogg).
    """
    if not settings.voice_enabled:
        return JSONResponse({"text": "", "error": "voice_disabled"}, status_code=503)
    audio = await request.body()
    if not audio:
        return JSONResponse({"text": "", "error": "empty_audio"}, status_code=400)
    ctype = (request.headers.get("content-type") or "").lower()
    encoding = "ogg_opus" if "ogg" in ctype else "webm_opus"
    from app.voice.stt import transcribe_audio

    text = transcribe_audio(audio, encoding=encoding)
    return JSONResponse({"text": text})


# --------------------------------------------------------------------------
#  Trigger de Eventarc: difusión automática de novedades por WhatsApp
# --------------------------------------------------------------------------
def _verify_eventarc_token(request: Request) -> bool:
    """Valida que la petición venga de Eventarc (token OIDC firmado por Google).

    El endpoint es público (el servicio permite no-autenticados para Twilio), así
    que se protege aquí verificando el token OIDC que Eventarc adjunta al invocar.
    """
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return False
    token = auth.split(" ", 1)[1].strip()
    try:
        from google.auth.transport import requests as ga_requests
        from google.oauth2 import id_token

        claims = id_token.verify_oauth2_token(token, ga_requests.Request())
    except Exception as exc:  # noqa: BLE001
        logger.warning("eventarc_token_invalid", error=str(exc))
        return False
    if not claims.get("email_verified"):
        return False
    email = claims.get("email", "")
    expected = settings.eventarc_service_account
    if expected:
        return email == expected
    # Sin SA configurada: al menos exige una cuenta de servicio de Google.
    return email.endswith(".gserviceaccount.com")


def _run_kb_broadcast(doc_id: str) -> None:
    """Difunde en segundo plano el resumen del documento recién ingestado."""
    try:
        from app.kb_broadcast import broadcast_event

        broadcast_event(doc_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("kb_broadcast_trigger_failed", doc_id=doc_id, error=str(exc))


@app.post("/internal/kb-broadcast")
async def kb_broadcast_trigger(request: Request,
                               background_tasks: BackgroundTasks) -> Response:
    """Disparador de Firestore/Eventarc: al crearse/actualizarse un documento en
    la colección `kb_events` (ingesta nueva), difunde por WhatsApp su resumen a los
    usuarios suscritos. Idempotente: `broadcast_event` reclama el evento una sola
    vez por ingesta, así reintentos y el envío manual no duplican el mensaje."""
    if not _verify_eventarc_token(request):
        return PlainTextResponse("unauthorized", status_code=401)
    # El path del documento viaja en el atributo CloudEvent 'subject':
    #   'documents/kb_events/{docId}'
    subject = request.headers.get("ce-subject", "")
    doc_id = subject.rsplit("/", 1)[-1] if "/" in subject else ""
    if not doc_id:
        logger.warning("kb_trigger_no_subject", subject=subject)
        return Response(status_code=204)
    background_tasks.add_task(_run_kb_broadcast, doc_id)
    return Response(status_code=204)


# --------------------------------------------------------------------------
#  Informe diario de inquietudes (#8): Cloud Scheduler -> correo (SendGrid)
# --------------------------------------------------------------------------
def _run_daily_report() -> None:
    """Genera y envía el informe diario de inquietudes en segundo plano."""
    try:
        from app.daily_report import send_daily_report

        send_daily_report()
    except Exception as exc:  # noqa: BLE001
        logger.error("daily_report_trigger_failed", error=str(exc))


@app.post("/internal/daily-report")
async def daily_report_trigger(request: Request,
                               background_tasks: BackgroundTasks) -> Response:
    """Disparador de Cloud Scheduler (20:00 America/Lima): compone y envía por
    correo el informe de reclamos/pedidos/sugerencias/recomendaciones del día.
    Protegido por OIDC igual que /internal/kb-broadcast (el servicio es público
    para Twilio, así que se verifica el token de la cuenta de servicio)."""
    if not _verify_eventarc_token(request):
        return PlainTextResponse("unauthorized", status_code=401)
    background_tasks.add_task(_run_daily_report)
    return Response(status_code=204)


# --------------------------------------------------------------------------
#  Proactividad iniciada: alerta satelital SST (#4) y reenganche
# --------------------------------------------------------------------------
def _run_sst_alert() -> None:
    """Comprueba la anomalía SST y difunde la alerta en segundo plano."""
    try:
        from app.sst_alert import run_sst_alert

        run_sst_alert()
    except Exception as exc:  # noqa: BLE001
        logger.error("sst_alert_trigger_failed", error=str(exc))


@app.post("/internal/sst-alert")
async def sst_alert_trigger(request: Request,
                            background_tasks: BackgroundTasks) -> Response:
    """Disparador de Cloud Scheduler: si la anomalía SST del norte es significativa
    y escala de nivel, difunde una alerta de El Niño Costero por WhatsApp (plantilla).
    Protegido por OIDC igual que /internal/kb-broadcast."""
    if not _verify_eventarc_token(request):
        return PlainTextResponse("unauthorized", status_code=401)
    background_tasks.add_task(_run_sst_alert)
    return Response(status_code=204)


def _run_reengagement() -> None:
    """Reengancha a usuarios inactivos en segundo plano."""
    try:
        from app.reengagement import run_reengagement

        run_reengagement()
    except Exception as exc:  # noqa: BLE001
        logger.error("reengage_trigger_failed", error=str(exc))


@app.post("/internal/re-engage")
async def reengage_trigger(request: Request,
                           background_tasks: BackgroundTasks) -> Response:
    """Disparador de Cloud Scheduler: envía una plantilla de reenganche a los
    usuarios activos con opt-in que llevan varios días sin actividad. OIDC."""
    if not _verify_eventarc_token(request):
        return PlainTextResponse("unauthorized", status_code=401)
    background_tasks.add_task(_run_reengagement)
    return Response(status_code=204)


def _process_and_reply(form: dict) -> None:
    """Procesa la consulta y envía la respuesta por la API REST (en background)."""
    try:
        incoming = parse_incoming(form)
        was_voice = False
        was_image = False
        user_text = incoming.body

        # Ubicación compartida -> consulta de clima por coordenadas (geoposición).
        # Se pasan las coordenadas al agente para que invoque la tool consultar_clima.
        if incoming.is_location:
            coords = f"{incoming.latitude},{incoming.longitude}"
            base = incoming.body or "¿Qué clima hace en mi ubicación actual?"
            user_text = f"{base} (coordenadas del usuario: {coords})"

        # Nota de voz -> transcripción.
        if incoming.is_voice and settings.voice_enabled and incoming.media_url:
            from app.voice.stt import transcribe_audio

            audio = download_media(incoming.media_url)
            if audio:
                user_text = transcribe_audio(audio)
                was_voice = True

        # Imagen -> descripción/análisis multimodal (mismo patrón que la voz).
        # El caption (si lo hay) guía el análisis y encabeza la consulta al agente.
        elif incoming.is_image and settings.vision_enabled and incoming.media_url:
            img = download_media(incoming.media_url)
            if img and len(img) <= settings.vision_max_bytes:
                from app.vision.describe import describe_image

                desc = describe_image(
                    img, mime_type=incoming.media_content_type or "image/jpeg",
                    caption=incoming.body,
                )
                if desc:
                    was_image = True
                    caption = incoming.body.strip()
                    if caption:
                        user_text = (
                            f"{caption}\n\n[El usuario adjuntó una imagen. Análisis "
                            f"de la imagen: {desc}]"
                        )
                    else:
                        user_text = (
                            f"[El usuario envió una imagen, sin texto. Análisis de la "
                            f"imagen: {desc}] Responde de forma útil según lo que "
                            f"muestra la imagen."
                        )
            elif img:
                logger.warning("vision_image_too_large", bytes=len(img))

        if not user_text:
            send_whatsapp_message(
                incoming.from_number,
                f"{WHATSAPP_INTRO}\n\nNo pude entender tu mensaje. ¿Puedes "
                f"escribirlo o enviarlo de nuevo?",
            )
            return

        # Medio de ENTRADA real del turno ("texto"/"voz"/"imagen"): tanto la nota
        # de voz como la imagen ya llegan a `user_text` como texto plano (STT o
        # descripción), así que sin esto el origen real se perdía por completo
        # de cara a los reportes del Admin UI y al correo de derivación (ver
        # `app.attentions` y `app.agent.turn_context`).
        medio = "voz" if was_voice else ("imagen" if was_image else "texto")

        # Control de sesión por usuario: si el número está registrado y activo,
        # la sesión se ancla a su CÓDIGO INTERNO (estable) en lugar del teléfono;
        # si no, se usa el número (comportamiento previo, no rompe a no-registrados).
        session_id = incoming.user_id
        try:
            from app.user_registry import get_user_registry

            session_id = get_user_registry().resolve_session(incoming.user_id)
        except Exception as exc:  # noqa: BLE001
            logger.warning("session_resolve_failed", error=str(exc))

        # --- Consola en vivo (handoff): espeja el entrante y captura el número.
        # Si un humano "tomó" la conversación desde la web (pausada), el bot NO
        # auto-responde. Fail-open: cualquier error aquí no interrumpe el flujo.
        try:
            from app.agent.live_console import get_live_store, live_token

            if live_token():  # activo solo si LIVE_CONSOLE_TOKEN está configurado
                _live = get_live_store()
                _live.capture_number(incoming.from_number)
                _kind = "voice" if was_voice else ("image" if was_image else "text")
                _live.mirror_in(user_text, kind=_kind)
                if _live.is_paused():
                    logger.info("live_handoff_active_skip_autoreply")
                    return
        except Exception as exc:  # noqa: BLE001
            logger.warning("live_mirror_in_failed", error=str(exc))

        # Orquestador agéntico (RAG + tools + guardrails + memoria).
        from app.agent.orchestrator import get_orchestrator

        # Aviso de "procesando" solo para el tier Pro (razonamiento con más
        # tools/latencia): en Flash el turno suele resolverse tan rápido que el
        # aviso llegaría después que la propia respuesta. Se envía ANTES de
        # invocar al agente (ver `on_before_agent` en orchestrator.answer).
        def _notify_processing(pro: bool) -> None:
            if pro:
                send_whatsapp_message(
                    incoming.from_number,
                    f"{WHATSAPP_INTRO}\n\n🔎 Un momento, estoy revisando tu consulta...",
                )

        response = get_orchestrator().answer(
            session_id, user_text, on_before_agent=_notify_processing, medio=medio)

        # Registro de la atención (#Admin UI "Atenciones Normales"): CADA turno de
        # WhatsApp que se respondió sin bloqueo, no solo los que `app.concerns`
        # clasifica como punto de dolor. Fire-and-forget (ver app.attentions).
        if not response.blocked:
            from app.attentions import record_attention_async

            record_attention_async(session_id, user_text, medio=medio)

        # Voz de salida (si la entrada fue voz y no fue bloqueada). Lleva el mismo
        # encabezado institucional que el texto (WHATSAPP_INTRO).
        audio_url = None
        if was_voice and settings.voice_enabled and not response.blocked:
            from app.voice.tts import synthesize_to_signed_url

            audio_url = synthesize_to_signed_url(f"{WHATSAPP_INTRO} {response.text}")

        send_whatsapp_message(
            incoming.from_number,
            f"{WHATSAPP_INTRO}\n\n{response.text}", audio_url,
            response.chart_url)

        # Espejo de la respuesta del bot para la consola en vivo (fail-open).
        try:
            from app.agent.live_console import get_live_store, live_token

            if live_token():
                get_live_store().mirror_out(response.text, kind="bot", media_url=audio_url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("live_mirror_out_failed", error=str(exc))
    except Exception as exc:  # noqa: BLE001
        logger.error("process_and_reply_failed", error=str(exc))


@app.post("/webhook/whatsapp")
async def whatsapp_webhook(request: Request, background_tasks: BackgroundTasks,
                           x_twilio_signature: str = Header(default="")) -> Response:
    form = dict(await request.form())

    # 1) Validación de firma (anti-spoofing). Tras el proxy de Cloud Run,
    # reconstruimos la URL pública con X-Forwarded-Proto para que coincida con
    # la URL sobre la que Twilio calculó la firma.
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("host", request.url.netloc)
    url = f"{proto}://{host}{request.url.path}"
    if not validate_signature(url, form, x_twilio_signature):
        logger.warning("invalid_twilio_signature", url=url)
        return PlainTextResponse("invalid signature", status_code=403)

    incoming = parse_incoming(form)
    if not incoming.from_number:
        return PlainTextResponse("bad request", status_code=400)

    # 2) Ack inmediato + 3) procesamiento en segundo plano.
    background_tasks.add_task(_process_and_reply, form)
    return Response(content=build_ack_response(), media_type="application/xml")


# --- Consola en vivo (handoff WhatsApp ↔ web), un solo usuario ----------------
# Endpoints consumidos por la consola web (a través del proxy de arandano-sst-web).
# Gated por token compartido en el header X-Live-Token. Solo envían al número
# vinculado (capturado del webhook), nunca a terceros.
def _live_authorized(token: str) -> bool:
    from app.agent.live_console import live_token

    expected = live_token()
    return bool(expected) and token == expected


@app.get("/api/live/messages")
def live_messages(since: int = 0, x_live_token: str = Header(default="")):
    if not _live_authorized(x_live_token):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    from app.agent.live_console import get_live_store, mask_number

    store = get_live_store()
    return {
        "messages": store.list_messages(since_ms=since),
        "paused": store.is_paused(),
        "linked": mask_number(store.linked_number()),
    }


@app.post("/api/live/send")
async def live_send(request: Request, x_live_token: str = Header(default="")):
    if not _live_authorized(x_live_token):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    from app.agent.live_console import get_live_store

    body = await request.json()
    text = (body.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "empty"}, status_code=400)
    store = get_live_store()
    to = store.linked_number()
    if not to:
        return JSONResponse(
            {"error": "sin número vinculado; envía un WhatsApp al bot primero"},
            status_code=409,
        )
    ok = send_whatsapp_message(to, text)  # sin firma: es mensaje humano
    if ok:
        store.mirror_out(text, kind="human")
    return {"sent": ok}


@app.post("/api/live/pause")
async def live_pause(request: Request, x_live_token: str = Header(default="")):
    if not _live_authorized(x_live_token):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    from app.agent.live_console import get_live_store

    body = await request.json()
    store = get_live_store()
    store.set_paused(bool(body.get("paused")))
    return {"paused": store.is_paused()}


# Servir la interfaz web del avatar (si está presente en la imagen).
_WEB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "web")
if os.path.isdir(_WEB_DIR):
    app.mount("/app", StaticFiles(directory=_WEB_DIR, html=True), name="web")
