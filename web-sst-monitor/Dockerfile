# Micro-servicio: FastAPI que sirve la página y actúa de proxy a NOAA CoastWatch
# (ERDDAP no envía CORS, así que la consulta va del lado del servidor). Independiente:
# no comparte imagen ni secretos con el agente. Sin API key (ERDDAP es abierto).
FROM python:3.12-slim

WORKDIR /app
ENV PORT=8080 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py index.html mapa_google.html satelital.html satelital_google.html consola.html map.json icen_igp.csv ./

EXPOSE 8080
# Shell form para expandir $PORT (Cloud Run lo inyecta = 8080).
CMD exec uvicorn app:app --host 0.0.0.0 --port ${PORT}
