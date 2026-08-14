package pe.utec.sstmonitor.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val OceanPrimary = Color(0xFF006684)
private val OceanSecondary = Color(0xFF4C616C)
private val WarmAccent = Color(0xFFE8792B) // pronostico / anomalia calida

private val LightColors = lightColorScheme(
    primary = OceanPrimary,
    secondary = OceanSecondary,
    tertiary = WarmAccent,
    background = Color(0xFFF6FAFC),
    surface = Color(0xFFFFFFFF),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF5DD5FC),
    secondary = Color(0xFFB3CAD6),
    tertiary = Color(0xFFFFB77C),
    background = Color(0xFF0B1418),
    surface = Color(0xFF15222A),
)

@Composable
fun SstMonitorTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
