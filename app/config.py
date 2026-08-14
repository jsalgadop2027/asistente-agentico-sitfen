"""Configuración central de la aplicación.

Estrategia de secretos (cumple "No hardcodear SIDs/claves/tokens"):
  - Parámetros NO sensibles: variables de entorno / .env (pydantic-settings).
  - Secretos (Twilio, LangSmith): se resuelven desde Google Secret Manager en
    runtime mediante `get_secret`. En desarrollo local se permite un override por
    variable de entorno para no depender de la nube.

Un único `settings` (singleton) se importa en toda la app.
"""
from __future__ import annotations

import functools
import logging
import os
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- GCP ---
    gcp_project_id: str = Field(default="chatbot-agentico-v2")
    gcp_region: str = Field(default="us-central1")
    gcp_location: str = Field(default="us-central1")

    # --- Modelos Vertex / Model Garden ---
    gemini_model_fast: str = Field(default="gemini-2.5-flash")
    gemini_model_pro: str = Field(default="gemini-2.5-pro")
    embedding_model: str = Field(default="gemini-embedding-001")
    # Se pasa como `dimensions=` (output_dimensionality) a VertexAIEmbeddings.
    # Debe coincidir con la dimensión del índice vectorial de Firestore ya
    # creado (infra/01_setup_firestore_and_buckets.ps1 e
    # infra/06_conversation_memory_index.ps1, ambos vía $env:EMBEDDING_DIM) —
    # esos índices no se pueden redimensionar in place, así que cambiar este
    # valor exige borrar y recrear ambos índices.
    embedding_dim: int = Field(default=768)

    # Failover de ubicación del LLM ante 429 "Resource exhausted".
    # Gemini 2.5 se sirve bajo demanda con Dynamic Shared Quota (DSQ): la
    # capacidad es un pool COMPARTIDO por (ubicación, modelo), no una cuota del
    # proyecto — un 429 aquí no significa que hayamos excedido nada nuestro (no
    # aparece en la métrica quota/exceeded), sino que ese pool está saturado en
    # ese momento. Los pools son INDEPENDIENTES entre ubicaciones: se ha
    # observado 429 en una y 200 simultáneo en las demás, así que reintentar en
    # la MISMA ubicación no ayuda (bug real: 5 reintentos durante ~60 s, todos
    # 429, y el turno terminaba en el fallback genérico "Tuve un problema
    # procesando tu consulta") pero reintentar en OTRA sí.
    # Orden de intento; la primera es la preferida (misma región que Firestore,
    # menor latencia). "global" reparte entre regiones y es la mitigación que
    # recomienda Google para DSQ.
    vertex_llm_locations: str = Field(default="us-central1,global,us-east5,us-west1")
    # Reintentos DENTRO de una misma ubicación antes de pasar a la siguiente.
    # Bajo a propósito: el backoff por defecto de la librería (6 intentos, ~60 s)
    # hace esperar al usuario de WhatsApp un minuto por ubicación antes de que el
    # failover pueda actuar. Con DSQ conviene fallar rápido y cambiar de pool.
    vertex_llm_max_retries: int = Field(default=2)

    # --- Router multimodelo (Flash <-> Pro) ---
    # Selecciona el modelo por consulta: Flash (rápido/barato) por defecto y Pro
    # sólo cuando la consulta requiere razonamiento complejo (análisis, comparación,
    # estrategia, causalidad, multi-paso). Baja el costo sin perder calidad en las
    # preguntas difíciles. Es una heurística determinista (sin llamadas de red).
    router_enabled: bool = Field(default=True)
    # Nº de palabras a partir del cual una consulta se considera "larga/compleja"
    # y se enruta a Pro aunque no tenga verbos de razonamiento explícitos.
    router_pro_min_words: int = Field(default=30)

    # --- Firestore (vectores + memoria) ---
    firestore_database: str = Field(default="(default)")
    firestore_vector_collection: str = Field(default="corpus_chunks")
    firestore_memory_collection: str = Field(default="conversations")
    # Memoria semántica de largo plazo: colección vectorial con los intercambios
    # (usuario+asistente) por sesión, para recuperar interacciones pasadas.
    firestore_conv_memory_collection: str = Field(default="conversation_memory")

    # --- Memoria conversacional (corto + largo plazo) ---
    # Corto plazo: nº de entradas (user+assistant) conservadas literalmente.
    # 20 entradas = 10 intercambios completos (antes 12 entradas = 6 intercambios).
    memory_max_turns: int = Field(default=20)
    # Largo plazo: resumen progresivo (se condensa el historial que sale de la
    # ventana) + memoria semántica (recuerdos relevantes de sesiones antiguas).
    ltm_enabled: bool = Field(default=True)
    ltm_summary_enabled: bool = Field(default=True)
    ltm_semantic_enabled: bool = Field(default=True)
    # Nº de recuerdos semánticos relevantes a recuperar por consulta.
    ltm_recall_top_k: int = Field(default=3)
    # Máximo de palabras del resumen progresivo de largo plazo.
    ltm_summary_max_words: int = Field(default=180)
    # Eventos de novedades de la base de conocimiento (documentos nuevos
    # vectorizados, pendientes de anunciar al usuario en el canal web).
    firestore_kb_events_collection: str = Field(default="kb_events")
    # Registro de usuarios finales (control de sesión por WhatsApp mediante un
    # código interno estable de 8 caracteres).
    firestore_users_collection: str = Field(default="users")
    # Cuenta de servicio con la que Eventarc invoca /internal/kb-broadcast. Si se
    # define, el endpoint solo acepta tokens OIDC emitidos por ella (env
    # EVENTARC_SERVICE_ACCOUNT). Si queda vacío, acepta cualquier cuenta de
    # servicio de Google (menos estricto; recomendable fijarla en producción).
    eventarc_service_account: Optional[str] = Field(default=None)
    vector_distance: str = Field(default="COSINE")
    rag_top_k: int = Field(default=15)
    rag_rerank_top_n: int = Field(default=6)
    # Nº de reformulaciones adicionales que genera el LLM para la expansión
    # multi-query del retriever (además de la consulta original). Antes era un
    # default de Python hardcodeado en AdvancedRetriever._expand_query.
    rag_multiquery_n: int = Field(default=4)
    # Reranker real (cross-encoder) vía Vertex AI Ranking API, en vez de pedirle
    # a un LLM generalista que ordene índices en un prompt (más preciso, más
    # barato, no puede "alucinar" un orden inválido). Fail-open: si la API
    # falla, el retriever cae automáticamente al reranker por prompt. Kill
    # switch operativo (env var, sin rebuild) por si la API tuviera un
    # problema en producción.
    rag_ranking_api_enabled: bool = Field(default=True)
    # Hybrid Search (BM25 léxico + vectorial, fusionados por RRF). Kill switch
    # operativo igual que el de arriba — ver app/agent/bm25_index.py.
    rag_hybrid_search_enabled: bool = Field(default=True)

    # --- Cloud Storage ---
    gcs_corpus_bucket: str = Field(default="chatbot-agentico-v2-corpus")
    gcs_audio_bucket: str = Field(default="chatbot-agentico-v2-audio")
    signed_url_ttl_seconds: int = Field(default=900)

    # --- Twilio (nombres de secretos en Secret Manager) ---
    secret_twilio_account_sid: str = Field(default="twilio-account-sid")
    secret_twilio_auth_token: str = Field(default="twilio-auth-token")
    secret_twilio_whatsapp_number: str = Field(default="twilio-whatsapp-number")
    twilio_account_sid: Optional[str] = Field(default=None)
    twilio_auth_token: Optional[str] = Field(default=None)
    twilio_whatsapp_number: Optional[str] = Field(default=None)
    # SID de la plantilla de WhatsApp aprobada para el resumen de novedades
    # (Content API de Twilio, 'HX...'). Requerido para difundir a usuarios FUERA
    # de la ventana de 24 h en producción. Si queda vacío, la difusión cae a texto
    # libre (solo entrega en Sandbox o dentro de la ventana de 24 h). Variables de
    # la plantilla: {{1}}=nombre, {{2}}=título, {{3}}=resumen.
    whatsapp_kb_template_sid: Optional[str] = Field(default=None)

    # --- Captura de inquietudes (#3) + informe diario (#8) ---
    # Colección Firestore con las inquietudes clasificadas del usuario
    # (reclamo/pedido/sugerencia/recomendación) para el informe diario.
    firestore_concerns_collection: str = Field(default="user_concerns")
    # Tras cada mensaje se clasifica el punto de dolor y se guarda si aplica.
    # Es fire-and-forget: nunca bloquea ni rompe la respuesta al usuario.
    concern_capture_enabled: bool = Field(default=True)
    # Longitud mínima del mensaje para intentar clasificarlo (evita "hola", "ok").
    concern_min_chars: int = Field(default=8)

    # --- Reporte de atenciones normales del Admin UI (ver admin_ui/_atenciones.py) ---
    # Registro liviano de CADA turno de WhatsApp respondido (no solo los que
    # `app.concerns` clasifica como punto de dolor accionable — la mayoría de
    # mensajes son consultas informativas comunes, clasificadas "ninguno" y por
    # eso nunca llegaban a `user_concerns`). Sin clasificación LLM: solo deja
    # constancia de que hubo una atención, para poder contarla y cruzarla contra
    # `derivations` en el reporte.
    firestore_attentions_collection: str = Field(default="attentions")
    attention_capture_enabled: bool = Field(default=True)
    # Informe diario (20:00 America/Lima) con reclamos/pedidos/sugerencias/
    # recomendaciones del día, enviado por correo vía SendGrid.
    daily_report_enabled: bool = Field(default=True)
    daily_report_to: str = Field(default="jsalgadop2027@gmail.com")
    # Perú no observa horario de verano: offset fijo UTC-5 para fechar "el día".
    lima_utc_offset_hours: int = Field(default=-5)
    # Remitente del correo. DEBE coincidir con un sender verificado en SendGrid
    # (Single Sender o dominio autenticado); si no, SendGrid rechaza TODO envío
    # con 403 "The from address does not match a verified Sender Identity" —
    # bug real al migrar de cuenta. Hoy el verificado es jsalgadop2027@gmail.com
    # (nickname "SITFEN"). Al cambiar esta dirección, verifícala ANTES en
    # SendGrid: se comprueba con GET https://api.sendgrid.com/v3/verified_senders.
    email_from: str = Field(default="jsalgadop2027@gmail.com")
    email_from_name: str = Field(default="Asistente Arándano FEN")
    # SendGrid: nombre del secreto en Secret Manager (override local
    # SENDGRID_API_KEY para desarrollo). NO se hardcodea la clave.
    secret_sendgrid_api_key: str = Field(default="sendgrid-api-key")
    sendgrid_api_key: Optional[str] = Field(default=None)

    # --- Alerta satelital SST (#4) ---
    # URL base del servicio de monitoreo SST (arandano-sst-web). El agente le pide
    # la SST de puntos del norte para calcular la anomalía. Si queda vacío, la
    # comprobación se omite (no rompe).
    sst_monitor_base_url: Optional[str] = Field(default=None)
    sst_alert_enabled: bool = Field(default=True)
    # Umbral de anomalía (°C sobre la climatología mensual Niño 1+2) para considerar
    # la anomalía "significativa" (≈ El Niño Costero débil según ICEN).
    sst_anomaly_alert_c: float = Field(default=1.0)
    # SID de la plantilla WhatsApp aprobada para la alerta SST (Content API).
    sst_alert_template_sid: Optional[str] = Field(default=None)
    # Estado anti-repetición de la alerta (último nivel y fecha NOAA difundidos).
    firestore_sst_state_collection: str = Field(default="sst_alert_state")

    # --- Reenganche de usuarios inactivos ---
    reengage_enabled: bool = Field(default=True)
    # Minutos sin actividad (last_seen_at) para considerar inactivo a un usuario.
    # En MINUTOS, no días: el reenganche busca retomar la conversación el mismo
    # día, en los tres cortes de Cloud Scheduler (8:00, 12:00 y 17:00 de Lima).
    # `last_seen_at` se marca en cada mensaje entrante de WhatsApp
    # (`UserRegistry.resolve_session`), así que el umbral es exacto al minuto.
    reengage_inactive_minutes: int = Field(default=30)
    # Enfriamiento entre avisos al MISMO usuario. 180 min (3 h) es el valor que
    # deja pasar los tres cortes del día —hay 4 h entre 8:00 y 12:00, y 5 h entre
    # 12:00 y 17:00— y a la vez impide duplicados si una corrida se reintenta.
    # Subirlo por encima de 4 h silenciaría alguno de los cortes.
    reengage_cooldown_minutes: int = Field(default=180)
    # Tope de reenganches por corrida (evita ráfagas y respeta tiers de WhatsApp).
    reengage_max_per_run: int = Field(default=50)
    # SID de la plantilla WhatsApp aprobada para el reenganche (Content API).
    reengage_template_sid: Optional[str] = Field(default=None)

    # --- Derivación de solicitudes a entidades públicas ---
    # Al confirmar el usuario, el agente envía su solicitud por correo a la entidad
    # pública más pertinente. Mientras no haya correos verificados por entidad, todo
    # cae a `derivation_to` (admin) etiquetado, para ruteo manual (nunca se inventa
    # un destinatario). Reutiliza la configuración de SendGrid.
    derivation_enabled: bool = Field(default=True)
    derivation_to: str = Field(default="jsalgadop2027@gmail.com")
    # Registro de cada derivación (una entidad de un caso = un documento), para las
    # estadísticas del Admin UI (ver admin_ui/_derivaciones.py). Independiente del
    # envío por correo: una falla al registrar no bloquea el correo, y viceversa.
    firestore_derivations_collection: str = Field(default="derivations")
    # Confirmación determinista de derivaciones (ver app/pending_derivation.py):
    # caso ofrecido y aún sin confirmar, por usuario. El TTL evita que un "Sí"
    # tardío resucite un caso planteado mucho antes.
    firestore_pending_derivations_collection: str = Field(default="pending_derivations")
    pending_derivation_ttl_minutes: int = Field(default=30)

    # --- Fase 3: seguimiento de inquietudes + objetivos + escalamiento ---
    # Seguimiento in-session (NO push, no requiere plantilla): inyecta al prompt
    # las inquietudes abiertas recientes del usuario (reclamo/pedido) para que el
    # agente las retome de forma natural en la conversación. Cero invasividad.
    concern_followup_enabled: bool = Field(default=True)
    # Ventana (días) de inquietudes que se consideran "abiertas" para el seguimiento.
    concern_followup_days: int = Field(default=14)
    # Máximo de inquietudes que se inyectan al prompt (evita saturar el contexto).
    concern_followup_max: int = Field(default=3)
    # Objetivos/metas de negocio del usuario, detectados por el MISMO clasificador
    # Flash (sin llamada extra) y guardados por usuario; se inyectan al prompt para
    # que el agente oriente sus respuestas y sugerencias hacia esa meta.
    goal_tracking_enabled: bool = Field(default=True)
    firestore_goals_collection: str = Field(default="user_goals")
    # Escalamiento a humano: cuando el usuario pide una persona o se detecta
    # angustia/insatisfacción no resoluble, la tool `escalar_a_humano` avisa al
    # equipo por correo (SendGrid) y registra el caso. No pausa el bot globalmente
    # (la consola en vivo es de un solo usuario); el humano retoma por la consola.
    handoff_enabled: bool = Field(default=True)
    handoff_to: str = Field(default="jsalgadop2027@gmail.com")
    firestore_handoffs_collection: str = Field(default="handoffs")

    # --- Voz ---
    voice_enabled: bool = Field(default=True)
    # STT vía Gemini (Vertex AI): sin ajustes de modelo/sample-rate, ver
    # app/voice/stt.py.
    tts_language: str = Field(default="es-US")
    tts_voice: str = Field(default="es-US-Neural2-A")

    # --- Proactividad del canal web (avatar 3D) ---
    # El avatar consulta periódicamente si el agente tiene algo que decir por
    # iniciativa propia (alerta SST del FEN, documento nuevo en la base, o el
    # seguimiento de una inquietud abierta del usuario identificado).
    proactive_web_enabled: bool = Field(default=True)
    # El avatar sondea cada ~20 s POR VISITANTE y la lectura SST son 3 llamadas
    # HTTP al servicio satelital: se cachea en proceso para no amplificar carga.
    proactive_sst_ttl_seconds: int = Field(default=900)   # 15 min
    # Caché por sesión del seguimiento personal (evita consultar Firestore en cada
    # sondeo de un usuario identificado).
    proactive_followup_ttl_seconds: int = Field(default=600)  # 10 min

    # --- Visión (imágenes entrantes) ---
    # El usuario puede enviar una FOTO por WhatsApp (planta con síntomas, plaga,
    # documento, etiqueta, factura). Gemini multimodal la describe/analiza y el
    # agente responde fundamentado en el corpus, igual que con las notas de voz
    # (ver app/vision/describe.py). Si se desactiva, la foto se ignora y se usa el
    # texto (caption) si lo hay.
    vision_enabled: bool = Field(default=True)
    # Tamaño máximo de imagen a procesar (bytes). WhatsApp ya limita ~5 MB; se pone
    # un techo defensivo para no descargar/enviar imágenes desmedidas al modelo.
    vision_max_bytes: int = Field(default=8 * 1024 * 1024)  # 8 MB

    # --- Generación de imágenes por IA (Vertex AI Imagen) ---
    # A diferencia de los gráficos (matplotlib, gratis salvo la subida a GCS),
    # Imagen cobra por imagen generada: kill switch operativo + cupo diario por
    # usuario (ver app/agent/tools/image_gen_tools.py) acotan el gasto.
    image_gen_enabled: bool = Field(default=True)
    # "imagen-3.0-fast-generate-001" (más barato/rápido) vs "imagen-3.0-generate-002"
    # (mejor calidad, más lento/costoso). Fast es razonable para ilustraciones de
    # apoyo en WhatsApp, no para material publicable formal.
    imagen_model: str = Field(default="imagen-3.0-fast-generate-001")
    # Tope de imágenes generadas por usuario y por día (hora de Lima). Fail-open si
    # Firestore no responde o el usuario no está identificado (sesión web anónima).
    image_gen_max_per_day: int = Field(default=5)
    firestore_image_gen_usage_collection: str = Field(default="image_gen_usage")

    # --- Clima (AccuWeather) ---
    # API key del servicio de clima. NO se hardcodea: se lee de env/.env en local
    # o de Secret Manager en producción. Opcional: si falta, la tool lo informa.
    accuweather_api_key: Optional[str] = Field(default=None)

    # --- NOAA (monitoreo ENSO / El Niño-Oscilación del Sur) ---
    # Token de la Climate Data Online API v2 del NCEI. Mismo patrón que
    # accuweather_api_key: NO se hardcodea, se lee de env/.env en local (override
    # NOAA_API_TOKEN) o llega inyectado como variable de entorno vía secretKeyRef
    # en Cloud Run (Secret Manager, secreto "noaa-api-token"). Opcional: si falta,
    # la tool lo informa en vez de fallar.
    noaa_api_token: Optional[str] = Field(default=None)

    # --- LangSmith ---
    langchain_tracing_v2: bool = Field(default=False)
    langchain_project: str = Field(default="chatbot-agentico-v2")
    secret_langsmith_api_key: str = Field(default="langsmith-api-key")
    langchain_api_key: Optional[str] = Field(default=None)

    # --- Confident AI (observabilidad de producción vía DeepEval tracing) ---
    # Sube la traza de cada consulta (estructura del agente ReAct, nodos, llamadas
    # al modelo, tools, latencias, errores y eventos de seguridad) al dashboard de
    # Confident AI para ver rendimiento, trazabilidad, monitoreo, seguimiento por
    # conversación, seguridad y salud. Desactivado por defecto: se activa poniendo
    # ENABLE_CONFIDENT_TRACING=true en el entorno (se hace en el deploy).
    # OJO: NO usar el nombre CONFIDENT_TRACING_ENABLED: esa variable la lee DeepEval
    # y solo la considera activa si vale exactamente "YES" (tracing_enabled() hace
    # os.getenv("CONFIDENT_TRACING_ENABLED","YES").upper()=="YES"). Un valor como
    # "true" APAGARÍA el tracing de DeepEval. Por eso este toggle usa otro nombre.
    enable_confident_tracing: bool = Field(default=False)
    # Nombre del secreto en Secret Manager (la key NUNCA se hardcodea).
    secret_confident_api_key: str = Field(default="confident-api-key")
    # Override por entorno (desarrollo local / secretKeyRef CONFIDENT_API_KEY).
    confident_api_key: Optional[str] = Field(default=None)
    # Entorno lógico reportado en el dashboard (production | staging | development).
    confident_environment: str = Field(default="production")
    # Muestreo de trazas (1.0 = todas). Bajar para reducir volumen/costo.
    confident_sampling_rate: float = Field(default=1.0)
    # Enmascara PII (emails, teléfonos, DNI/RUC, tarjetas) en inputs/outputs antes
    # de subirlos a Confident AI (SaaS en EE. UU.). Minimización de datos, coherente
    # con langsmith_hide_io. Poner en False solo si necesitas el texto literal.
    confident_mask_pii: bool = Field(default=True)

    # --- Guardrails / límites ---
    rate_limit_per_minute: int = Field(default=15)
    max_input_chars: int = Field(default=4000)
    enable_pii_redaction: bool = Field(default=True)
    # Sal para pseudonimizar identificadores personales (p. ej. el teléfono de un
    # usuario NO registrado) antes de usarlos como clave en Firestore. En
    # producción, sobreescribir con un valor secreto (env PII_HASH_SALT).
    pii_hash_salt: str = Field(default="arandano-v2-pii")
    # Oculta inputs/outputs en las trazas de LangSmith (evita que PII del mensaje
    # del usuario quede registrada en la observabilidad). Prioriza privacidad
    # sobre riqueza de la traza; poner en False solo en proyectos de depuración.
    langsmith_hide_io: bool = Field(default=True)

    # --- Validación de ingesta (integridad + seguridad antes de vectorizar) ---
    # Tamaño máximo por documento (bytes). 0 = sin límite.
    ingestion_max_bytes: int = Field(default=25 * 1024 * 1024)  # 25 MB
    # Política ante PII detectada en el texto: "redact" | "block" | "warn".
    ingestion_pii_mode: str = Field(default="redact")
    # Antivirus: host/puerto de un demonio ClamAV (opcional). Si se define, se
    # escanea cada archivo. La firma EICAR de prueba siempre se detecta.
    clamav_host: Optional[str] = Field(default=None)
    clamav_port: int = Field(default=3310)
    # Si True y el antivirus no está disponible/configurado, se bloquea la carga.
    ingestion_require_av: bool = Field(default=False)
    # Bloquea documentos con contenido activo/armado antes de indexar:
    # macros VBA en Office y JavaScript/acciones automáticas/archivos embebidos
    # en PDF (vectores de malware y de exfiltración). Seguridad.
    ingestion_block_active_content: bool = Field(default=True)
    # Escaneo de inyección de prompt / envenenamiento de datos en el TEXTO del
    # documento antes de indexar (OWASP LLM01/LLM03): un PDF puede traer
    # instrucciones adversarias que el agente ejecutaría al recuperarlas.
    # Modos: "sanitize" (neutraliza y avisa) | "block" | "warn" | "off".
    ingestion_injection_mode: str = Field(default="sanitize")

    # --- CORS (canal web) ---
    # Orígenes cross-site permitidos para la API web, coma-separados
    # (env CORS_ALLOW_ORIGINS). Vacío = solo mismo origen (el avatar web se sirve
    # desde /app/, mismo origen, así que NO necesita CORS). Evita el comodín "*".
    cors_allow_origins: str = Field(default="")

    # --- Webhook Twilio ---
    # Fail-closed: si no hay auth_token para verificar la firma, se RECHAZA la
    # petición (anti-spoofing). En desarrollo local puede ponerse en False.
    twilio_require_signature: bool = Field(default=True)

    # --- Runtime ---
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")

    @property
    def is_local(self) -> bool:
        return self.environment.lower() in ("local", "dev", "development")


