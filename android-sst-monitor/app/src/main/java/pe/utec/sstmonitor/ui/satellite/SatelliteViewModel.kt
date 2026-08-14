package pe.utec.sstmonitor.ui.satellite

import android.app.Application
import android.graphics.Bitmap
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import pe.utec.sstmonitor.data.satellite.DepartmentMap
import pe.utec.sstmonitor.data.satellite.GibsRepository
import pe.utec.sstmonitor.data.satellite.MapViewMode
import pe.utec.sstmonitor.data.satellite.SatLayer
import pe.utec.sstmonitor.data.satellite.SatelliteConfig
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import kotlin.math.abs

/** America/Lima es fija en UTC-5 (Perú no observa horario de verano). */
private val LIMA_ZONE: ZoneId = ZoneId.of("America/Lima")

/**
 * Estado del visor satelital. Es el equivalente movil del estado del visor web
 * /satelital: misma ventana de fechas, capa activa, encuadre (centro + amplitud
 * en longitud) y preferencias de animacion/referencias.
 */
data class SatelliteUiState(
    val view: MapViewMode = MapViewMode.GEO,
    val layer: SatLayer = SatLayer.ANOM,
    val dates: List<LocalDate> = emptyList(),
    /** Fotogramas por fecha (null = sin dato o aun no descargado). */
    val frames: List<Bitmap?> = emptyList(),
    val frameIdx: Int = 0,
    val playing: Boolean = false,
    val fps: Float = 3f,
    val loop: Boolean = true,
    val opacity: Float = SatLayer.ANOM.defaultOpacity,
    val showCoast: Boolean = true,
    val showCities: Boolean = true,
    val showDepts: Boolean = true,
    val showZones: Boolean = true,
    val showCite: Boolean = true,
    val showPorts: Boolean = true,
    val showLabels: Boolean = true,
    // Encuadre: centro + amplitud en longitud (latSpan = lonSpan * RATIO_LAT).
    val cLon: Double = SatelliteConfig.DEF_CLON,
    val cLat: Double = SatelliteConfig.DEF_CLAT,
    val lonSpan: Double = SatelliteConfig.MAX_SPAN,
    val baseBitmap: Bitmap? = null,
    val coastBitmap: Bitmap? = null,
    val loading: Boolean = true,
    /** Ultima comprobacion de datos nuevos, fijada a hora de Lima (no la del dispositivo). */
    val checkedAt: LocalDateTime? = null,
    val departments: DepartmentMap? = null,
)

class SatelliteViewModel(app: Application) : AndroidViewModel(app) {

    private val repo = GibsRepository()

    private val _state = MutableStateFlow(SatelliteUiState(dates = SatelliteConfig.buildDates()))
    val state: StateFlow<SatelliteUiState> = _state.asStateFlow()

    private var framesJob: Job? = null
    private var staticJob: Job? = null

    init {
        // Geometria departamental (asset local; si falla, el mapa sale sin limites).
        viewModelScope.launch(Dispatchers.IO) {
            DepartmentMap.load(getApplication<Application>())?.let { map ->
                _state.update { it.copy(departments = map) }
            }
        }

        _state.update { it.copy(checkedAt = LocalDateTime.now(LIMA_ZONE)) }
        applyView()

        // Reloj de reproduccion: un unico bucle que lee fps/estado en cada tick.
        viewModelScope.launch {
            while (true) {
                val s = _state.value
                if (s.playing && !s.loading && s.frames.isNotEmpty()) {
                    delay((1000f / s.fps).toLong())
                    advanceFrame()
                } else {
                    delay(120)
                }
            }
        }

        // Auto-actualizacion cada 12 h (ademas del ON_RESUME que dispara la pantalla).
        viewModelScope.launch {
            while (true) {
                delay(12 * 3600 * 1000L)
                refreshData(force = false)
            }
        }
    }

    // --- Animacion -----------------------------------------------------------

    private fun advanceFrame() {
        _state.update { s ->
            var next = s.frameIdx + 1
            if (next >= s.frames.size) {
                if (!s.loop) return@update s.copy(playing = false)  // sin "Repetir": se detiene
                next = 0                                            // con "Repetir": vuelve al inicio
            }
            s.copy(frameIdx = next)
        }
    }

    fun togglePlay() {
        _state.update { s ->
            if (s.playing) {
                s.copy(playing = false)
            } else {
                // Si quedo al final sin bucle, reproducir re-arranca desde el inicio.
                val idx = if (s.frameIdx >= s.frames.size - 1 && !s.loop) 0 else s.frameIdx
                s.copy(playing = true, frameIdx = idx)
            }
        }
    }

    fun scrubTo(i: Int) {
        _state.update { s ->
            if (s.frames.isEmpty()) s
            else s.copy(playing = false, frameIdx = i.coerceIn(0, s.frames.size - 1))
        }
    }

    fun setFps(fps: Float) = _state.update { it.copy(fps = fps) }
    fun setLoop(loop: Boolean) = _state.update { it.copy(loop = loop) }
    fun setOpacity(opacity: Float) = _state.update { it.copy(opacity = opacity) }
    fun setViewMode(mode: MapViewMode) = _state.update { it.copy(view = mode) }

    fun setLayer(layer: SatLayer) {
        if (layer == _state.value.layer) return
        _state.update { it.copy(layer = layer, opacity = layer.defaultOpacity) }
        loadFrames()
    }

