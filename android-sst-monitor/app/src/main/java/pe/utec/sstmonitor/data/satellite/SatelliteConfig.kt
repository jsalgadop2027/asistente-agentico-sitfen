package pe.utec.sstmonitor.data.satellite

import java.time.LocalDate
import java.time.ZoneOffset

/** Punto de referencia geografico dibujado sobre el mapa satelital. */
data class GeoPoint(val name: String, val lat: Double, val lon: Double)

/** Encuadre geografico (bbox) de la vista. */
data class GeoBounds(
    val minLon: Double,
    val maxLon: Double,
    val minLat: Double,
    val maxLat: Double,
) {
    val lonSpan: Double get() = maxLon - minLon
    val latSpan: Double get() = maxLat - minLat
}

/** Capas satelitales de NASA GIBS (producto GHRSST MUR L4, diario, ~1 km). */
enum class SatLayer(val gibsId: String, val defaultOpacity: Float, val label: String) {
    ANOM("GHRSST_L4_MUR_Sea_Surface_Temperature_Anomalies", 0.95f, "Anomalía (FEN)"),
    SST("GHRSST_L4_MUR_Sea_Surface_Temperature", 0.85f, "SST absoluta"),
}

/** Vista del mapa: relieve satelital o mapa politico con departamentos en color. */
enum class MapViewMode(val label: String) { GEO("Geográfico"), POL("Político") }

/**
 * Configuracion del visor satelital. Replica del visor web /satelital
 * (web-sst-monitor/satelital.html): mismas capas WMS, encuadre por defecto,
 * ventana temporal y limites de zoom, para que ambos clientes muestren lo mismo.
 */
object SatelliteConfig {
    const val WMS = "https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi"

    // Tamano del fotograma WMS: proporcion 5:6.4 (lon:lat), sin distorsion.
    const val FRAME_W = 600
    const val FRAME_H = 768
    const val RATIO_LAT = FRAME_H.toDouble() / FRAME_W   // latSpan = lonSpan * 1.28

    // Vista por defecto (norte de Peru) y limites de zoom.
    const val DEF_CLON = -80.5
    const val DEF_CLAT = -6.2
    const val MIN_SPAN = 1.5
    const val MAX_SPAN = 5.0

    // Ventana temporal: N dias terminando hace END_OFFSET dias (rezago del producto).
    const val N_DAYS = 14
    const val END_OFFSET = 2L

    // Region maxima permitida para el centro al hacer zoom (evita irse del norte).
    val REGION = GeoBounds(minLon = -84.0, maxLon = -77.5, minLat = -10.4, maxLat = -2.6)

    const val BASE_LAYER = "BlueMarble_ShadedRelief_Bathymetry"
    const val COAST_LAYER = "Coastlines_15m"

    fun bounds(cLon: Double, cLat: Double, lonSpan: Double): GeoBounds {
        val latSpan = lonSpan * RATIO_LAT
        return GeoBounds(
            minLon = cLon - lonSpan / 2, maxLon = cLon + lonSpan / 2,
            minLat = cLat - latSpan / 2, maxLat = cLat + latSpan / 2,
        )
    }

    /** Mantiene el centro dentro de la region al hacer zoom/pan. */
    fun clampCenter(cLon: Double, cLat: Double, lonSpan: Double): Pair<Double, Double> {
        val latSpan = lonSpan * RATIO_LAT
        val lon = if (lonSpan >= REGION.maxLon - REGION.minLon) {
            (REGION.minLon + REGION.maxLon) / 2
        } else {
            cLon.coerceIn(REGION.minLon + lonSpan / 2, REGION.maxLon - lonSpan / 2)
        }
        val lat = if (latSpan >= REGION.maxLat - REGION.minLat) {
            (REGION.minLat + REGION.maxLat) / 2
        } else {
            cLat.coerceIn(REGION.minLat + latSpan / 2, REGION.maxLat - latSpan / 2)
        }
        return lon to lat
    }

    /** Fechas de la ventana de animacion, ascendentes en el tiempo (UTC, como GIBS). */
    fun buildDates(): List<LocalDate> {
        val today = LocalDate.now(ZoneOffset.UTC)
        return (N_DAYS - 1 downTo 0).map { k -> today.minusDays(END_OFFSET + k) }
    }

