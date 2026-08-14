# Empaqueta el instalador de escritorio (Electron, Windows/NSIS) en Cloud
# Build y lo publica en un bucket de GCS -- no requiere Node/electron-builder
# instalado localmente ni una máquina Windows (usa Wine dentro del build, ver
# infra/cloudbuild.desktop.yaml). Bloque opcional, incurre costo de build.
$ErrorActionPreference = "Stop"
$PROJECT = $env:GCP_PROJECT_ID; if (-not $PROJECT) { $PROJECT = "chatbot-agentico-v2" }
$BUCKET  = "$PROJECT-desktop-builds"

# Animador "Hombre" del instalador (opcional, ver comentario del mismo asset
# en el Dockerfile del agente): sin definir, el instalador solo trae Mujer y
# Robot -- no rompe el build.
$MALE_AVATAR_URL = $env:MALE_AVATAR_URL; if (-not $MALE_AVATAR_URL) { $MALE_AVATAR_URL = "" }

Write-Host "Verificando bucket de destino gs://$BUCKET ..." -ForegroundColor Cyan
try {
  gcloud storage buckets describe "gs://$BUCKET" --project=$PROJECT *>$null
  if ($LASTEXITCODE -ne 0) { throw "no existe" }
} catch {
  gcloud storage buckets create "gs://$BUCKET" --project=$PROJECT --location=us-central1 --uniform-bucket-level-access
}

Write-Host "Construyendo instalador de escritorio en Cloud Build (Wine, sin maquina Windows)..." -ForegroundColor Cyan
# La raíz de la fuente subida a Cloud Build es desktop/ (no la raíz del repo):
# el .gcloudignore de la raíz excluye toda la carpeta desktop/ a propósito
# (no forma parte de la imagen del agente), así que desde ahí nunca llegaría
# al build. Dentro de desktop/ no hay .gcloudignore propio, así que gcloud usa
# su .gitignore (excluye node_modules/ y dist/, que es justo lo que se quiere).
Push-Location (Join-Path $PSScriptRoot "..\desktop")
try {
  gcloud builds submit --config=../infra/cloudbuild.desktop.yaml `
    --substitutions="_BUCKET=$BUCKET,_MALE_AVATAR_URL=$MALE_AVATAR_URL" `
    --project=$PROJECT .
} finally {
  Pop-Location
}

Write-Host "`nListo. Descargar el instalador:" -ForegroundColor Green
Write-Host "  gcloud storage cp gs://$BUCKET/desktop/*.exe . --project=$PROJECT" -ForegroundColor White
