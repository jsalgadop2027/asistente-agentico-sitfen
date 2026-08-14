# Crea el índice vectorial COMPUESTO para la memoria semántica de largo plazo.
# La búsqueda `recall` prefiltra por user_id y luego hace KNN sobre `embedding`,
# por lo que Firestore exige un índice compuesto (user_id + vector). (Bloque F)
$ErrorActionPreference = "Stop"
$PROJECT = $env:GCP_PROJECT_ID; if (-not $PROJECT) { $PROJECT = "chatbot-agentico-v2" }
$COLL    = $env:FIRESTORE_CONV_MEMORY_COLLECTION; if (-not $COLL) { $COLL = "conversation_memory" }
$DIM     = $env:EMBEDDING_DIM; if (-not $DIM) { $DIM = "768" }

Write-Host "Creando índice vectorial compuesto (user_id + embedding, dim=$DIM) para '$COLL'..." -ForegroundColor Cyan
# El valor JSON de vector-config pierde las comillas al pasar por PowerShell ->
# gcloud.ps1 -> python; se invoca vía cmd /c con comillas escapadas (\") para que
# el runtime de gcloud reciba un JSON válido: {"dimension":N,"flat":{}}.
$vc = "vector-config={\`"dimension\`":$DIM,\`"flat\`":{}}"
$create = "gcloud firestore indexes composite create " +
          "--collection-group=$COLL --query-scope=COLLECTION " +
          "--field-config=field-path=user_id,order=ASCENDING " +
          "--field-config=field-path=embedding,$vc --project=$PROJECT"
cmd /c $create
if ($LASTEXITCODE -eq 0) {
  Write-Host "Índice solicitado. Puede tardar varios minutos en quedar ACTIVO." -ForegroundColor Green
} else {
  Write-Host "El índice ya existe o hubo un aviso (revisa el mensaje de gcloud arriba)." -ForegroundColor Yellow
}

Write-Host "Nota: mientras el índice no esté ACTIVO, la memoria semántica es fail-open" -ForegroundColor DarkGray
Write-Host "      (recall devuelve [] y no rompe la respuesta del agente)." -ForegroundColor DarkGray
