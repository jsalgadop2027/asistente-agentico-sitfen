# Construye imágenes y despliega: servicio webhook, Admin UI y job de ingesta.
# (Bloque B - incurre costo de build y de Cloud Run)
$ErrorActionPreference = "Stop"
$PROJECT = $env:GCP_PROJECT_ID; if (-not $PROJECT) { $PROJECT = "chatbot-agentico-v2" }
$REGION  = $env:GCP_REGION;     if (-not $REGION)  { $REGION  = "us-central1" }
$REPO    = "chatbot-repo"
$SVC     = "arandano-agent"
$ADMIN   = "arandano-admin"
$JOB     = "arandano-ingest"

$PROJNUM = gcloud projects describe $PROJECT --format="value(projectNumber)"
$SA = "$PROJNUM-compute@developer.gserviceaccount.com"
$BASE = "$REGION-docker.pkg.dev/$PROJECT/$REPO"

# 1) Artifact Registry.
Write-Host "Creando Artifact Registry..." -ForegroundColor Cyan
try {
  gcloud artifacts repositories create $REPO --repository-format=docker `
    --location=$REGION --project=$PROJECT
} catch { Write-Host "Repo ya existe (continuando)." -ForegroundColor Yellow }

# 2) Permisos para la service account de runtime (menor privilegio).
Write-Host "Otorgando roles a $SA..." -ForegroundColor Cyan
$roles = @(
  "roles/aiplatform.user", "roles/datastore.user",
  "roles/secretmanager.secretAccessor", "roles/storage.objectAdmin",
  "roles/speech.client", "roles/logging.logWriter", "roles/cloudtrace.agent"
)
foreach ($r in $roles) {
  gcloud projects add-iam-policy-binding $PROJECT `
    --member="serviceAccount:$SA" --role=$r --condition=None | Out-Null
}

# 2a-bis) La SA de runtime en Cloud Run solo trae credenciales de token (sin
#     llave privada), así que generate_signed_url() (usado para adjuntar el
#     audio TTS al mensaje de WhatsApp) no puede firmar localmente. Necesita
#     poder firmar vía la API de IAM sobre sí misma (self-impersonation).
Write-Host "Otorgando Service Account Token Creator (self) a $SA..." -ForegroundColor Cyan
gcloud iam service-accounts add-iam-policy-binding $SA `
  --member="serviceAccount:$SA" --role="roles/iam.serviceAccountTokenCreator" `
  --project=$PROJECT | Out-Null

