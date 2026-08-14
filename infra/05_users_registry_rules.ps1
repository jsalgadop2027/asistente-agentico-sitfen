# Configura la colección `users` (registro de usuarios / control de sesión WhatsApp):
#   1) Índices: NO se requiere índice compuesto (ver nota). Solo se documenta.
#   2) Reglas de seguridad de Firestore (deny-all a SDKs cliente): se despliegan
#      con Firebase CLI si está disponible; si no, se imprimen las instrucciones.
# (Bloque E — complementa 01_setup_firestore_and_buckets.ps1)
$ErrorActionPreference = "Stop"
$PROJECT = $env:GCP_PROJECT_ID; if (-not $PROJECT) { $PROJECT = "chatbot-agentico-v2" }
$COLL    = $env:FIRESTORE_USERS_COLLECTION; if (-not $COLL) { $COLL = "users" }
$ROOT    = Split-Path -Parent $PSScriptRoot
$RULES   = Join-Path $ROOT "firestore.rules"

Write-Host "== Colección de usuarios: $COLL (proyecto $PROJECT) ==" -ForegroundColor Cyan

# 1) Índices --------------------------------------------------------------------
# Las consultas del registro son:
#   - get_by_whatsapp:  where('whatsapp','==', X).limit(1)   -> igualdad de UN campo
#   - list_users:       stream() completo, ordenado EN MEMORIA por apellido/nombre
# Firestore auto-indexa cada campo por separado, así que la igualdad simple NO
# necesita índice compuesto. No hay ninguna consulta con (filtro + orderBy) sobre
# campos distintos ni con múltiples rangos, que son los casos que sí lo exigirían.
Write-Host "Índices: la colección '$COLL' no requiere índice compuesto." -ForegroundColor Green
Write-Host "  (igualdad de campo único auto-indexada; el listado ordena en memoria)" -ForegroundColor DarkGray

# 2) Reglas de seguridad --------------------------------------------------------
# El backend accede vía Admin SDK (service account de Cloud Run), que OMITE las
# reglas. Estas reglas son defensa en profundidad: bloquean cualquier SDK cliente.
if (-not (Test-Path $RULES)) {
  Write-Host "No se encontró $RULES — omitiendo despliegue de reglas." -ForegroundColor Yellow
  return
}

$firebase = Get-Command firebase -ErrorAction SilentlyContinue
if ($firebase) {
  Write-Host "Desplegando reglas de Firestore con Firebase CLI..." -ForegroundColor Cyan
  try {
    firebase deploy --only firestore:rules --project $PROJECT
    Write-Host "Reglas desplegadas." -ForegroundColor Green
  } catch {
    Write-Host "No se pudieron desplegar las reglas automáticamente: $_" -ForegroundColor Yellow
  }
} else {
  Write-Host "Firebase CLI no está instalado. Para desplegar las reglas (deny-all):" -ForegroundColor Yellow
  Write-Host "  npm i -g firebase-tools" -ForegroundColor DarkGray
  Write-Host "  firebase login" -ForegroundColor DarkGray
  Write-Host "  firebase deploy --only firestore:rules --project $PROJECT" -ForegroundColor DarkGray
  Write-Host "  (usa firebase.json + firestore.rules en la raíz del repo)" -ForegroundColor DarkGray
}

Write-Host "Listo. La colección '$COLL' se crea sola al registrar el primer usuario." -ForegroundColor Green
