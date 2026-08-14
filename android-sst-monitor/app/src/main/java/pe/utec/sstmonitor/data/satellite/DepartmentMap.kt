package pe.utec.sstmonitor.data.satellite

import android.content.Context
import androidx.compose.ui.graphics.Path
import org.json.JSONObject

/**
 * Geometria de los departamentos del Peru (assets/map.json, copiado del portal web).
 * Los paths vienen ya proyectados en px del mapa con una proyeccion afin:
 *   x = offX + (lon - lonMin) * k * cosLat ;  y = offY + (latMax - lat) * k
 * Para dibujarlos sobre el bbox actual basta calcular el "viewBox" equivalente y
 * escalar el canvas (igual que la capa SVG del visor web /satelital).
 */
class DepartmentMap(
    private val lonMin: Double,
    private val latMax: Double,
    private val k: Double,
    private val cosLat: Double,
    private val offX: Double,
    private val offY: Double,
    val departments: List<Department>,
) {
    /** Un departamento: path en px del mapa + centroide aproximado en lon/lat. */
    class Department(
        val name: String,
        val path: Path,
        val centerLon: Double,
        val centerLat: Double,
    )

    fun xOfLon(lon: Double): Double = offX + (lon - lonMin) * k * cosLat
    fun yOfLat(lat: Double): Double = offY + (latMax - lat) * k

    companion object {
        fun load(context: Context): DepartmentMap? = runCatching {
            val text = context.assets.open("map.json").bufferedReader().use { it.readText() }
            val root = JSONObject(text)
            val lonMin = root.getDouble("lonMin")
            val latMax = root.getDouble("latMax")
            val k = root.getDouble("k")
            val cosLat = root.getDouble("cosLat")
            val offX = root.getDouble("offX")
            val offY = root.getDouble("offY")

            fun lonOfX(px: Double) = lonMin + (px - offX) / (k * cosLat)
            fun latOfY(py: Double) = latMax - (py - offY) / k

            val arr = root.getJSONArray("departments")
            val deps = (0 until arr.length()).map { i ->
                val obj = arr.getJSONObject(i)
                val path = parseSvgPath(obj.getString("path"))
                // Centroide aproximado (centro del bounding box del path) -> lon/lat.
                val b = path.getBounds()
                Department(
                    name = obj.getString("name"),
                    path = path,
                    centerLon = lonOfX(((b.left + b.right) / 2).toDouble()),
                    centerLat = latOfY(((b.top + b.bottom) / 2).toDouble()),
                )
            }
            DepartmentMap(lonMin, latMax, k, cosLat, offX, offY, deps)
        }.getOrNull()

        /** Parser minimo: los paths de map.json solo usan comandos absolutos M, L y Z. */
        private fun parseSvgPath(d: String): Path {
            val path = Path()
            for (tok in d.split(' ')) {
                when {
                    tok == "Z" -> path.close()
                    tok.startsWith("M") || tok.startsWith("L") -> {
                        val xy = tok.substring(1).split(',')
                        if (xy.size == 2) {
                            val x = xy[0].toFloatOrNull() ?: continue
                            val y = xy[1].toFloatOrNull() ?: continue
                            if (tok[0] == 'M') path.moveTo(x, y) else path.lineTo(x, y)
                        }
                    }
                }
            }
            return path
        }
    }
}
