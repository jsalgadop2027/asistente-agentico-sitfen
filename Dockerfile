# Imagen del servicio agéntico (FastAPI webhook) para Cloud Run.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

WORKDIR /app

# Dependencias del sistema: libs de imagen para pdfplumber + curl/tar para
# descargar los assets del avatar durante el build.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg62-turbo libpng16-16 curl ca-certificates tar \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.lock .
RUN pip install --upgrade pip && pip install -r requirements.lock

# Cliente de tracing de Confident AI (observabilidad de producción). Se instala
# constreñido por las versiones del stack core para no moverlas; si hubiera un
# conflicto de dependencias, el build falla AQUÍ (no en runtime).
# Nota: pip>=26 rechaza extras (p. ej. uvicorn[standard]) en un archivo -c de
# constraints, y requirements.lock los usa. Se genera una copia solo-versiones
# (extras eliminados con sed) para constreñir de forma válida.
# Además se libera el pin de `click`: DeepEval exige click<8.4.0 y el lock lo fija
# en 8.4.2. click solo lo usan los CLI de uvicorn/streamlit (el servicio corre con
# gunicorn+UvicornWorker, no el CLI), por lo que dejarlo flotar a 8.3.x es seguro
# y es el ÚNICO paquete del stack core que cambia al instalar DeepEval.
COPY requirements-observability.txt .
RUN sed -E -e 's/\[[^][]*\]//g' -e '/^click==/d' requirements.lock > /tmp/core-constraints.txt \
    && pip install -r requirements-observability.txt -c /tmp/core-constraints.txt

COPY app ./app
COPY ingestion ./ingestion
COPY evaluation ./evaluation
COPY web ./web

# --- Auto-hospedaje de los assets del avatar (sin CDN externo en runtime) ---
# La descarga ocurre en build (Cloud Build tiene salida a internet). El navegador
# del usuario luego sirve todo desde el mismo origen de Cloud Run.
# El host de Ready Player Me (models.readyplayer.me) dejó de resolver en DNS, por
# lo que el modelo original ya no se puede descargar. Usamos el avatar de
# referencia de TalkingHead (RPM-compatible: ARKit + Oculus Visemes), alojado en
# su repo y servido por jsdelivr (alcanzable y estable).
ARG THREE_VERSION=0.170.0
ARG TH_VERSION=1.4
ARG MODEL_URL="https://cdn.jsdelivr.net/gh/met4citizen/TalkingHead@1.4/avatars/brunette.glb"
# Animador "Hombre" del selector (ver web/index.html, MODEL_URLS.M). OPCIONAL a
# propósito: a diferencia de MODEL_URL (mujer, requerido, rompe el build si
# falla), esta descarga NO usa `-f` de curl, así que un 404/URL vacía no tumba
# el build entero -- el selector simplemente falla-abierto para esa opción
# (switchAvatar la revierte a "Mujer" con un aviso, ver web/index.html). Pásala
# con --build-arg MALE_MODEL_URL=... o env MALE_MODEL_URL en Cloud Build.
ARG MALE_MODEL_URL=""
# Animador "Robot" del selector (ver web/index.html, MODEL_URLS.R): NO es un
# avatar Ready Player Me, así que NO tiene el rig/blend shapes que exige
# TalkingHead (showAvatar() lanzaría "Blend shapes not found") -- se renderiza
# con un visor Three.js propio, fuera del pipeline de TalkingHead, reproduciendo
# su propia animación "Idle" en loop (sin lipsync ni mirada). "Animated Robot"
# de Quaternius (CC0, sin atribución requerida), alojado en el CDN estático de
# poly.pizza -- cabeza redondeada y ojos grandes, más amigable que la opción
# anterior (RobotExpressive.glb de three.js, con cabeza en forma de caja).
ARG ROBOT_MODEL_URL="https://static.poly.pizza/7d95dbce-8c73-489b-8298-f430b1f0dbdf.glb"
RUN set -eux; \
    mkdir -p web/vendor/three web/vendor/talkinghead; \
    # three.js: build/ completo (three.module.js + three.core.js) y addons (examples/jsm)
    curl -fSL "https://registry.npmjs.org/three/-/three-${THREE_VERSION}.tgz" -o /tmp/three.tgz; \
    tar -xzf /tmp/three.tgz -C /tmp; \
    cp -r /tmp/package/build web/vendor/three/build; \
    mkdir -p web/vendor/three/examples; \
    cp -r /tmp/package/examples/jsm web/vendor/three/examples/jsm; \
    # TalkingHead: módulo principal + dynamicbones (import estático interno) +
    # módulos de lip-sync (lipsyncModules por defecto: fi, en, lt).
    base="https://cdn.jsdelivr.net/gh/met4citizen/TalkingHead@${TH_VERSION}/modules"; \
    for f in talkinghead.mjs dynamicbones.mjs lipsync-fi.mjs lipsync-en.mjs lipsync-lt.mjs; do \
      curl -fSL "$base/$f" -o "web/vendor/talkinghead/$f"; \
    done; \
    # Modelo 3D (mujer, por defecto). Si esta descarga falla (p. ej. el modelo ya
    # no existe en RPM), el build se rompe a propósito -> diagnóstico inequívoco.
    curl -fSL "${MODEL_URL}" -o web/avatar.glb; \
    # Modelo 3D (hombre, opcional -- ver comentario del ARG arriba).
    if [ -n "${MALE_MODEL_URL}" ]; then \
      curl -fSL "${MALE_MODEL_URL}" -o web/avatar_male.glb || echo "AVISO: no se pudo descargar MALE_MODEL_URL, el animador 'Hombre' no estará disponible."; \
    else \
      echo "AVISO: MALE_MODEL_URL no definido, el animador 'Hombre' no estará disponible."; \
    fi; \
    # Modelo 3D (robot, opcional -- ver comentario del ARG arriba).
    if [ -n "${ROBOT_MODEL_URL}" ]; then \
      curl -fSL "${ROBOT_MODEL_URL}" -o web/avatar_robot.glb || echo "AVISO: no se pudo descargar ROBOT_MODEL_URL, el animador 'Robot' no estará disponible."; \
    else \
      echo "AVISO: ROBOT_MODEL_URL no definido, el animador 'Robot' no estará disponible."; \
    fi; \
    rm -f /tmp/three.tgz; rm -rf /tmp/package; \
    echo "=== assets horneados ==="; \
    ls -la web/vendor/three/build web/vendor/talkinghead; \
    wc -c web/avatar.glb; \
    [ -f web/avatar_male.glb ] && wc -c web/avatar_male.glb || true; \
    [ -f web/avatar_robot.glb ] && wc -c web/avatar_robot.glb || true

# Usuario no root (DevSecOps: principio de menor privilegio).
RUN useradd -m appuser
USER appuser

EXPOSE 8080

# gunicorn con 1 worker uvicorn (asíncrono, no bloqueante): el webhook de
# WhatsApp responde el ack de inmediato y procesa en BackgroundTasks, que
# Starlette despacha a un threadpool, así que un solo worker ya atiende
# concurrencia real sin bloquear el event loop. 2 workers duplicaban en
# memoria el índice BM25 (uno por proceso, sin compartir), lo que agotó el
# límite de 1024 MiB del contenedor y provocó reinicios (WhatsApp sin
# respuesta). Con 1 worker el índice se construye una sola vez por instancia.
CMD exec gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 1 --timeout 120 \
    --bind 0.0.0.0:${PORT}