    /** URL GetMap de GIBS para una capa, bbox y fecha (time null = capa estatica). */
    fun wmsUrl(layerId: String, transparent: Boolean, bounds: GeoBounds, time: LocalDate? = null): String {
        val bbox = "${bounds.minLon},${bounds.minLat},${bounds.maxLon},${bounds.maxLat}"
        return buildString {
            append(WMS)
            append("?SERVICE=WMS&VERSION=1.1.1&REQUEST=GetMap")
            append("&LAYERS=").append(layerId)
            append("&SRS=EPSG:4326&BBOX=").append(bbox)
            append("&WIDTH=").append(FRAME_W).append("&HEIGHT=").append(FRAME_H)
            append("&FORMAT=image/png&TRANSPARENT=").append(if (transparent) "TRUE" else "FALSE")
            if (time != null) append("&TIME=").append(time)
        }
    }
}

/** Referencias geograficas del norte (mismas listas que el visor web /satelital). */
object GeoRefs {

    /** Ciudades principales del norte de Peru (referencia geografica), norte -> sur. */
    val CITIES = listOf(
        GeoPoint("Zarumilla", -3.50, -80.27),
        GeoPoint("Tumbes", -3.57, -80.46),
        GeoPoint("Zorritos", -3.68, -80.66),
        GeoPoint("Talara", -4.58, -81.27),
        GeoPoint("Sullana", -4.90, -80.69),
        GeoPoint("Paita", -5.09, -81.11),
        GeoPoint("Piura", -5.19, -80.63),
        GeoPoint("Jaén", -5.71, -78.81),
        GeoPoint("Ferreñafe", -6.64, -79.79),
        GeoPoint("Lambayeque", -6.70, -79.91),
        GeoPoint("Chiclayo", -6.77, -79.84),
        GeoPoint("Pimentel", -6.84, -79.93),
        GeoPoint("Cajamarca", -7.16, -78.51),
        GeoPoint("Chepén", -7.22, -79.42),
        GeoPoint("Pacasmayo", -7.40, -79.57),
        GeoPoint("Trujillo", -8.11, -79.03),
        GeoPoint("Salaverry", -8.22, -78.98),
        GeoPoint("Chimbote", -9.08, -78.59),
    )

    /** Zonas exactas de cultivo de arandano en el norte (valles productores). */
    val ZONES = listOf(
        GeoPoint("Valle del Chira (Piura)", -4.93, -80.70),
        GeoPoint("Olmos–Motupe (Lambayeque)", -6.05, -79.74),
        GeoPoint("Jayanca–Íllimo (Lamb.)", -6.42, -79.85),
        GeoPoint("Virú–Chao (La Libertad)", -8.42, -78.75),
        GeoPoint("Santa–Nepeña (Áncash)", -8.98, -78.60),
    )

    /** Sedes de la Red CITE del ITP detectadas en el norte (a nivel de sede/ciudad). */
    val CITE_ITP = listOf(
        GeoPoint("CITEpesquero Piura", -5.19, -80.63),
        GeoPoint("CITEagroindustrial Lambayeque", -6.39, -79.82),
        GeoPoint("CITEagroindustrial Chavimochic", -8.41, -78.75),
    )

    /** Puertos y terminales portuarios del norte (Tumbes -> La Libertad), norte -> sur. */
    val PORTS = listOf(
        GeoPoint("Puerto Pizarro", -3.50, -80.45),
        GeoPoint("Caleta Zorritos", -3.68, -80.68),
        GeoPoint("Terminal Talara", -4.58, -81.28),
        GeoPoint("Puerto Paita", -5.09, -81.11),
        GeoPoint("Terminal Bayóvar", -5.83, -81.11),
        GeoPoint("Caleta San José", -6.78, -79.98),
        GeoPoint("Caleta Santa Rosa", -6.89, -79.95),
        GeoPoint("Puerto Eten", -6.93, -79.86),
        GeoPoint("Puerto Pimentel", -6.84, -79.93),
        GeoPoint("Puerto Malabrigo (Chicama)", -7.69, -79.44),
        GeoPoint("Puerto Salaverry", -8.22, -78.98),
    )
}
