package pe.utec.sstmonitor.data

import com.google.gson.annotations.SerializedName
import java.time.LocalDateTime

/** Respuesta cruda de la API Marine de Open-Meteo. */
data class MarineResponse(
    val latitude: Double = 0.0,
    val longitude: Double = 0.0,
    val timezone: String? = null,
    @SerializedName("hourly_units") val hourlyUnits: HourlyUnits? = null,
    val hourly: Hourly? = null,
)

data class HourlyUnits(
    val time: String? = null,
    @SerializedName("sea_surface_temperature") val sst: String? = null,
)

data class Hourly(
    val time: List<String> = emptyList(),
    @SerializedName("sea_surface_temperature") val sst: List<Double?> = emptyList(),
)

/** Un punto de la serie ya parseado y limpio (sin nulos). */
data class SstPoint(
    val time: LocalDateTime,
    val temp: Double,
)

/** Serie completa lista para graficar, con metadatos derivados. */
data class SstSeries(
    val location: CoastLocation,
    val points: List<SstPoint>,
    /** Indice del primer punto cuyo tiempo es >= ahora (separa pasado de pronostico). */
    val nowIndex: Int,
) {
    val current: SstPoint? get() = points.getOrNull(nowIndex) ?: points.lastOrNull()
    val min: Double? get() = points.minOfOrNull { it.temp }
    val max: Double? get() = points.maxOfOrNull { it.temp }
}
