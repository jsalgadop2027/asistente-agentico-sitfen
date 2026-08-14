# Sube el corpus a GCS, dispara la ingesta y crea una alerta de presupuesto.
# (Bloque B) — guardrail de costo (requisito "costos más bajos posibles").
$ErrorActionPreference = "Stop"
$PROJECT = $env:GCP_PROJECT_ID; if (-not $PROJECT) { $PROJECT = "chatbot-agentico-v2" }
$REGION  = $env:GCP_REGION;     if (-not $REGION)  { $REGION  = "us-central1" }
$CORPUS  = $env:GCS_CORPUS_BUCKET; if (-not $CORPUS) { $CORPUS = "$PROJECT-corpus" }
$JOB     = "arandano-ingest"
$AMOUNT  = $env:BUDGET_AMOUNT; if (-not $AMOUNT) { $AMOUNT = "20" }  # USD/mes

# 1) Subir corpus local a GCS.
Write-Host "Subiendo corpus a gs://$CORPUS ..." -ForegroundColor Cyan
gcloud storage cp "corpus_documental/*.pdf" "gs://$CORPUS/" --project=$PROJECT

# 2) Ejecutar la ingesta (Cloud Run Job) -> embeddings a Firestore.
Write-Host "Ejecutando job de ingesta..." -ForegroundColor Cyan
gcloud run jobs execute $JOB --region=$REGION --project=$PROJECT --wait

# 3) Alerta de presupuesto (requiere billing account).
$BILLING = gcloud beta billing projects describe $PROJECT --format="value(billingAccountName)"
if ($BILLING) {
  $BACCT = $BILLING -replace "billingAccounts/", ""
  Write-Host "Creando alerta de presupuesto ($AMOUNT USD/mes)..." -ForegroundColor Cyan
  try {
    gcloud billing budgets create --billing-account=$BACCT `
      --display-name="Budget-$PROJECT" `
      --budget-amount="$AMOUNT`USD" `
      --threshold-rule=percent=0.5 --threshold-rule=percent=0.9 --threshold-rule=percent=1.0
  } catch { Write-Host "No se pudo crear el budget (revisa permisos de billing)." -ForegroundColor Yellow }
} else {
  Write-Host "Sin billing account visible: omite alerta de presupuesto." -ForegroundColor Yellow
}

Write-Host "Corpus ingestado y guardrail de costo configurado." -ForegroundColor Green
