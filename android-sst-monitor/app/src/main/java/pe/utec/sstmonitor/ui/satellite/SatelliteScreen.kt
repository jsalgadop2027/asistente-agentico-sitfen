package pe.utec.sstmonitor.ui.satellite

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculateCentroid
import androidx.compose.foundation.gestures.calculatePan
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Remove
import androidx.compose.material.icons.filled.RestartAlt
import androidx.compose.material.icons.filled.SatelliteAlt
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.geometry.isSpecified
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.withTransform
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChanged
import androidx.compose.ui.text.TextMeasurer
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.utec.sstmonitor.data.satellite.GeoBounds
import pe.utec.sstmonitor.data.satellite.GeoPoint
import pe.utec.sstmonitor.data.satellite.GeoRefs
import pe.utec.sstmonitor.data.satellite.MapViewMode
import pe.utec.sstmonitor.data.satellite.SatLayer
import pe.utec.sstmonitor.data.satellite.SatelliteConfig
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.graphics.Shadow
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.roundToInt

// Formato humano de fechas, como en el visor web: "05 jul 2026".
private val MESES = listOf("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
private fun fmtHuman(d: LocalDate): String =
    "${d.dayOfMonth.toString().padStart(2, '0')} ${MESES[d.monthValue - 1]} ${d.year}"

private val checkedFmt = DateTimeFormatter.ofPattern("dd/MM/yyyy, hh:mm a")

// Colores del visor (mismos que el web /satelital).
private val BADGE_BG = Color(0xD914223C)
private val OCEAN_POL = Color(0xFFA9D3E8)
private val MAP_BG = Color(0xFFEEF2F7)

/**
 * Visor satelital animado de SST (norte de Peru): puerto movil del visor web
 * /satelital. Fotogramas WMS de NASA GIBS por fecha, con capa de anomalia o SST
 * absoluta, limites departamentales, marcadores de referencia, zoom y animacion.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SatelliteScreen(viewModel: SatelliteViewModel = viewModel()) {
    val state by viewModel.state.collectAsState()

    // Auto-actualizacion al volver a la app (equivalente al visibilitychange del web).
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) viewModel.refreshData(force = false)
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.SatelliteAlt, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("SST Satelital", maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.refreshData(force = true) }) {
                        Icon(Icons.Filled.Refresh, contentDescription = "Actualizar")
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.primary,
                    titleContentColor = MaterialTheme.colorScheme.onPrimary,
                    actionIconContentColor = MaterialTheme.colorScheme.onPrimary,
                ),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text(
                "Monitoreo del Fenómeno de \"El Niño\" (Océano Pacífico) — Anomalía y SST · " +
                    "NASA GIBS / GHRSST MUR L4",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            Card(elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) {
                MapPanel(state, viewModel, Modifier.padding(12.dp))
            }

            DataCard(state, viewModel)
            ViewAndLayerCard(state, viewModel)
            AnimationCard(state, viewModel)
            ReferencesCard(state, viewModel)

            Text(
                "La barra de calor (derecha del mapa) replica el colormap real de GIBS de la capa " +
                    "activa: Anomalía con eje −7 a +7 °C (el producto satura en ±3 °C, por eso fuera " +
                    "de esa franja el color queda plano); SST absoluta = 0 a 32 °C. Escala geográfica " +
                    "(abajo-izq.) en km. Pellizca para hacer zoom, arrastra para desplazarte y usa " +
                    "⟲ para volver al encuadre original.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                "Fuente: NASA GIBS (WMS), producto GHRSST MUR L4 (~1 km, diario, ~1–2 días de " +
                    "rezago). Datos públicos, sin API key. Discos verdes = zonas de cultivo de " +
                    "arándano; rombos ámbar = sedes de la Red CITE del ITP (CITEpesquero Piura, " +
                    "CITEagroindustrial Lambayeque y CITEagroindustrial Chavimochic); anclas azules = " +
                    "puertos y terminales portuarios del norte, de Tumbes a La Libertad.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

// --- Mapa + barra de calor ---------------------------------------------------

@Composable
private fun MapPanel(state: SatelliteUiState, viewModel: SatelliteViewModel, modifier: Modifier = Modifier) {
    BoxWithConstraints(modifier.fillMaxWidth()) {
        val legendW = 46.dp
        val gap = 8.dp
        val mapW = maxWidth - legendW - gap
        val mapH = mapW * (SatelliteConfig.FRAME_H.toFloat() / SatelliteConfig.FRAME_W)
        Row(Modifier.fillMaxWidth().height(mapH)) {
            SatelliteMapView(state, viewModel, mapW, Modifier.width(mapW).fillMaxHeight())
            Spacer(Modifier.width(gap))
            LegendBar(Legends.of(state.layer), Modifier.width(legendW).fillMaxHeight())
        }
    }
}

@Composable
private fun SatelliteMapView(
    state: SatelliteUiState,
    viewModel: SatelliteViewModel,
    mapW: Dp,
    modifier: Modifier = Modifier,
) {
    // Vista previa fluida del gesto (traslacion + escala); al soltar se consolida
    // el encuadre y se re-piden las imagenes (igual que el pan/zoom del web).
    var previewScale by remember { mutableFloatStateOf(1f) }
    var previewOffset by remember { mutableStateOf(Offset.Zero) }
    val textMeasurer = rememberTextMeasurer()

    Box(
        modifier
            .clip(RoundedCornerShape(12.dp))
            .background(MAP_BG)
            .pointerInput(Unit) {
                awaitEachGesture {
                    awaitFirstDown(requireUnconsumed = false)
                    var scale = 1f
                    var offset = Offset.Zero
                    do {
                        val event = awaitPointerEvent()
                        val zoom = event.calculateZoom()
                        val pan = event.calculatePan()
                        val centroid = event.calculateCentroid()
                        if (zoom != 1f && centroid.isSpecified) {
                            // Mantiene fijo el punto bajo el centroide del pellizco.
                            offset = Offset(
                                centroid.x - zoom * (centroid.x - offset.x),
                                centroid.y - zoom * (centroid.y - offset.y),
                            )
                            scale *= zoom
                        }
                        offset += pan
                        previewScale = scale
                        previewOffset = offset
                        event.changes.forEach { if (it.positionChanged()) it.consume() }
                    } while (event.changes.any { it.pressed })
                    viewModel.commitGesture(
                        scale, offset.x, offset.y,
                        size.width.toFloat(), size.height.toFloat(),
                    )
                    previewScale = 1f
                    previewOffset = Offset.Zero
                }
            },
    ) {
        Canvas(Modifier.fillMaxSize()) {
            withTransform({
                translate(previewOffset.x, previewOffset.y)
                scale(previewScale, previewScale, pivot = Offset.Zero)
            }) {
                drawSatelliteMap(state, textMeasurer)
            }
        }

        // Insignia de fecha (arriba-izq.)
        Box(
            Modifier
                .align(Alignment.TopStart)
                .padding(8.dp)
                .background(BADGE_BG, RoundedCornerShape(999.dp))
                .padding(horizontal = 11.dp, vertical = 5.dp),
        ) {
            val iso = state.dates.getOrNull(state.frameIdx)
            Text(
                iso?.let { fmtHuman(it) } ?: "—",
                color = Color(0xFFE8EEF7),
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
            )
        }

        // Controles de zoom (arriba-der.)
        Column(
            Modifier.align(Alignment.TopEnd).padding(8.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            val canZoomIn = state.lonSpan > SatelliteConfig.MIN_SPAN + 1e-6
            val canZoomOut = state.lonSpan < SatelliteConfig.MAX_SPAN - 1e-6
            ZoomButton(Icons.Filled.Add, "Acercar", canZoomIn) { viewModel.zoomIn() }
            ZoomButton(Icons.Filled.RestartAlt, "Restablecer tamaño original", true) { viewModel.resetView() }
            ZoomButton(Icons.Filled.Remove, "Alejar", canZoomOut) { viewModel.zoomOut() }
            Box(
                Modifier.background(BADGE_BG, RoundedCornerShape(6.dp)).padding(horizontal = 6.dp, vertical = 2.dp),
            ) {
                Text(
                    "${(SatelliteConfig.MAX_SPAN / state.lonSpan * 100).roundToInt()}%",
                    color = Color.White, fontSize = 10.sp, fontWeight = FontWeight.SemiBold,
                )
            }
        }

        // Escala geografica en km (abajo-izq.)
        ScaleBar(state, mapW, Modifier.align(Alignment.BottomStart).padding(10.dp))

        // Cortina de carga
        if (state.loading) {
            Box(
                Modifier.matchParentSize().background(Color(0x8C0A1220)),
                contentAlignment = Alignment.Center,
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(
                        Modifier.size(16.dp), strokeWidth = 2.dp, color = Color(0xFFE8EEF7),
                    )
                    Spacer(Modifier.width(10.dp))
                    Text("Cargando fotogramas satelitales…", color = Color(0xFFE8EEF7), fontSize = 12.sp)
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ZoomButton(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    description: String,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    Surface(
        onClick = onClick,
        enabled = enabled,
        shape = RoundedCornerShape(8.dp),
        color = BADGE_BG.copy(alpha = if (enabled) BADGE_BG.alpha else 0.4f),
        contentColor = Color.White,
        modifier = Modifier.size(32.dp),
    ) {
        Box(contentAlignment = Alignment.Center) {
            Icon(icon, contentDescription = description, Modifier.size(18.dp))
        }
    }
}

@Composable
private fun ScaleBar(state: SatelliteUiState, mapW: Dp, modifier: Modifier = Modifier) {
    val b = SatelliteConfig.bounds(state.cLon, state.cLat, state.lonSpan)
    val kmPerDegLon = 111.32 * cos((b.minLat + b.maxLat) / 2 * PI / 180)
    val totalKm = b.lonSpan * kmPerDegLon
    val nice = listOf(10, 20, 25, 50, 100, 150, 200, 250, 500)
    val target = totalKm * 0.22
    var km = nice.first()
    for (n in nice) if (n <= target) km = n
    val barW = mapW * (km / totalKm).toFloat()

    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            "$km km",
            color = Color.White,
            fontSize = 10.sp,
            fontWeight = FontWeight.SemiBold,
            style = TextStyle(shadow = Shadow(Color.Black, blurRadius = 4f)),
        )
        Spacer(Modifier.height(2.dp))
        Box(
            Modifier
                .width(barW)
                .height(7.dp)
                .drawBehind {
                    val sw = 2.dp.toPx()
                    // Bordes izquierdo, derecho e inferior (como la barra del web).
                    drawLine(Color.White, Offset(sw / 2, 0f), Offset(sw / 2, size.height), sw)
                    drawLine(Color.White, Offset(size.width - sw / 2, 0f), Offset(size.width - sw / 2, size.height), sw)
                    drawLine(Color.White, Offset(0f, size.height - sw / 2), Offset(size.width, size.height - sw / 2), sw)
                },
        )
    }
}

// --- Dibujo del mapa (canvas) --------------------------------------------------

private fun DrawScope.drawSatelliteMap(state: SatelliteUiState, textMeasurer: TextMeasurer) {
    val b = SatelliteConfig.bounds(state.cLon, state.cLat, state.lonSpan)
    val w = size.width
    val h = size.height
    val dst = IntSize(w.roundToInt(), h.roundToInt())

    // 1) Fondo: relieve satelital (geografico) u oceano plano (politico).
    if (state.view == MapViewMode.GEO) {
        state.baseBitmap?.let {
            drawImage(it.asImageBitmap(), dstSize = dst, filterQuality = FilterQuality.Medium)
        }
    } else {
        drawRect(OCEAN_POL)
    }

    // 2) Limites departamentales, reproyectados al bbox actual (viewBox afin).
    val map = state.departments
    if (map != null) {
        val x0 = map.xOfLon(b.minLon).toFloat()
        val x1 = map.xOfLon(b.maxLon).toFloat()
        val y0 = map.yOfLat(b.maxLat).toFloat()   // maxLat = arriba
        val y1 = map.yOfLat(b.minLat).toFloat()
        if (x1 > x0 && y1 > y0) {
            val sx = w / (x1 - x0)
            val sy = h / (y1 - y0)
            val strokeW = 1.dp.toPx() / ((sx + sy) / 2f)   // trazo ~constante en pantalla
            withTransform({
                scale(scaleX = sx, scaleY = sy, pivot = Offset.Zero)
                translate(-x0, -y0)
            }) {
                map.departments.forEachIndexed { i, dep ->
                    if (state.view == MapViewMode.POL) {
                        drawPath(dep.path, POLIT_COLORS[i % POLIT_COLORS.size], alpha = 0.82f)
                        drawPath(dep.path, Color.Black.copy(alpha = 0.55f), style = Stroke(strokeW))
                    } else {
                        drawPath(dep.path, Color.White.copy(alpha = 0.9f), style = Stroke(strokeW))
                    }
                }
            }
        }
    }

    // 3) Fotograma satelital de la fecha activa (opacidad regulable).
    state.frames.getOrNull(state.frameIdx)?.let {
        drawImage(
            it.asImageBitmap(), dstSize = dst,
            alpha = state.opacity, filterQuality = FilterQuality.Medium,
        )
    }

    // 4) Linea de costa.
    if (state.showCoast) {
        state.coastBitmap?.let { drawImage(it.asImageBitmap(), dstSize = dst) }
    }

    // 5) Marcadores de referencia.
    drawMarkers(state, b, textMeasurer)
}

private fun DrawScope.drawMarkers(state: SatelliteUiState, b: GeoBounds, textMeasurer: TextMeasurer) {
    val w = size.width
    val h = size.height

    fun project(p: GeoPoint): Offset? {
        val x = ((p.lon - b.minLon) / b.lonSpan * w).toFloat()
        val y = ((b.maxLat - p.lat) / b.latSpan * h).toFloat()
        return if (x < 0f || x > w || y < 0f || y > h) null else Offset(x, y)
    }

    fun label(
        text: String, cx: Float, topY: Float, color: Color,
        shadow: Color = Color.Black, sizeSp: TextUnit = 9.sp, bold: Boolean = false,
    ) {
        val layout = textMeasurer.measure(
            AnnotatedString(text),
            TextStyle(
                color = color,
                fontSize = sizeSp,
                fontWeight = if (bold) FontWeight.Bold else FontWeight.Medium,
                shadow = Shadow(shadow, blurRadius = 5f),
            ),
        )
        drawText(layout, topLeft = Offset(cx - layout.size.width / 2f, topY))
    }

    // Etiquetas de departamento (checkbox «Departamentos», ambas vistas, como el web).
    if (state.showDepts) {
        state.departments?.departments?.forEach { dep ->
            project(GeoPoint(dep.name, dep.centerLat, dep.centerLon))?.let { pos ->
                val layout = textMeasurer.measure(
                    AnnotatedString(dep.name.uppercase()),
                    TextStyle(
                        color = Color(0xFF14203A), fontSize = 8.sp,
                        fontWeight = FontWeight.Bold, shadow = Shadow(Color.White, blurRadius = 6f),
                    ),
                )
                drawText(layout, topLeft = Offset(pos.x - layout.size.width / 2f, pos.y - layout.size.height / 2f))
            }
        }
    }

    // Zonas de cultivo de arandano: disco verde translucido.
    if (state.showZones) {
        GeoRefs.ZONES.forEach { z ->
            project(z)?.let { pos ->
                val r = 6.5.dp.toPx()
                drawCircle(Color(0x7322C55E), radius = r, center = pos)
                drawCircle(Color(0xFF22C55E), radius = r, center = pos, style = Stroke(1.5.dp.toPx()))
                if (state.showLabels) label(z.name, pos.x, pos.y + r + 2.dp.toPx(), Color(0xFFD7FFE4))
            }
        }
    }

    // Sedes RedCITE (ITP): rombo ambar.
    if (state.showCite) {
        GeoRefs.CITE_ITP.forEach { c ->
            project(c)?.let { pos ->
                val s = 7.dp.toPx()
                withTransform({ rotate(degrees = 45f, pivot = pos) }) {
                    drawRect(Color(0xFFF59E0B), topLeft = pos - Offset(s / 2, s / 2), size = Size(s, s))
                    drawRect(
                        Color(0xFF7C2D12), topLeft = pos - Offset(s / 2, s / 2), size = Size(s, s),
                        style = Stroke(1.5.dp.toPx()),
                    )
                }
                if (state.showLabels) label(c.name, pos.x, pos.y + s + 2.dp.toPx(), Color(0xFFFFE4B3))
            }
        }
    }

    // Puertos y terminales: ancla en cuadro azul.
    if (state.showPorts) {
        GeoRefs.PORTS.forEach { p ->
            project(p)?.let { pos ->
                val s = 10.dp.toPx()
                val topLeft = pos - Offset(s / 2, s / 2)
                drawRoundRect(
                    Color(0xFF0EA5E9), topLeft = topLeft, size = Size(s, s),
                    cornerRadius = androidx.compose.ui.geometry.CornerRadius(2.dp.toPx()),
                )
                drawRoundRect(
                    Color(0xFF075985), topLeft = topLeft, size = Size(s, s),
                    cornerRadius = androidx.compose.ui.geometry.CornerRadius(2.dp.toPx()),
                    style = Stroke(1.5.dp.toPx()),
                )
                val anchor = textMeasurer.measure(
                    AnnotatedString("⚓"), TextStyle(color = Color.White, fontSize = 7.sp),
                )
                drawText(
                    anchor,
                    topLeft = Offset(pos.x - anchor.size.width / 2f, pos.y - anchor.size.height / 2f),
                )
                if (state.showLabels) label(p.name, pos.x, pos.y + s / 2 + 2.dp.toPx(), Color(0xFFBAE6FD))
            }
        }
    }

    // Ciudades: punto blanco con anillo oscuro.
    if (state.showCities) {
        GeoRefs.CITIES.forEach { c ->
            project(c)?.let { pos ->
                drawCircle(Color(0xFF16223A), radius = 3.5.dp.toPx(), center = pos)
                drawCircle(Color.White, radius = 2.dp.toPx(), center = pos)
                if (state.showLabels) label(c.name, pos.x, pos.y + 4.dp.toPx() + 2.dp.toPx(), Color.White)
            }
        }
    }
}

// --- Barra de calor (leyenda) ---------------------------------------------------

@Composable
private fun LegendBar(spec: LegendSpec, modifier: Modifier = Modifier) {
    Row(modifier) {
        Box(
            Modifier
                .width(14.dp)
                .fillMaxHeight()
                .clip(RoundedCornerShape(3.dp))
                .background(Brush.verticalGradient(*spec.stops)),
        )
        Spacer(Modifier.width(4.dp))
        BoxWithConstraints(Modifier.weight(1f).fillMaxHeight()) {
            val boxH = maxHeight
            spec.ticks.forEach { (text, pct) ->
                Text(
                    text,
                    fontSize = 8.sp,
                    color = MaterialTheme.colorScheme.onSurface,
                    maxLines = 1,
                    modifier = Modifier.offset(y = boxH * (pct / 100f) - 6.dp),
                )
            }
        }
    }
}

// --- Paneles de control -----------------------------------------------------------

@Composable
private fun CtlTitle(text: String) {
    Text(
        text.uppercase(),
        style = MaterialTheme.typography.labelMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        fontWeight = FontWeight.Bold,
    )
}

@Composable
private fun DataCard(state: SatelliteUiState, viewModel: SatelliteViewModel) {
    Card(elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) {
        Row(
            Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            FilledIconButton(onClick = { viewModel.refreshData(force = true) }) {
                Icon(Icons.Filled.Refresh, contentDescription = "Actualizar datos ahora")
            }
            Spacer(Modifier.width(12.dp))
            Column {
                Text(
                    state.dates.lastOrNull()?.let { "Datos al ${fmtHuman(it)}" } ?: "Datos: —",
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    state.checkedAt?.let { "Comprobado: ${it.format(checkedFmt)}" } ?: "Comprobado: —",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun ViewAndLayerCard(state: SatelliteUiState, viewModel: SatelliteViewModel) {
    Card(elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            CtlTitle("Vista del mapa")
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                MapViewMode.entries.forEachIndexed { i, mode ->
                    SegmentedButton(
                        selected = state.view == mode,
                        onClick = { viewModel.setViewMode(mode) },
                        shape = SegmentedButtonDefaults.itemShape(index = i, count = MapViewMode.entries.size),
                    ) { Text(mode.label, fontSize = 12.sp, maxLines = 1) }
                }
            }
            CtlTitle("Capa (dato satelital)")
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                SatLayer.entries.forEachIndexed { i, layer ->
                    SegmentedButton(
                        selected = state.layer == layer,
                        onClick = { viewModel.setLayer(layer) },
                        shape = SegmentedButtonDefaults.itemShape(index = i, count = SatLayer.entries.size),
                    ) { Text(layer.label, fontSize = 12.sp, maxLines = 1) }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AnimationCard(state: SatelliteUiState, viewModel: SatelliteViewModel) {
    Card(elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            CtlTitle("Animación")
            Row(verticalAlignment = Alignment.CenterVertically) {
                FilledIconButton(onClick = { viewModel.togglePlay() }, enabled = state.frames.isNotEmpty()) {
                    Icon(
                        if (state.playing) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                        contentDescription = "Reproducir / Pausar",
                    )
                }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(
                            state.dates.getOrNull(state.frameIdx)?.let { fmtHuman(it) } ?: "—",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Text(
                            if (state.frames.isEmpty()) "" else "${state.frameIdx + 1}/${state.frames.size}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Slider(
                        value = state.frameIdx.toFloat(),
                        onValueChange = { viewModel.scrubTo(it.roundToInt()) },
                        valueRange = 0f..(state.frames.size - 1).coerceAtLeast(0).toFloat(),
                        enabled = state.frames.size >= 2,
                    )
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Checkbox(checked = state.loop, onCheckedChange = { viewModel.setLoop(it) })
                Text("Repetir", style = MaterialTheme.typography.bodyMedium)
            }

            CtlTitle("Velocidad")
            val speeds = listOf("Lenta" to 1.5f, "Normal" to 3f, "Rápida" to 6f)
            SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                speeds.forEachIndexed { i, (name, fps) ->
                    SegmentedButton(
                        selected = state.fps == fps,
                        onClick = { viewModel.setFps(fps) },
                        shape = SegmentedButtonDefaults.itemShape(index = i, count = speeds.size),
                    ) { Text(name, fontSize = 12.sp, maxLines = 1) }
                }
            }

            CtlTitle("Opacidad de la capa")
            Slider(
                value = state.opacity,
                onValueChange = { viewModel.setOpacity(it) },
                valueRange = 0.3f..1f,
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ReferencesCard(state: SatelliteUiState, viewModel: SatelliteViewModel) {
    Card(elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            CtlTitle("Referencias")
            FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                RefCheck("Costas", state.showCoast, viewModel::setShowCoast)
                RefCheck("Ciudades", state.showCities, viewModel::setShowCities)
                RefCheck("Departamentos", state.showDepts, viewModel::setShowDepts)
                RefCheck("Zonas arándano", state.showZones, viewModel::setShowZones, Color(0xFF22C55E), round = true)
                RefCheck("RedCITE (ITP)", state.showCite, viewModel::setShowCite, Color(0xFFF59E0B))
                RefCheck("Puertos", state.showPorts, viewModel::setShowPorts, Color(0xFF0EA5E9))
                RefCheck("Etiquetas", state.showLabels, viewModel::setShowLabels)
            }
        }
    }
}

@Composable
private fun RefCheck(
    label: String,
    checked: Boolean,
    onChecked: (Boolean) -> Unit,
    swatch: Color? = null,
    round: Boolean = false,
) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Checkbox(checked = checked, onCheckedChange = onChecked)
        if (swatch != null) {
            Box(
                Modifier
                    .size(11.dp)
                    .background(swatch, if (round) CircleShape else RoundedCornerShape(2.dp)),
            )
            Spacer(Modifier.width(5.dp))
        }
        Text(label, style = MaterialTheme.typography.bodySmall)
    }
}
