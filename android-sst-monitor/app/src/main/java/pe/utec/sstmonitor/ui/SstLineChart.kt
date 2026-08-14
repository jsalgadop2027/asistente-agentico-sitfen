package pe.utec.sstmonitor.ui

import androidx.compose.foundation.Canvas
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import pe.utec.sstmonitor.data.SstPoint
import java.time.format.DateTimeFormatter
import kotlin.math.ceil
import kotlin.math.floor

private val dateFmt = DateTimeFormatter.ofPattern("dd/MM")

/**
 * Grafica de lineas de la SST: tramo pasado en solido, pronostico en punteado,
 * marcador vertical en "ahora". Dibujado con Canvas nativo (sin dependencias).
 */
@Composable
fun SstLineChart(
    points: List<SstPoint>,
    nowIndex: Int,
    lineColor: Color,
    forecastColor: Color,
    gridColor: Color,
    labelColor: Color,
    modifier: Modifier = Modifier,
) {
    if (points.size < 2) return

    Canvas(modifier = modifier) {
        val leftPad = 42.dp.toPx()
        val rightPad = 12.dp.toPx()
        val topPad = 14.dp.toPx()
        val bottomPad = 26.dp.toPx()

        val chartW = size.width - leftPad - rightPad
        val chartH = size.height - topPad - bottomPad
        if (chartW <= 0f || chartH <= 0f) return@Canvas

        val temps = points.map { it.temp }
        val minT = floor(temps.min() - 0.3)
        val maxT = ceil(temps.max() + 0.3).let { if (it <= minT) minT + 1.0 else it }
        val range = maxT - minT

        val n = points.size
        fun x(i: Int) = leftPad + chartW * (i.toFloat() / (n - 1))
        fun y(t: Double) = topPad + chartH * (1f - ((t - minT) / range).toFloat())

        val labelPx = 10.sp.toPx()
        val textPaint = android.graphics.Paint().apply {
            color = labelColor.toArgb()
            textSize = labelPx
            isAntiAlias = true
        }

        // --- Rejilla horizontal + etiquetas de temperatura ---
        val steps = 4
        for (k in 0..steps) {
            val t = minT + range * k / steps
            val yy = y(t)
            drawLine(
                color = gridColor,
                start = Offset(leftPad, yy),
                end = Offset(leftPad + chartW, yy),
                strokeWidth = 1f,
            )
            drawContext.canvas.nativeCanvas.drawText(
                "${t.toInt()}°",
                4.dp.toPx(),
                yy + labelPx / 3f,
                textPaint,
            )
        }

        // --- Tramo pasado (solido) ---
        val boundary = nowIndex.coerceIn(0, n - 1)
        val pastPath = Path().apply {
            moveTo(x(0), y(points[0].temp))
            for (i in 1..boundary) lineTo(x(i), y(points[i].temp))
        }
        drawPath(
            path = pastPath,
            color = lineColor,
            style = Stroke(width = 3.dp.toPx(), cap = StrokeCap.Round),
        )

        // --- Tramo pronostico (punteado) ---
        if (boundary < n - 1) {
            val fcPath = Path().apply {
                moveTo(x(boundary), y(points[boundary].temp))
                for (i in (boundary + 1) until n) lineTo(x(i), y(points[i].temp))
            }
            drawPath(
                path = fcPath,
                color = forecastColor,
                style = Stroke(
                    width = 3.dp.toPx(),
                    cap = StrokeCap.Round,
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(12f, 10f)),
                ),
            )
        }

        // --- Marcador vertical "ahora" ---
        val nowX = x(boundary)
        drawLine(
            color = forecastColor,
            start = Offset(nowX, topPad),
            end = Offset(nowX, topPad + chartH),
            strokeWidth = 1.5f,
            pathEffect = PathEffect.dashPathEffect(floatArrayOf(6f, 6f)),
        )
        drawCircle(color = lineColor, radius = 4.dp.toPx(), center = Offset(nowX, y(points[boundary].temp)))

        // --- Etiquetas de fecha (inicio, hoy, fin) ---
        val leftText = android.graphics.Paint(textPaint).apply {
            textAlign = android.graphics.Paint.Align.LEFT
        }
        val midText = android.graphics.Paint(textPaint).apply {
            textAlign = android.graphics.Paint.Align.CENTER
        }
        val rightText = android.graphics.Paint(textPaint).apply {
            textAlign = android.graphics.Paint.Align.RIGHT
        }
        val baseY = size.height - 6.dp.toPx()
        drawContext.canvas.nativeCanvas.drawText(points.first().time.format(dateFmt), leftPad, baseY, leftText)
        drawContext.canvas.nativeCanvas.drawText("hoy", nowX, baseY, midText)
        drawContext.canvas.nativeCanvas.drawText(points.last().time.format(dateFmt), leftPad + chartW, baseY, rightText)
    }
}
