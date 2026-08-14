# Habilita las APIs facturables necesarias. (Bloque B - requiere billing activo)
# Habilitar APIs no genera costo; el costo viene del uso.
$ErrorActionPreference = "Stop"
$PROJECT = $env:GCP_PROJECT_ID; if (-not $PROJECT) { $PROJECT = "chatbot-agentico-v2" }

Write-Host "Proyecto: $PROJECT" -ForegroundColor Cyan

$apis = @(
  "aiplatform.googleapis.com",        # Vertex AI (Gemini, embeddings, Model Garden)
  "run.googleapis.com",               # Cloud Run (servicio + job)
  "cloudbuild.googleapis.com",        # Cloud Build (build de imágenes)
  "artifactregistry.googleapis.com",  # Artifact Registry (imágenes)
  "firestore.googleapis.com",         # Firestore (vectores + memoria)
  "secretmanager.googleapis.com",     # Secret Manager (Twilio/LangSmith)
  "speech.googleapis.com",            # Speech-to-Text (voz entrante)
  "texttospeech.googleapis.com",      # Text-to-Speech (voz saliente)
  "storage.googleapis.com",           # Cloud Storage (corpus + audio)
  "monitoring.googleapis.com",        # Observabilidad
  "logging.googleapis.com",
  "cloudtrace.googleapis.com"
)

gcloud services enable $apis --project=$PROJECT
Write-Host "APIs habilitadas correctamente." -ForegroundColor Green
