# Construye la imagen de evaluación y crea/actualiza el Cloud Run Job arandano-eval.
# (Bloque opcional - incurre costo de build; el job en sí NO se auto-ejecuta acá,
# ver instrucciones al final. Requiere que infra/03_deploy.ps1 ya se haya corrido
# al menos una vez, para que exista la imagen base arandano-agent:latest.)
$ErrorActionPreference = "Stop"
$PROJECT = $env:GCP_PROJECT_ID; if (-not $PROJECT) { $PROJECT = "chatbot-agentico-v2" }
$REGION  = $env:GCP_REGION;     if (-not $REGION)  { $REGION  = "us-central1" }
$REPO    = "chatbot-repo"
$SVC     = "arandano-agent"
$EVALIMG = "arandano-eval"
$JOB     = "arandano-eval"

$PROJNUM = gcloud projects describe $PROJECT --format="value(projectNumber)"
$SA = "$PROJNUM-compute@developer.gserviceaccount.com"
$BASE = "$REGION-docker.pkg.dev/$PROJECT/$REPO"

# 1) Imagen del job: parte de la imagen del agente YA construida (Dockerfile.eval)
#    y le agrega requirements-eval.txt (ragas, deepeval) encima — deliberadamente
#    fuera de la imagen de producción (ver CLAUDE.md), sin reconstruir el resto.
Write-Host "Construyendo imagen de evaluación (agente + requirements-eval.txt)..." -ForegroundColor Cyan
gcloud builds submit --config=infra/cloudbuild.eval.yaml `
  --substitutions="_BASE_IMAGE=$BASE/$SVC`:latest,_IMAGE=$BASE/$EVALIMG`:latest" `
  --project=$PROJECT .

# 2) Mismas env vars/secretos que el job de ingesta: Firestore + Vertex AI vía la
#    service account de producción (ya tiene aiplatform.user, datastore.user, etc.
#    otorgados en infra/03_deploy.ps1 paso 2).
$ENVVARS = "ENVIRONMENT=production,GCP_PROJECT_ID=$PROJECT,GCP_REGION=$REGION,GCP_LOCATION=$REGION"
$COMMON_SECRETS = "PII_HASH_SALT=pii-hash-salt:latest"

# 3) Un solo job, 3 modos seleccionables por --args en cada ejecución (el --args
#    de creación es solo el default; se puede sobreescribir sin necesidad de
#    `jobs update`):
#      evaluation.build_golden_dataset  -> genera golden_dataset_v2.jsonl (180 preg.)
#      evaluation.run_all               -> RAGAS+DeepEval sobre golden_dataset_v2.jsonl
#      evaluation.derivation_eval       -> precisión/recall de identificar_entidades
#    task-timeout generoso (3h): la corrida de run_all sobre ~180 preguntas con
#    juez Gemini Pro puede tardar por el rate-limiting de cuota que el propio
#    código ya anticipa (ver evaluation/run_all.py::_retry_on_quota).
Write-Host "Creando/actualizando job de evaluación $JOB..." -ForegroundColor Cyan
try {
  gcloud run jobs create $JOB --image "$BASE/$EVALIMG`:latest" --region=$REGION --project=$PROJECT `
    --service-account=$SA --memory=2Gi --cpu=2 --task-timeout=10800 --max-retries=0 `
    --set-env-vars=$ENVVARS --set-secrets=$COMMON_SECRETS `
    --command="python" --args="-m,evaluation.build_golden_dataset"
} catch {
  gcloud run jobs update $JOB --image "$BASE/$EVALIMG`:latest" --region=$REGION --project=$PROJECT `
    --task-timeout=10800 --set-env-vars=$ENVVARS --set-secrets=$COMMON_SECRETS
}

Write-Host "`nListo: imagen construida y job registrado. Este script NO ejecuta el job." -ForegroundColor Green
Write-Host "Correrlo genera costo real de Vertex AI. Orden recomendado:" -ForegroundColor Yellow
Write-Host "  1) Generar el golden dataset nuevo (~180 preguntas, corpus de 200 PDFs)," -ForegroundColor White
Write-Host "     sube a gs://<bucket>/eval/golden_dataset_v2.jsonl (sin --out, el" -ForegroundColor White
Write-Host "     filesystem del job es efímero):" -ForegroundColor White
Write-Host "     gcloud run jobs execute $JOB --region=$REGION --project=$PROJECT ``" -ForegroundColor White
Write-Host "       --args=`"-m,evaluation.build_golden_dataset,--n,180,--floor,15`"" -ForegroundColor White
Write-Host "     Bajarlo al repo antes del paso 2 (run_all.py lee el archivo local):" -ForegroundColor White
Write-Host "     gsutil cp gs://$PROJECT-corpus/eval/golden_dataset_v2.jsonl evaluation/golden_dataset_v2.jsonl" -ForegroundColor White
Write-Host "  2) Evaluar respuestas RAG (RAGAS + DeepEval) contra el golden dataset" -ForegroundColor White
Write-Host "     (sube resultado a gs://<bucket>/eval/results.json):" -ForegroundColor White
Write-Host "     gcloud run jobs execute $JOB --region=$REGION --project=$PROJECT --args=`"-m,evaluation.run_all`"" -ForegroundColor White
Write-Host "  3) Evaluar derivación a entidades (precisión/recall, sin LLM juez;" -ForegroundColor White
Write-Host "     sube a gs://<bucket>/eval/derivation_results.json):" -ForegroundColor White
Write-Host "     gcloud run jobs execute $JOB --region=$REGION --project=$PROJECT --args=`"-m,evaluation.derivation_eval`"" -ForegroundColor White
