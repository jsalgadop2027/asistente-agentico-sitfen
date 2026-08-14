# Crea/actualiza los secretos en Secret Manager. (Bloque B)
# NO hardcodea: los valores se pasan por variables de entorno antes de ejecutar.
#
# Ejemplo de uso (PowerShell):
#   $env:TWILIO_ACCOUNT_SID="ACxxxx"
#   $env:TWILIO_AUTH_TOKEN="xxxx"
#   $env:TWILIO_WHATSAPP_NUMBER="whatsapp:+18167449920"
#   $env:LANGSMITH_API_KEY="ls__xxxx"   # opcional
#   ./infra/02_secrets.ps1
$ErrorActionPreference = "Stop"
$PROJECT = $env:GCP_PROJECT_ID; if (-not $PROJECT) { $PROJECT = "chatbot-agentico-v2" }

function Set-Secret($name, $value) {
  if (-not $value) { Write-Host "  (omitido) $name sin valor en entorno" -ForegroundColor Yellow; return }
  $exists = $true
  try { gcloud secrets describe $name --project=$PROJECT | Out-Null } catch { $exists = $false }
  if (-not $exists) {
    gcloud secrets create $name --replication-policy=automatic --project=$PROJECT | Out-Null
  }
  $value | gcloud secrets versions add $name --data-file=- --project=$PROJECT | Out-Null
  Write-Host "  secreto actualizado: $name" -ForegroundColor Green
}

Write-Host "Cargando secretos en Secret Manager..." -ForegroundColor Cyan
Set-Secret "twilio-account-sid"     $env:TWILIO_ACCOUNT_SID
Set-Secret "twilio-auth-token"      $env:TWILIO_AUTH_TOKEN
Set-Secret "twilio-whatsapp-number" $env:TWILIO_WHATSAPP_NUMBER
Set-Secret "langsmith-api-key"      $env:LANGSMITH_API_KEY
Set-Secret "confident-api-key"      $env:CONFIDENT_API_KEY

Write-Host "Listo. Recuerda otorgar acceso a la service account de Cloud Run (03_deploy)." -ForegroundColor Green
