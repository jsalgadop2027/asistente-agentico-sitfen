# SST Costa Perú — Monitor de temperatura del mar (Web)

Versión **web** del monitor [`android-sst-monitor`](../android-sst-monitor): grafica la
**temperatura superficial del mar (SST)** frente a la costa peruana, con foco en las zonas
exportadoras de arándano (Piura, Lambayeque, La Libertad) para el seguimiento temprano del
**Fenómeno de El Niño**. Complementa el capstone *Smart Agentic Chatbot*.

## Fuente de la verdad: NOAA

La SST proviene de **NOAA CoastWatch** — producto *Blended 5 km Global Sea Surface
Temperature (NRT)*, variable `analysed_sst`, servido vía **ERDDAP**:

```
https://coastwatch.noaa.gov/erddap/griddap/noaacwBLENDEDCsstDaily.json
```

- **Diaria, observada/analizada** (satélite + boyas), latencia ~1–2 días. **Sin pronóstico**
  (NOAA es análisis, no un modelo predictivo).
- ERDDAP **no envía cabeceras CORS**, así que el navegador **no** puede consultarlo directo.
  Por eso este monitor tiene un **backend propio** (FastAPI) que consulta NOAA del lado del
  servidor y expone una API del mismo origen. Sin API key (ERDDAP es abierto).
- Las coordenadas costeras suelen caer en píxeles de tierra (NaN); el backend pide una caja
  sesgada mar adentro y elige la **celda de mar válida más cercana**.

## Qué hace

- **Mapa de calor**: contorno del Perú (SVG) con el **océano Pacífico coloreado** por la SST
  (gradiente latitudinal, rampa térmica, dominio fijo 14–28 °C) y pines por estación.
- Tarjeta de temperatura actual (última lectura NOAA) con mínima/máxima.
- Gráfica de líneas de la SST diaria observada (últimos ~10 días).
- **Resumen de la costa**: SST actual de 9 puertos, de Tumbes a Moquegua.
- Selector de estación, botón de actualización, tema claro/oscuro automático.

## Insignia de alerta FEN

`/satelital` y `/satelital-google` muestran, a simple vista bajo el título, una insignia
coloreada con el **nivel de alerta vigente para la costa norte**. Endpoint:
`GET /api/fen-status`.

Las tres fuentes miden lo mismo —la anomalía de TSM en la región **Niño 1+2** (90°-80°W,
10°S-0°), la misma caja sobre la que el IGP calcula el ICEN, y no la caja "norte de Perú"
que acota la vista satelital, que es solo el encuadre visual del mapa— y degradan en
cascada **por frescura**: esto es una señal TEMPRANA, así que el dato de anteayer vale más
que el de la semana pasada. Contrastadas el 13-ago-2026 coincidían (+4.39 satélite, +4.10
semanal del CPC, +1.98 el ICEN rezagado de mayo), así que preferir la más reciente no
sacrifica exactitud. Se refresca ~cada hora.

**1. Primaria: anomalía diaria de NOAA Coral Reef Watch** (`noaacrwsstanomalyDaily` en el
ERDDAP de `coastwatch.noaa.gov`, el mismo host que sirve el resto de esta API) — 5 km,
promediada por coseno de latitud sobre la caja Niño 1+2 y sobre los **últimos 5 días**
(`FEN_SMOOTH_DAYS`, evita que un solo día ruidoso —huecos de nubes, un pico costero
puntual— dispare un salto de categoría). Diaria, con ~2 días de latencia.

**2. Respaldo: índice semanal Niño 1+2 de la NOAA/CPC** (`wksst9120.for`, sobre OISSTv2.1,
base 1991-2020). Es el número que el CPC publica en su boletín ENSO, ya calculado sobre la
región estándar: no lo promediamos nosotros. Se actualiza los lunes, con ~2-3 días de
rezago, y es texto plano —sin ERDDAP de por medio—, así que sigue en pie si ERDDAP cae.
(El archivo hermano `wksst8110.for`, base 1981-2010, quedó congelado en enero de 2021: no
usarlo.)