@functools.lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


@functools.lru_cache(maxsize=32)
def get_secret(secret_id: str, *, fallback_env: Optional[str] = None) -> Optional[str]:
    """Resuelve un secreto desde Secret Manager, con fallback a env (sólo local).

    Cacheado para evitar llamadas repetidas. Devuelve None si no se encuentra.
    """
    # 1) Override por variable de entorno (desarrollo local).
    if fallback_env:
        env_val = os.getenv(fallback_env)
        if env_val:
            return env_val

    settings = get_settings()
    try:
        from google.cloud import secretmanager  # import perezoso

        client = secretmanager.SecretManagerServiceClient()
        name = (
            f"projects/{settings.gcp_project_id}/secrets/{secret_id}/versions/latest"
        )
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("utf-8").strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("No se pudo leer el secreto '%s' desde Secret Manager: %s",
                       secret_id, exc)
        return None


def get_twilio_credentials() -> dict[str, Optional[str]]:
    """Credenciales Twilio resueltas en runtime (Secret Manager o env local)."""
    s = get_settings()
    return {
        "account_sid": get_secret(s.secret_twilio_account_sid,
                                  fallback_env="TWILIO_ACCOUNT_SID"),
        "auth_token": get_secret(s.secret_twilio_auth_token,
                                 fallback_env="TWILIO_AUTH_TOKEN"),
        "whatsapp_number": get_secret(s.secret_twilio_whatsapp_number,
                                      fallback_env="TWILIO_WHATSAPP_NUMBER"),
    }


settings = get_settings()
