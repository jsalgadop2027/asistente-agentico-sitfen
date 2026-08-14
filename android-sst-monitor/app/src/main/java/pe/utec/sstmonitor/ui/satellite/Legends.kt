package pe.utec.sstmonitor.ui.satellite

import androidx.compose.ui.graphics.Color
import pe.utec.sstmonitor.data.satellite.SatLayer

/**
 * Barra de calor por capa: gradiente y marcas replican EXACTAMENTE el colormap
 * oficial de GIBS (muestreado de los .xml v1.3 en el visor web /satelital), asi
 * la barra coincide con los colores reales del satelite.
 *
 * Los stops estan convertidos del CSS "to top" del web (0% = abajo) al gradiente
 * vertical de Compose (offset 0 = arriba): offset = 1 - pctCss/100, en orden
 * ascendente. Las marcas (ticks) conservan su posicion como % desde arriba.
 */
class LegendSpec(
    val stops: Array<Pair<Float, Color>>,
    val ticks: List<Pair<String, Float>>,   // etiqueta -> % desde arriba
)

object Legends {

    // Eje -7..+7 °C con marcas cada 1°. El colormap real de GIBS satura en ±3 °C,
    // por eso el gradiente vive en la franja central y fuera queda plano
    // (violeta bajo -3, rojo oscuro sobre +3): representacion fiel.
    private val ANOM = LegendSpec(
        stops = arrayOf(
            0.000f to Color(128, 0, 0),
            0.286f to Color(128, 0, 0),
            0.300f to Color(154, 0, 44),
            0.336f to Color(230, 0, 103),
            0.371f to Color(255, 33, 0),
            0.407f to Color(255, 145, 0),
            0.443f to Color(255, 208, 37),
            0.479f to Color(237, 237, 152),
            0.514f to Color(191, 208, 182),
            0.550f to Color(177, 255, 152),
            0.586f to Color(96, 255, 158),
            0.621f to Color(0, 227, 255),
            0.657f to Color(34, 100, 241),
            0.693f to Color(150, 0, 202),
            0.714f to Color(107, 0, 219),
            1.000f to Color(107, 0, 219),
        ),
        ticks = listOf(
            "+7°" to 0f, "+6°" to 7.1f, "+5°" to 14.3f, "+4°" to 21.4f,
            "+3°" to 28.6f, "+2°" to 35.7f, "+1°" to 42.9f, "0" to 50f,
            "-1°" to 57.1f, "-2°" to 64.3f, "-3°" to 71.4f, "-4°" to 78.6f,
            "-5°" to 85.7f, "-6°" to 92.9f, "-7°" to 100f,
        ),
    )

    // SST absoluta: escala termica 0..32 °C.
    private val SST = LegendSpec(
        stops = arrayOf(
            0.000f to Color(107, 2, 0),
            0.123f to Color(222, 59, 0),
            0.250f to Color(255, 175, 0),
            0.377f to Color(120, 211, 0),
            0.503f to Color(46, 163, 239),
            0.630f to Color(33, 75, 158),
            0.756f to Color(30, 16, 77),
            0.883f to Color(121, 6, 117),
            1.000f to Color(43, 0, 26),
        ),
        ticks = listOf("32°" to 0f, "24°" to 25f, "16°" to 50f, "8°" to 75f, "0°" to 100f),
    )

    fun of(layer: SatLayer): LegendSpec = when (layer) {
        SatLayer.ANOM -> ANOM
        SatLayer.SST -> SST
    }
}

/** Relleno de los departamentos en la vista politica (misma paleta que el web). */
val POLIT_COLORS = listOf(
    Color(0xFFFBB4AE), Color(0xFFB3CDE3), Color(0xFFCCEBC5), Color(0xFFDECBE4),
    Color(0xFFFED9A6), Color(0xFFE5D8BD), Color(0xFFFDDAEC), Color(0xFFB3E2CD),
    Color(0xFFFDCDAC), Color(0xFFCBD5E8), Color(0xFFF4CAE4), Color(0xFFE6F5C9),
)