> Hasta agosto de 2026 la primaria era la anomalía **GHRSST MUR L4** vía
> `jplMURSST41anom1day` en `coastwatch.pfeg.noaa.gov`. Ese servidor dejó de aceptar
> conexiones (443 rechazado; `upwell.pfeg.noaa.gov` igual), así que la insignia llevaba
> tiempo cayendo **en silencio** al ICEN y mostrando un FEN mucho más benigno que el real.
> Los fallos de fuente ahora se loguean. El overlay animado de los visores sigue siendo MUR
> vía teselas WMS de NASA GIBS: eso no se vio afectado.

**3. Última red: ICEN del IGP** — el último **ICEN** (Índice Costero El Niño) publicado por
el **IGP**, leído de `icen_igp.csv` (copia de [`datasets/icen_igp.csv`](../datasets/icen_igp.csv);
actualizar reemplazando ese archivo cuando el IGP publique un mes nuevo). Se publica con
~2-3 meses de rezago por control de calidad, así que solo sirve cuando fallan las otras dos.

Las tres fuentes comparten la misma clasificación oficial de 8 niveles usada por ENFEN: Frío
fuerte/moderado/débil, Neutro, y Cálido débil/moderado/fuerte/**extraordinario**. Umbrales
(°C, valor ≥ umbral):

Además del texto ya armado (`display`/`tooltip`), la respuesta trae `value` (el número crudo:
la anomalía en °C o el ICEN) y `date` (fecha corta) para consumidores que necesiten el dato
sin parsear el texto — así lo usa `app.sst_alert` (alerta por WhatsApp) como fuente única,
en vez de recalcular su propia anomalía.

| Nivel | Umbral | Color |
|---|---|---|
| Cálido extraordinario | ≥ 3.0 | `#7c3aad` (morado) |
| Cálido fuerte | ≥ 1.7 | `#dc2626` (rojo) |
| Cálido moderado | ≥ 1.0 | `#f97316` (naranja) |
| Cálido débil | ≥ 0.4 | `#eab308` (amarillo) |
| Neutro | ≥ −0.4 | `#6b7280` (gris) |
| Frío débil | ≥ −1.2 | `#93c5fd` (celeste) |
| Frío moderado | ≥ −1.7 | `#3b82f6` (azul) |
| Frío fuerte | < −1.7 | `#1d4ed8` (azul oscuro) |

## Vistas alternativas

Mismo backend (`app.py`), tres páginas adicionales servidas aparte de `/`:

- **`/mapa-google`** (`mapa_google.html`) — copia de la vista principal con el mapa SVG
  propio reemplazado por un **mapa real de Google Maps** (calles, relieve, satélite y
  Street View) para mayor detalle de geolocalización; los marcadores por estación
  siguen coloreados por SST con la misma rampa. Requiere una clave de la **Maps
  JavaScript API** (ver abajo); sin ella, la tarjeta del mapa muestra un aviso y el
  resto de la página (gráfica, resumen, selector) funciona igual. Lleva también la
  insignia de alerta FEN (`GET /api/fen-status`): era la única vista sin ella, así
  que mostraba SST puntual sin decir en qué nivel está el fenómeno.
- **`/satelital`** (`satelital.html`) — visor animado con teselas **NASA GIBS / GHRSST
  MUR L4** (anomalía y SST absoluta) sobre un bbox editable del norte del Perú, con mapa
  base propio (BlueMarble + costas + límites departamentales dibujados a mano).
- **`/satelital-google`** (`satelital_google.html`) — la misma animación de NASA GIBS
  (anomalía/SST, controles de reproducción/velocidad/opacidad, marcadores de ciudades,
  zonas de arándano, sedes RedCITE y puertos) pero con el mapa base propio reemplazado
  por un **mapa real de Google Maps**: calles, relieve, satélite y Street View, con
  nombres y límites reales en vez de la proyección estilizada a mano. El fotograma
  satelital se pinta como overlay sincronizado al viewport de Google (se vuelve a pedir
  automáticamente cuando el usuario termina de mover/hacer zoom el mapa); el zoom/pan ya
  no es un estado propio sino el nativo de Google (rueda del mouse sin Ctrl, pellizco en
  móvil). Por eso ya no tiene los controles «Vista del mapa» (Geográfico/Político) ni los
  checks «Costas»/«Departamentos» de la versión clásica: Google los reemplaza con su
  propio selector de tipo de mapa y su cartografía real. Requiere la misma
  `GOOGLE_MAPS_API_KEY` que `/mapa-google` (ver abajo).
- **`/consola`** (`consola.html`) — copia de `/satelital` + consola bidireccional de
  WhatsApp (texto y voz) de un solo usuario, vía proxy a `/api/live/*`.

### Configurar el mapa de Google (`/mapa-google`, `/satelital-google`)

1. En Google Cloud Console: habilita **Maps JavaScript API** y crea una clave de API.
2. Restríngela por **HTTP referrer** al dominio donde corre este servicio (y a
   `http://localhost:8080/*` para pruebas locales) — así se protege sin necesidad de
   ocultarla (el SDK de Maps JS se ejecuta en el navegador, no es un secreto de backend).
3. Expórtala como `GOOGLE_MAPS_API_KEY` antes de correr el servicio local o el script de
   despliegue (`infra/07_deploy_sst_web.ps1` la inyecta en Cloud Run si está definida).
   La misma clave habilita ambas vistas.

## Arquitectura

```
Navegador  ──/api/sst, /api/series──►  FastAPI (este servicio)  ──ERDDAP──►  NOAA CoastWatch
   (mismo origen, sin CORS)              (uvicorn, cachea 1/día)             (blended SST NRT)
```

El navegador solo habla con `/api/*` del mismo origen (CSP `connect-src 'self'`). La única
salida a Internet ocurre server-side, hacia NOAA.

## Cómo ejecutar (local)

```bash
cd web-sst-monitor
pip install -r requirements.txt
uvicorn app:app --reload --port 8080
# abre http://localhost:8080
```

Requiere conexión a Internet (el backend consulta NOAA). Endpoints:
`GET /api/sst?lat&lon`, `GET /api/series?lat&lon&days`, `GET /health`.

## Despliegue en GCP (Cloud Run)

Servicio Cloud Run **independiente** (`arandano-sst-web`): imagen `python:3.12-slim` con
uvicorn. Público, **escala a cero** (costo ~0 en reposo), HTTPS automático, sin secretos.

```powershell
infra/07_deploy_sst_web.ps1
```

Construye la imagen desde este folder (`gcloud builds submit`) y despliega el servicio
(`gcloud run deploy`, 512Mi). Para republicar tras un cambio, vuelve a correr el script.

## Estructura

```
web-sst-monitor/
├── index.html         # UI: mapa SVG + gráfica Canvas + lógica de render (llama a /api/*)
├── mapa_google.html   # Copia de index.html con mapa real de Google Maps (ver /mapa-google)
├── satelital.html     # Visor animado NASA GIBS (ver /satelital)
├── satelital_google.html # satelital.html sobre mapa real de Google Maps (ver /satelital-google)
├── consola.html       # satelital.html + consola de WhatsApp en vivo (ver /consola)
├── map.json           # Geometría de departamentos/Ecuador/océano (index.html, satelital.html)
├── icen_igp.csv       # Copia de datasets/icen_igp.csv, respaldo de GET /api/fen-status
├── app.py             # FastAPI: sirve las páginas + proxy a NOAA (/api/sst, /api/series)
├── requirements.txt   # fastapi, uvicorn, httpx
├── Dockerfile         # python:3.12-slim + uvicorn
└── .dockerignore
```

Script de despliegue: [`infra/07_deploy_sst_web.ps1`](../infra/07_deploy_sst_web.ps1).

## Notas

- La SST blended de NOAA se actualiza a diario; pulsa *Actualizar* (↻) para refrescar.
  El backend cachea por celda/día para no golpear ERDDAP en cada carga.
- ERDDAP rechaza (403) User-Agents de librería genéricos: el backend se identifica con un
  User-Agent descriptivo.
- Ampliaciones sugeridas: modo **anomalía** (SST vs. climatología, que justificaría una
  escala divergente de alerta), alertas por umbral, y contraste con boyas/ENFEN.
```