# 2b) Secreto de sal para pseudonimizar PII (teléfono de no registrados).
#     Se crea UNA sola vez con un valor aleatorio fuerte; si ya existe NO se
#     modifica (cambiar la sal invalidaría los tokens de sesión ya emitidos).
Write-Host "Asegurando secreto pii-hash-salt..." -ForegroundColor Cyan
$saltExists = $null
try { $saltExists = gcloud secrets describe pii-hash-salt --project=$PROJECT --format="value(name)" 2>$null } catch {}
if (-not $saltExists) {
  $bytes = New-Object byte[] 32
  [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
  $tmp = Join-Path $env:TEMP "pii_salt.tmp"
  [IO.File]::WriteAllText($tmp, [Convert]::ToBase64String($bytes))  # sin salto de línea
  gcloud secrets create pii-hash-salt --replication-policy=automatic --project=$PROJECT
  gcloud secrets versions add pii-hash-salt --data-file=$tmp --project=$PROJECT
  Remove-Item $tmp -Force
  Write-Host "Secreto pii-hash-salt creado." -ForegroundColor Green
} else {
  Write-Host "Secreto pii-hash-salt ya existe (no se modifica)." -ForegroundColor Yellow
}

# 3) Build de imágenes.
Write-Host "Construyendo imagen del servicio..." -ForegroundColor Cyan
gcloud builds submit --tag "$BASE/$SVC`:latest" --project=$PROJECT .
Write-Host "Construyendo imagen del Admin UI..." -ForegroundColor Cyan
gcloud builds submit --config=infra/cloudbuild.admin.yaml `
  --ignore-file=infra/.gcloudignore.admin `
  --substitutions=_IMAGE="$BASE/$ADMIN`:latest" --project=$PROJECT .

$ENVVARS = "ENVIRONMENT=production,GCP_PROJECT_ID=$PROJECT,GCP_REGION=$REGION,GCP_LOCATION=$REGION,LANGCHAIN_TRACING_V2=true,EVENTARC_SERVICE_ACCOUNT=$SA"
# SID de la plantilla de WhatsApp aprobada (Utility) para el resumen de novedades
# (Content API de Twilio, 'HX...'). Ya está aprobada y en producción, así que se
# fija por defecto para que un redeploy NO la borre (regresión a texto libre).
# Se puede sobreescribir exportando WHATSAPP_KB_TEMPLATE_SID en el entorno.
$KB_TPL = $env:WHATSAPP_KB_TEMPLATE_SID
if (-not $KB_TPL) { $KB_TPL = "HX8cd7d71bace0360bac662d108a8c9331" }
$ENVVARS += ",WHATSAPP_KB_TEMPLATE_SID=$KB_TPL"

# Plantillas de proactividad (alerta SST #4 y reenganche). Fijadas por defecto a
# las plantillas aprobadas para que un redeploy NO las borre; overridable por env.
$SST_TPL = $env:SST_ALERT_TEMPLATE_SID
if (-not $SST_TPL) { $SST_TPL = "HXe8db77e3634456f3cb2f8b2fa181e191" }
$ENVVARS += ",SST_ALERT_TEMPLATE_SID=$SST_TPL"
$RE_TPL = $env:REENGAGE_TEMPLATE_SID
if (-not $RE_TPL) { $RE_TPL = "HXeebdf056ca33a1be21cb4536c52a0093" }
$ENVVARS += ",REENGAGE_TEMPLATE_SID=$RE_TPL"
# URL del servicio satelital: el agente le pide la SST del norte para la anomalía.
$SSTURL = ""
try { $SSTURL = gcloud run services describe arandano-sst-web --region=$REGION --project=$PROJECT --format="value(status.url)" 2>$null } catch {}
if ($SSTURL) { $ENVVARS += ",SST_MONITOR_BASE_URL=$SSTURL" }

# Observabilidad de producción con Confident AI (DeepEval tracing): se activa
# SOLO en el servicio del agente (no en Admin UI ni en el job de ingesta).
# OJO con los nombres: ENABLE_CONFIDENT_TRACING es NUESTRO toggle. NO usar
# CONFIDENT_TRACING_ENABLED: esa es de DeepEval y solo acepta "YES" (otro valor
# apaga su tracing); el código la fija a "YES" en runtime.
# DEEPEVAL_TELEMETRY_OPT_OUT/ERROR_REPORTING: apaga la telemetría propia de
# DeepEval (PostHog/Sentry) para que la librería NO llame a casa (privacidad).
$AGENT_ENVVARS = "$ENVVARS,ENABLE_CONFIDENT_TRACING=true,DEEPEVAL_TELEMETRY_OPT_OUT=YES,ERROR_REPORTING=NO"

# Secretos montados como variables de entorno (Secret Manager -> secretKeyRef).
# El agente usa clima + NOAA + LangSmith + Confident AI + sal PII; admin y job solo la sal PII.
$AGENT_SECRETS  = "ACCUWEATHER_API_KEY=accuweather-api-key:latest,NOAA_API_TOKEN=noaa-api-token:latest,LANGCHAIN_API_KEY=langsmith-api-key:latest,CONFIDENT_API_KEY=confident-api-key:latest,PII_HASH_SALT=pii-hash-salt:latest"
$COMMON_SECRETS = "PII_HASH_SALT=pii-hash-salt:latest"

# 4) Deploy del servicio webhook (público: Twilio debe alcanzarlo).
Write-Host "Desplegando servicio $SVC..." -ForegroundColor Cyan
gcloud run deploy $SVC --image "$BASE/$SVC`:latest" --region=$REGION --project=$PROJECT `
  --service-account=$SA --allow-unauthenticated `
  --memory=1Gi --cpu=1 --min-instances=1 --max-instances=5 --concurrency=20 --no-cpu-throttling `
  --set-env-vars=$AGENT_ENVVARS --set-secrets=$AGENT_SECRETS

# 5) Deploy del Admin UI (restringido; acceso por IAM).
Write-Host "Desplegando Admin UI $ADMIN..." -ForegroundColor Cyan
gcloud run deploy $ADMIN --image "$BASE/$ADMIN`:latest" --region=$REGION --project=$PROJECT `
  --service-account=$SA --no-allow-unauthenticated `
  --memory=1Gi --cpu=1 --min-instances=0 --max-instances=3 `
  --set-env-vars=$ENVVARS --set-secrets=$COMMON_SECRETS

# 6) Job de ingesta batch (re-ejecutable).
Write-Host "Creando/actualizando job de ingesta $JOB..." -ForegroundColor Cyan
try {
  gcloud run jobs create $JOB --image "$BASE/$SVC`:latest" --region=$REGION --project=$PROJECT `
    --service-account=$SA --memory=2Gi --cpu=2 --max-retries=1 `
    --set-env-vars=$ENVVARS --set-secrets=$COMMON_SECRETS `
    --command="python" --args="-m,ingestion.ingest,--source,gcs,--bucket,$PROJECT-corpus"
} catch {
  gcloud run jobs update $JOB --image "$BASE/$SVC`:latest" --region=$REGION --project=$PROJECT `
    --set-env-vars=$ENVVARS --set-secrets=$COMMON_SECRETS
}

# 7) Trigger de Eventarc: difusión automática al ingestar (kb_events -> WhatsApp).
#    IMPORTANTE: la ubicación del trigger debe COINCIDIR con la de la base
#    Firestore. En este proyecto la base '(default)' es regional en us-central1
#    (= $REGION), por eso ese es el valor por defecto. Si mueves Firestore a otra
#    ubicación (p. ej. la multi-región 'nam5'), expórtala en FIRESTORE_LOCATION.
#    Verifícala con:
#      gcloud firestore databases describe --database='(default)' --format='value(locationId)'
$FSLOC = $env:FIRESTORE_LOCATION; if (-not $FSLOC) { $FSLOC = $REGION }
Write-Host "Habilitando Eventarc y creando trigger de difusion..." -ForegroundColor Cyan
gcloud services enable eventarc.googleapis.com --project=$PROJECT | Out-Null

# Roles necesarios: recibir eventos e invocar el servicio de Cloud Run.
gcloud projects add-iam-policy-binding $PROJECT `
  --member="serviceAccount:$SA" --role="roles/eventarc.eventReceiver" --condition=None | Out-Null
gcloud run services add-iam-policy-binding $SVC --region=$REGION --project=$PROJECT `
  --member="serviceAccount:$SA" --role="roles/run.invoker" | Out-Null

try {
  gcloud eventarc triggers create arandano-kb-broadcast `
    --location=$FSLOC --project=$PROJECT `
    --destination-run-service=$SVC --destination-run-region=$REGION `
    --destination-run-path="/internal/kb-broadcast" `
    --event-filters="type=google.cloud.firestore.document.v1.written" `
    --event-filters="database=(default)" `
    --event-filters="namespace=(default)" `
    --event-filters-path-pattern="document=kb_events/{docId}" `
    --event-data-content-type="application/protobuf" `
    --service-account="$SA"
} catch {
  Write-Host "Trigger ya existe o requiere propagacion de agentes de servicio (reintenta si falla)." -ForegroundColor Yellow
}

# 8) Secreto de SendGrid (informe diario #8). Solo se toca si pasas la API key por
#    entorno (SENDGRID_API_KEY); el agente la lee de Secret Manager en runtime.
Write-Host "Asegurando secreto sendgrid-api-key..." -ForegroundColor Cyan
if ($env:SENDGRID_API_KEY) {
  $sgExists = $null
  try { $sgExists = gcloud secrets describe sendgrid-api-key --project=$PROJECT --format="value(name)" 2>$null } catch {}
  if (-not $sgExists) { gcloud secrets create sendgrid-api-key --replication-policy=automatic --project=$PROJECT }
  $sgtmp = Join-Path $env:TEMP "sendgrid.tmp"
  [IO.File]::WriteAllText($sgtmp, $env:SENDGRID_API_KEY)  # sin salto de línea
  gcloud secrets versions add sendgrid-api-key --data-file=$sgtmp --project=$PROJECT
  Remove-Item $sgtmp -Force
  Write-Host "Secreto sendgrid-api-key actualizado." -ForegroundColor Green
} else {
  Write-Host "SENDGRID_API_KEY no definido: crea el secreto 'sendgrid-api-key' antes de usar el informe diario." -ForegroundColor Yellow
}

# 9) Cloud Scheduler: informe diario de inquietudes a las 20:00 (hora de Lima).
#    Invoca /internal/daily-report con token OIDC de la cuenta de servicio; el
#    endpoint lo verifica igual que el trigger de Eventarc (el servicio es público
#    para Twilio, así que la protección es el OIDC, no el IAM invoker).
Write-Host "Configurando Cloud Scheduler del informe diario (20:00 Lima)..." -ForegroundColor Cyan
gcloud services enable cloudscheduler.googleapis.com --project=$PROJECT | Out-Null
$SVCURL = gcloud run services describe $SVC --region=$REGION --project=$PROJECT --format="value(status.url)"
$JOBNAME = "arandano-daily-report"
$jobExists = $null
try { $jobExists = gcloud scheduler jobs describe $JOBNAME --location=$REGION --project=$PROJECT --format="value(name)" 2>$null } catch {}
if ($jobExists) {
  gcloud scheduler jobs update http $JOBNAME --location=$REGION --project=$PROJECT `
    --schedule="0 20 * * *" --time-zone="America/Lima" `
    --uri="$SVCURL/internal/daily-report" --http-method=POST `
    --oidc-service-account-email=$SA --oidc-token-audience="$SVCURL"
} else {
  gcloud scheduler jobs create http $JOBNAME --location=$REGION --project=$PROJECT `
    --schedule="0 20 * * *" --time-zone="America/Lima" `
    --uri="$SVCURL/internal/daily-report" --http-method=POST `
    --oidc-service-account-email=$SA --oidc-token-audience="$SVCURL"
}

# 10) Cloud Scheduler de proactividad: alerta SST diaria (09:00) y reenganche
#     tres veces al día (08:00, 12:00 y 17:00), hora de Lima. Se reengancha a
#     quien lleve `reengage_inactive_minutes` (30 min) sin escribir, así que los
#     tres cortes son los momentos en que se evalúa esa inactividad. El
#     enfriamiento (`reengage_cooldown_minutes`, 3 h) impide duplicados si una
#     corrida se reintenta, sin llegar a silenciar ninguno de los tres cortes
#     (hay 4 h entre 8:00 y 12:00, y 5 h entre 12:00 y 17:00). Ambos con OIDC de
#     la cuenta de servicio.
Write-Host "Configurando Schedulers de alerta SST y reenganche..." -ForegroundColor Cyan
function Set-SchedulerJob($jobName, $schedule, $path) {
  $exists = $null
  try { $exists = gcloud scheduler jobs describe $jobName --location=$REGION --project=$PROJECT --format="value(name)" 2>$null } catch {}
  $verb = if ($exists) { "update" } else { "create" }
  gcloud scheduler jobs $verb http $jobName --location=$REGION --project=$PROJECT `
    --schedule=$schedule --time-zone="America/Lima" `
    --uri="$SVCURL$path" --http-method=POST `
    --oidc-service-account-email=$SA --oidc-token-audience="$SVCURL"
}
Set-SchedulerJob "arandano-sst-check" "0 9 * * *"  "/internal/sst-alert"
Set-SchedulerJob "arandano-reengage"  "0 8,12,17 * * *" "/internal/re-engage"

$URL = gcloud run services describe $SVC --region=$REGION --project=$PROJECT --format="value(status.url)"
Write-Host "`nDespliegue completo." -ForegroundColor Green
Write-Host "URL del webhook (configura en Twilio):" -ForegroundColor Green
Write-Host "  $URL/webhook/whatsapp" -ForegroundColor White
