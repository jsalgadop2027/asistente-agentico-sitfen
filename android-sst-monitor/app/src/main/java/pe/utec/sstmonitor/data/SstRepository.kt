package pe.utec.sstmonitor.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter

/** Obtiene y normaliza las series de temperatura superficial del mar (SST). */
class SstRepository(
    private val api: MarineApi = MarineApi.create(),
) {
    private val parser: DateTimeFormatter = DateTimeFormatter.ISO_LOCAL_DATE_TIME

    /** America/Lima es fija en UTC-5 (Perú no observa horario de verano). */
    private val limaZone = ZoneId.of("America/Lima")

    /** Serie completa (7 dias pasados + 3 de pronostico) para graficar una ubicacion. */
    suspend fun getSeries(location: CoastLocation): SstSeries = withContext(Dispatchers.IO) {
        val response = api.getSst(location.lat, location.lon)
        val times = response.hourly?.time ?: emptyList()
        val temps = response.hourly?.sst ?: emptyList()

        val points = times.zip(temps).mapNotNull { (t, v) ->
            if (v == null) null
            else runCatching { SstPoint(LocalDateTime.parse(t, parser), v) }.getOrNull()
        }

        // La API se pide con timezone=America/Lima (ver MarineApi), así que `points`
        // llega en hora de Lima; `now` debe estarlo también o el índice "actual"
        // quedaría mal si el dispositivo tiene otra zona horaria.
        val now = LocalDateTime.now(limaZone)
        val nowIndex = points.indexOfFirst { it.time >= now }
            .let { if (it < 0) (points.size - 1).coerceAtLeast(0) else it }

        SstSeries(location = location, points = points, nowIndex = nowIndex)
    }

    /** Solo la temperatura actual, para la vista de resumen de toda la costa. */
    suspend fun getCurrentTemp(location: CoastLocation): Double? =
        runCatching { getSeries(location).current?.temp }.getOrNull()
}