    // --- Referencias ----------------------------------------------------------

    fun setShowCoast(v: Boolean) = _state.update { it.copy(showCoast = v) }
    fun setShowCities(v: Boolean) = _state.update { it.copy(showCities = v) }
    fun setShowDepts(v: Boolean) = _state.update { it.copy(showDepts = v) }
    fun setShowZones(v: Boolean) = _state.update { it.copy(showZones = v) }
    fun setShowCite(v: Boolean) = _state.update { it.copy(showCite = v) }
    fun setShowPorts(v: Boolean) = _state.update { it.copy(showPorts = v) }
    fun setShowLabels(v: Boolean) = _state.update { it.copy(showLabels = v) }

    // --- Zoom / pan -----------------------------------------------------------

    fun zoomIn() = zoomByFactor(0.66)
    fun zoomOut() = zoomByFactor(1 / 0.66)

    private fun zoomByFactor(factor: Double) {
        val s = _state.value
        val newSpan = (s.lonSpan * factor).coerceIn(SatelliteConfig.MIN_SPAN, SatelliteConfig.MAX_SPAN)
        if (abs(newSpan - s.lonSpan) < 1e-6) return
        val (lon, lat) = SatelliteConfig.clampCenter(s.cLon, s.cLat, newSpan)
        _state.update { it.copy(cLon = lon, cLat = lat, lonSpan = newSpan) }
        applyView()
    }

    /** Restablece la vista al encuadre original (100%). */
    fun resetView() {
        _state.update {
            it.copy(
                cLon = SatelliteConfig.DEF_CLON,
                cLat = SatelliteConfig.DEF_CLAT,
                lonSpan = SatelliteConfig.MAX_SPAN,
            )
        }
        applyView()
    }

    /**
     * Consolida un gesto de pellizco/arrastre. El gesto acumulado mapea el punto p
     * del contenido a scale*p + offset en pantalla; de ahi se despeja el nuevo
     * centro y amplitud, se acota a la region y se re-piden las imagenes.
     */
    fun commitGesture(scale: Float, offsetX: Float, offsetY: Float, widthPx: Float, heightPx: Float) {
        if (widthPx <= 0f || heightPx <= 0f) return
        if (abs(scale - 1f) < 0.01f && abs(offsetX) < 2f && abs(offsetY) < 2f) return  // fue un toque
        val s = _state.value
        val b = SatelliteConfig.bounds(s.cLon, s.cLat, s.lonSpan)
        // Fraccion del contenido que quedo en el centro de la pantalla tras el gesto.
        val u = ((widthPx / 2 - offsetX) / scale) / widthPx
        val v = ((heightPx / 2 - offsetY) / scale) / heightPx
        val newSpan = (s.lonSpan / scale).coerceIn(SatelliteConfig.MIN_SPAN, SatelliteConfig.MAX_SPAN)
        val gLon = b.minLon + u * b.lonSpan
        val gLat = b.maxLat - v * b.latSpan
        val (lon, lat) = SatelliteConfig.clampCenter(gLon, gLat, newSpan)
        _state.update { it.copy(cLon = lon, cLat = lat, lonSpan = newSpan) }
        applyView()
    }

    // --- Carga de datos ---------------------------------------------------------

    /**
     * Rehace la ventana de fechas; solo si aparece un dia nuevo (o force) vuelve a
     * pedir los fotogramas. Espejo de refreshData() del visor web.
     */
    fun refreshData(force: Boolean) {
        val fresh = SatelliteConfig.buildDates()
        val changed = fresh.lastOrNull() != _state.value.dates.lastOrNull()
        _state.update { it.copy(checkedAt = LocalDateTime.now(LIMA_ZONE)) }  // registra la comprobacion
        if (!changed && !force) return
        _state.update { it.copy(dates = fresh) }
        loadFrames()
    }

    /** Re-pide capas estaticas y fotogramas (tras cambiar el encuadre). */
    private fun applyView() {
        loadStatic()
        loadFrames()
    }

    private fun loadStatic() {
        staticJob?.cancel()
        staticJob = viewModelScope.launch {
            val s = _state.value
            val b = SatelliteConfig.bounds(s.cLon, s.cLat, s.lonSpan)
            val base = async { repo.fetch(SatelliteConfig.wmsUrl(SatelliteConfig.BASE_LAYER, false, b)) }
            val coast = async { repo.fetch(SatelliteConfig.wmsUrl(SatelliteConfig.COAST_LAYER, true, b)) }
            val baseBmp = base.await()
            val coastBmp = coast.await()
            _state.update { it.copy(baseBitmap = baseBmp, coastBitmap = coastBmp) }
        }
    }

    private fun loadFrames() {
        framesJob?.cancel()
        framesJob = viewModelScope.launch {
            _state.update { it.copy(loading = true, playing = false) }
            val s = _state.value
            val b = SatelliteConfig.bounds(s.cLon, s.cLat, s.lonSpan)
            val frames = s.dates.map { d ->
                async { repo.fetch(SatelliteConfig.wmsUrl(s.layer.gibsId, true, b, d)) }
            }.awaitAll()
            _state.update {
                it.copy(
                    frames = frames,
                    frameIdx = (frames.size - 1).coerceAtLeast(0),  // arranca en la fecha mas reciente
                    loading = false,
                    playing = true,                                  // anima por defecto, como el web
                )
            }
        }
    }
}
