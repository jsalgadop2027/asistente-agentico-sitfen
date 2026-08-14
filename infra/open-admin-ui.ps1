# Abre la Admin UI (carga de documentos) de forma segura mediante un proxy
# autenticado de Cloud Run. El servicio sigue PRIVADO: solo tu cuenta de gcloud
# (con rol run.invoker) puede acceder, vía http://localhost:PORT.
#
# Uso:   powershell -ExecutionPolicy Bypass -File infra\open-admin-ui.ps1
#        (opcional)  -Port 8090
param([int]$Port = 8088)

$ACCOUNT = "jsalgadop2027@gmail.com"
$PROJECT = "chatbot-agentico-v2"
$REGION  = "us-central1"
$SERVICE = "arandano-admin"
$URL     = "http://localhost:$Port"

# 1) Asegura la cuenta correcta (la que tiene permiso run.invoker).
if ((gcloud config get-value account 2>$null) -ne $ACCOUNT) {
  Write-Host "Cambiando cuenta activa a $ACCOUNT ..." -ForegroundColor Yellow
  gcloud config set account $ACCOUNT 2>$null
}

# 2) Lanza el proxy en SU PROPIA ventana (debe quedar abierta mientras la uses).
Write-Host "Iniciando proxy de Cloud Run en una ventana nueva..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList @(
  "-NoExit","-Command",
  "gcloud run services proxy $SERVICE --region $REGION --project $PROJECT --port $Port"
)

# 3) Espera a que el proxy responda y abre el navegador en TU sesión.
Write-Host "Esperando a que $URL responda..." -ForegroundColor Cyan
$ok = $false
for ($i = 0; $i -lt 30; $i++) {
  Start-Sleep -Seconds 1
  try { if ((Invoke-WebRequest "$URL/_stcore/health" -UseBasicParsing -TimeoutSec 3).StatusCode -eq 200) { $ok = $true; break } } catch {}
}
if ($ok) {
  Start-Process $URL
  Write-Host "Listo. Abierto en $URL  (NO uses la URL .run.app)." -ForegroundColor Green
  Write-Host "Para cerrar el acceso, cierra la ventana del proxy." -ForegroundColor Green
} else {
  Write-Host "El proxy no respondió a tiempo. Revisa la ventana del proxy por errores." -ForegroundColor Red
}
