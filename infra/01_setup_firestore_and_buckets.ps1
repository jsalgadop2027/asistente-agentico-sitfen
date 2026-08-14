# Crea la base Firestore nativa, el índice vectorial KNN y los buckets de GCS.
# (Bloque B)
$ErrorActionPreference = "Stop"
$PROJECT  = $env:GCP_PROJECT_ID;     if (-not $PROJECT)  { $PROJECT  = "chatbot-agentico-v2" }
$REGION   = $env:GCP_REGION;         if (-not $REGION)   { $REGION   = "us-central1" }
$CORPUS   = $env:GCS_CORPUS_BUCKET;  if (-not $CORPUS)   { $CORPUS   = "$PROJECT-corpus" }
$AUDIO    = $env:GCS_AUDIO_BUCKET;   if (-not $AUDIO)    { $AUDIO    = "$PROJECT-audio" }
$COLL     = $env:FIRESTORE_VECTOR_COLLECTION; if (-not $COLL) { $COLL = "corpus_chunks" }
$DIM      = $env:EMBEDDING_DIM;      if (-not $DIM)      { $DIM      = "768" }

# 1) Firestore nativo (idempotente: ignora error si ya existe).
Write-Host "Creando Firestore nativo en $REGION..." -ForegroundColor Cyan
try {
  gcloud firestore databases create --location=$REGION --type=firestore-native --project=$PROJECT
} catch { Write-Host "Firestore ya existe o no se pudo recrear (continuando)." -ForegroundColor Yellow }

# 2) Índice vectorial KNN sobre el campo 'embedding'.
Write-Host "Creando índice vectorial KNN (dim=$DIM)..." -ForegroundColor Cyan
try {
  gcloud firestore indexes composite create `
    --collection-group=$COLL `
    --query-scope=COLLECTION `
    --field-config="field-path=embedding,vector-config={`"dimension`":$DIM,`"flat`":{}}" `
    --project=$PROJECT
} catch { Write-Host "El índice ya existe o se está creando (continuando)." -ForegroundColor Yellow }

# 3) Buckets de GCS.
foreach ($b in @($CORPUS, $AUDIO)) {
  Write-Host "Creando bucket gs://$b ..." -ForegroundColor Cyan
  try {
    gcloud storage buckets create "gs://$b" --location=$REGION --project=$PROJECT `
      --uniform-bucket-level-access
  } catch { Write-Host "Bucket gs://$b ya existe (continuando)." -ForegroundColor Yellow }
}

Write-Host "Firestore, índice vectorial y buckets listos." -ForegroundColor Green
Write-Host "NOTA: el índice vectorial puede tardar varios minutos en quedar ACTIVO." -ForegroundColor Yellow
