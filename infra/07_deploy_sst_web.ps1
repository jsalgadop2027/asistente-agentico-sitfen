# Despliega el monitor SST web como servicio Cloud Run INDEPENDIENTE: una app
# FastAPI (uvicorn) que sirve web-sst-monitor/index.html Y expone /api/sst y
# /api/series, que consultan NOAA CoastWatch (blended SST NRT vía ERDDAP) del
# lado del servidor (NOAA no envía CORS). No comparte imagen ni secretos con el
# agente; sin API key (ERDDAP es abierto). Público y con escala a cero (costo ~0
# en reposo). (Bloque B — incurre costo de build y de Cloud Run.)
$ErrorActionPreference = "Stop"
$PROJECT = $env:GCP_PROJECT_ID; if (-not $PROJECT) { $PROJECT = "chatbot-agentico-v2" }
$REGION  = $env:GCP_REGION;     if (-not $REGION)  { $REGION  = "us-central1" }
$REPO    = "chatbot-repo"
$SVC     = "arandano-sst-web"
$BASE    = "$REGION-docker.pkg.dev/$PROJECT/$REPO"

# Contexto de build anclado a la ubicación del script (independiente del CWD).
$SRC = Join-Path (Split-Path $PSScriptRoot -Parent) "web-sst-monitor"

# 1) Artifact Registry (idempotente; reutiliza el repo del proyecto).
Write-Host "Asegurando Artifact Registry $REPO..." -ForegroundColor Cyan
try {
  gcloud artifacts repositories create $REPO --repository-format=docker `
    --location=$REGION --project=$PROJECT
} catch { Write-Host "Repo ya existe (continuando)." -ForegroundColor Yellow }

# 2) Build de la imagen estática (contexto = carpeta web-sst-monitor/).
Write-Host "Construyendo imagen del sitio SST..." -ForegroundColor Cyan
gcloud builds submit $SRC --tag "$BASE/$SVC`:latest" --project=$PROJECT

# 3) Deploy en Cloud Run: público, escala a cero. Si están definidas en el entorno
#    AGENT_BASE_URL y LIVE_CONSOLE_TOKEN, se inyectan para la consola de WhatsApp
#    en vivo (/api/live/* proxya al agente; los secretos siguen solo en el agente).
#    Si está definida GOOGLE_MAPS_API_KEY, se inyecta para /mapa-google (mapa
#    interactivo con Google Maps); sin ella esa vista queda con un aviso y el
#    resto del servicio (incl. el mapa clásico /) funciona igual.
Write-Host "Desplegando servicio $SVC..." -ForegroundColor Cyan
$ENV_VARS = @()
if ($env:AGENT_BASE_URL -and $env:LIVE_CONSOLE_TOKEN) {
  $ENV_VARS += "AGENT_BASE_URL=$($env:AGENT_BASE_URL),LIVE_CONSOLE_TOKEN=$($env:LIVE_CONSOLE_TOKEN)"
  Write-Host "  (consola en vivo: AGENT_BASE_URL + LIVE_CONSOLE_TOKEN inyectados)" -ForegroundColor DarkGray
}
if ($env:GOOGLE_MAPS_API_KEY) {
  $ENV_VARS += "GOOGLE_MAPS_API_KEY=$($env:GOOGLE_MAPS_API_KEY)"
  Write-Host "  (mapa Google: GOOGLE_MAPS_API_KEY inyectada)" -ForegroundColor DarkGray
}
$SET_ENV = @()
if ($ENV_VARS.Count -gt 0) { $SET_ENV = @("--set-env-vars", ($ENV_VARS -join ",")) }
gcloud run deploy $SVC --image "$BASE/$SVC`:latest" --region=$REGION --project=$PROJECT `
  --allow-unauthenticated `
  --memory=512Mi --cpu=1 --min-instances=0 --max-instances=3 --concurrency=80 --port=8080 `
  @SET_ENV

$URL = gcloud run services describe $SVC --region=$REGION --project=$PROJECT --format="value(status.url)"
Write-Host "`nDespliegue completo." -ForegroundColor Green
Write-Host "Monitor SST web disponible en:" -ForegroundColor Green
Write-Host "  $URL" -ForegroundColor White
