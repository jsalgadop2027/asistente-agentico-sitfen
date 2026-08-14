package pe.utec.sstmonitor.data

/** Punto de monitoreo en la costa peruana. */
data class CoastLocation(
    val name: String,
    val region: String,
    val lat: Double,
    val lon: Double,
)

/**
 * Estaciones costeras de norte a sur. Se priorizan puertos frente a las principales
 * zonas exportadoras de arandano (Piura, Lambayeque, La Libertad) por su relevancia
 * para el monitoreo del Fenomeno de El Nino.
 */
object Locations {
    val all: List<CoastLocation> = listOf(
        CoastLocation("Zorritos", "Tumbes", -3.68, -80.66),
        CoastLocation("Paita", "Piura", -5.09, -81.11),
        CoastLocation("Pimentel", "Lambayeque", -6.84, -79.94),
        CoastLocation("Salaverry", "La Libertad", -8.22, -78.98),
        CoastLocation("Chimbote", "Ancash", -9.08, -78.62),
        CoastLocation("Callao", "Lima", -12.06, -77.16),
        CoastLocation("Pisco", "Ica", -13.71, -76.22),
        CoastLocation("San Juan de Marcona", "Ica", -15.36, -75.17),
        CoastLocation("Ilo", "Moquegua", -17.64, -71.35),
    )

    val default: CoastLocation get() = all.first { it.name == "Callao" }
}
