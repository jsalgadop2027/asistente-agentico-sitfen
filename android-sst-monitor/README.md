# SST Costa Perú — Monitor de temperatura del mar (Android)

App Android nativa (**Kotlin + Jetpack Compose**) que grafica en tiempo real la
**temperatura superficial del mar (SST)** frente a la costa peruana, con foco en las
zonas exportadoras de arándano (Piura, Lambayeque, La Libertad) para el seguimiento
temprano del **Fenómeno de El Niño**.

Complementa el capstone *Smart Agentic Chatbot* como cliente móvil ligero e independiente.
La app tiene **dos pestañas** (barra de navegación inferior):

## Pestaña «Costa» — serie de SST

- Serie horaria de SST: **7 días observados + 3 de pronóstico** por estación.
- Gráfica de líneas propia (Canvas): tramo observado sólido, pronóstico punteado,
  marcador "hoy".
- Tarjeta de temperatura actual con mínima/máxima del rango.
- **Resumen de la costa**: temperatura actual de 9 puertos, de Tumbes a Moquegua.
- Selector de estación y botón de actualización.

Fuente: [Open-Meteo Marine API](https://open-meteo.com/en/docs/marine-weather-api) —
gratuita, sin API key, sin backend propio. Endpoint:

```
GET https://marine-api.open-meteo.com/v1/marine
    ?latitude=-12.06&longitude=-77.16
    &hourly=sea_surface_temperature
    &past_days=7&forecast_days=3&timezone=America/Lima
```

## Pestaña «Satélite» — visor animado del FEN

Puerto nativo del panel web `/satelital` (`arandano-sst-web`). Visor satelital
animado de la **temperatura del mar del norte del Perú**:

- **Animación** de 14 fotogramas diarios (NASA GIBS WMS), reproducción/pausa,
  velocidad (lenta/normal/rápida), barra de avance (*scrub*) y "Repetir".
- Dos **capas**: **Anomalía (FEN)** y **SST absoluta**, cada una con su barra de
  calor (leyenda vertical con el colormap real de GIBS) y opacidad ajustable.
- Dos **vistas**: **Geográfico** (relieve BlueMarble) y **Político** (departamentos
  del Perú rellenos en color, desde `map.json` empaquetado en `assets/`).
- **Referencias** conmutables: costas, ciudades del norte, límites/etiquetas
  departamentales, zonas de arándano (discos verdes), sedes **RedCITE del ITP**
  (rombos ámbar) y puertos del norte (anclas azules).
- **Zoom real como en la web**: pellizca o usa los botones **+ / − / ⟲** (con
  porcentaje respecto al encuadre original); al cambiar el encuadre se **re-piden
  los fotogramas WMS a mayor detalle** y el centro queda acotado a la región
  norte. Arrastra para desplazarte; badge de fecha y barra de escala en km.
- **Auto-actualización**: al volver a la app y cada 12 h se comprueba si GIBS
  publicó un día nuevo (↻ fuerza la recarga); etiquetas «Datos al …» y
  «Comprobado: …» como en la web.

Fuente: **NASA GIBS** (WMS EPSG:4326), producto **GHRSST MUR L4** (~1 km, diario,
~1–2 días de rezago). Público, sin API key. Los fotogramas se descargan como
bitmaps y se retienen en memoria para animar sin re-descargar.

Ambas pestañas consumen las APIs **directamente** (arquitectura independiente; no
tocan tu Cloud Run).

## Requisitos

Esta máquina **no tiene** JDK ni Android Studio instalados. Necesitas:

1. **Android Studio** (Ladybug 2024.2 o superior) — incluye JDK 17, Android SDK y Gradle.
   Descarga: https://developer.android.com/studio
2. Un **emulador** (AVD, API 26+) o un teléfono Android físico con *Depuración USB*.

No hace falta instalar Gradle ni JDK por separado: Android Studio los trae.

## Cómo compilar y ejecutar

1. Abre Android Studio → **Open** → selecciona la carpeta `android-sst-monitor/`.
2. Android Studio sincroniza Gradle y **genera el Gradle wrapper** automáticamente
   (descarga dependencias la primera vez; requiere internet).
3. Selecciona un dispositivo/emulador en la barra superior.
4. Pulsa **Run ▶** (o `Shift+F10`).

### Por línea de comandos (opcional)

Solo si ya tienes JDK 17 + Android SDK configurados. Desde `android-sst-monitor/`
genera primero el wrapper con un Gradle del sistema (`gradle wrapper`), luego:

```bash
./gradlew assembleDebug      # genera app/build/outputs/apk/debug/app-debug.apk
./gradlew installDebug       # instala en el dispositivo conectado
```

En Windows: `gradlew.bat assembleDebug`.

## Estructura

```
android-sst-monitor/
├── settings.gradle.kts / build.gradle.kts   # configuración raíz + versiones de plugins
├── gradle/wrapper/…                          # versión de Gradle (8.11.1)
└── app/
    ├── build.gradle.kts                       # dependencias del módulo
    └── src/main/
        ├── AndroidManifest.xml                # permiso INTERNET
        ├── assets/map.json                    # geometría departamental del Perú (vista Satélite)
        ├── res/…                              # tema, colores, icono adaptativo
        └── java/pe/utec/sstmonitor/
            ├── MainActivity.kt
            ├── data/            # Costa: MarineApi, Models, Locations, SstRepository
            │   └── satellite/   # SatelliteConfig (WMS/encuadre/refs), DepartmentMap,
            │                    # GibsRepository (descarga + caché LRU)
            └── ui/              # RootScreen (nav inferior)
                                 # Costa: SstViewModel, SstScreen, SstLineChart
                ├── satellite/   # SatelliteViewModel, SatelliteScreen, Legends
                └── theme/
```

## Stack

Kotlin 2.1 · Jetpack Compose (BOM 2024.12) · Material 3 · Retrofit 2.11 + Gson ·
Coroutines · minSdk 26 · targetSdk 35.

## Notas

- Requiere conexión a internet (permiso `INTERNET`).
- La SST de Open-Meteo se actualiza por hora; pulsa *Actualizar* para refrescar.
- El visor satelital descarga sus fotogramas de GIBS al abrir la pestaña; con
  conexión lenta puede tardar unos segundos (indicador «Cargando fotogramas
  satelitales…»). Al hacer zoom/pan se re-piden con el nuevo bbox (más detalle),
  con caché LRU en memoria para no re-descargar al alternar capa o encuadre.
- Ampliaciones sugeridas: alertas por umbral de anomalía, notificaciones push,
  y consumo vía tu backend Cloud Run para reutilizar las tools NOAA existentes.
```
