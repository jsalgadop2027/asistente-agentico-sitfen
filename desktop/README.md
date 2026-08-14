# SITFEN Desktop — Cliente ligero de escritorio (Electron)

Versión de escritorio (Windows/macOS/Linux) del chatbot agéntico **SITFEN**. Reutiliza
el mismo frontend del avatar 3D y consume el backend agéntico (RAG + guardrails +
TTS) desplegado en **Cloud Run** (`/api/chat`, `/api/tts`). Enfoque **Opción A:
cliente ligero** — la lógica de IA vive en la nube; el escritorio es la interfaz.

## Arquitectura
- **Electron** abre una ventana y sirve el frontend local (`renderer/`) por HTTP en
  `127.0.0.1` (necesario para que funcionen los ES modules + importmap del avatar).
- El avatar (TalkingHead + three.js), el modelo `.glb` y los módulos de lip-sync van
  **empaquetados localmente** en `renderer/vendor/` y `renderer/avatar.glb` (sin CDNs).
- Las llamadas de chat y voz salen al backend definido en `renderer/index.html`:
  `const API_BASE = "https://arandano-agent-...run.app"`.

## Requisitos
- **Node.js 18+** (incluye npm).

## Puesta en marcha (desarrollo)
```powershell
cd desktop
# (Opcional) re-descargar assets del avatar si renderer/vendor está vacío:
npm run fetch-assets
npm install      # instala Electron
npm start        # abre la app
```

## Generar instalador distribuible

**Opción A — en la nube (recomendado, no requiere Node/electron-builder ni
Windows instalados localmente):**
```powershell
powershell -ExecutionPolicy Bypass -File infra\09_build_desktop.ps1
```
Corre en Cloud Build (`infra/cloudbuild.desktop.yaml`) con la imagen oficial
`electronuserland/builder:wine` — genera el `.exe` (NSIS) vía Wine sobre
Linux, sin necesitar una máquina Windows (Cloud Build no ofrece workers
Windows en su pool estándar). Descarga los assets del avatar y publica el
instalador en `gs://chatbot-agentico-v2-desktop-builds/desktop/`:
```powershell
gcloud storage cp gs://chatbot-agentico-v2-desktop-builds/desktop/*.exe . --project=chatbot-agentico-v2
```

**Opción B — local:**
```powershell
npm run dist     # genera instalador en desktop/dist/ (NSIS .exe en Windows)
```
Recomendado firmar el binario (evita avisos de SmartScreen/Gatekeeper).

## Configuración
- **Backend:** edita `API_BASE` en `renderer/index.html` si cambia la URL del servicio.
- **El servicio debe estar ACTIVO.** Si el chatbot fue desactivado (IAM revocado),
  reactívalo o el cliente recibirá **403**:
  ```powershell
  gcloud run services add-iam-policy-binding arandano-agent --region us-central1 \
    --project chatbot-agentico-v2 --member=allUsers --role=roles/run.invoker
  ```

## Limitaciones conocidas / próximos pasos
- **Micrófono:** usa la Web Speech API del navegador; en Electron puede no transcribir
  de forma fiable. Mejora prevista: grabar con `MediaRecorder` y enviar a un endpoint
  `/api/stt` (reusando `app/voice/stt.py`, Google Speech).
- **Autenticación:** hoy depende de que el backend sea público (con sus guardrails y
  rate-limiting). Para distribución amplia, añadir API key o login (Firebase/Google).
- **Auto-actualización:** integrar `electron-updater` para releases.

Desarrollado por el Ing. Julio Salgado.
