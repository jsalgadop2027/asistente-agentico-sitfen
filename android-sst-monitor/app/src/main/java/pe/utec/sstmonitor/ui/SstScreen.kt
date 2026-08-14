package pe.utec.sstmonitor.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Waves
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import pe.utec.sstmonitor.data.CoastLocation
import pe.utec.sstmonitor.data.Locations
import pe.utec.sstmonitor.data.SstSeries
import java.time.format.DateTimeFormatter

private val updatedFmt = DateTimeFormatter.ofPattern("dd MMM, hh:mm a")

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SstScreen(viewModel: SstViewModel = viewModel()) {
    val state by viewModel.state.collectAsState()

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Filled.Waves, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text("SST Costa Perú")
                    }
                },
                actions = {
                    IconButton(onClick = { viewModel.refresh() }) {
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
            LocationSelector(
                selected = state.selected,
                onSelect = viewModel::selectLocation,
            )

            CurrentCard(state.series, state.loadingChart, state.error)

            ChartCard(state.series, state.loadingChart)

            OverviewCard(
                overview = state.overview,
                loading = state.loadingOverview,
                selectedName = state.selected.name,
                onSelect = viewModel::selectLocation,
            )

            Text(
                "Fuente: Open-Meteo Marine API · Temperatura superficial del mar (SST). " +
                    "Datos horarios: 7 días previos + 3 de pronóstico.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LocationSelector(
    selected: CoastLocation,
    onSelect: (CoastLocation) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
    ) {
        OutlinedTextField(
            value = "${selected.name} — ${selected.region}",
            onValueChange = {},
            readOnly = true,
            label = { Text("Estación costera") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor(),
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            Locations.all.forEach { loc ->
                DropdownMenuItem(
                    text = { Text("${loc.name} — ${loc.region}") },
                    onClick = {
                        onSelect(loc)
                        expanded = false
                    },
                )
            }
        }
    }
}

@Composable
private fun CurrentCard(series: SstSeries?, loading: Boolean, error: String?) {
    Card(elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            when {
                error != null && series == null -> {
                    Text("⚠️ $error", color = MaterialTheme.colorScheme.error)
                }
                series?.current != null -> {
                    val current = series.current!!
                    Text("Temperatura actual del mar", style = MaterialTheme.typography.labelMedium)
                    Text(
                        text = "%.1f°C".format(current.temp),
                        fontSize = 48.sp,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                    )
                    Spacer(Modifier.height(8.dp))
                    Row(horizontalArrangement = Arrangement.spacedBy(20.dp)) {
                        MinMax("Mínima", series.min)
                        MinMax("Máxima", series.max)
                    }
                    Spacer(Modifier.height(6.dp))
                    Text(
                        "Actualizado ${current.time.format(updatedFmt)}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                else -> {
                    Text("Cargando datos…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun MinMax(label: String, value: Double?) {
    Column {
        Text(label, style = MaterialTheme.typography.labelSmall)
        Text(
            value?.let { "%.1f°C".format(it) } ?: "—",
            fontWeight = FontWeight.SemiBold,
        )
    }
}

@Composable
private fun ChartCard(series: SstSeries?, loading: Boolean) {
    Card(elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Text("Evolución (últimos días + pronóstico)", style = MaterialTheme.typography.titleSmall)
            Spacer(Modifier.height(12.dp))
            Box(
                modifier = Modifier.fillMaxWidth().height(220.dp),
                contentAlignment = Alignment.Center,
            ) {
                when {
                    loading && series == null -> CircularProgressIndicator()
                    series != null && series.points.size >= 2 -> {
                        SstLineChart(
                            points = series.points,
                            nowIndex = series.nowIndex,
                            lineColor = MaterialTheme.colorScheme.primary,
                            forecastColor = MaterialTheme.colorScheme.tertiary,
                            gridColor = MaterialTheme.colorScheme.outlineVariant,
                            labelColor = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.fillMaxSize(),
                        )
                    }
                    else -> Text("Sin datos para graficar")
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(16.dp)) {
                LegendDot(MaterialTheme.colorScheme.primary, "Observado")
                LegendDot(MaterialTheme.colorScheme.tertiary, "Pronóstico")
            }
        }
    }
}

@Composable
private fun LegendDot(color: Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier
                .width(14.dp)
                .height(3.dp)
                .padding(0.dp),
        ) {
            androidx.compose.foundation.Canvas(Modifier.fillMaxSize()) {
                drawLine(
                    color = color,
                    start = androidx.compose.ui.geometry.Offset(0f, size.height / 2),
                    end = androidx.compose.ui.geometry.Offset(size.width, size.height / 2),
                    strokeWidth = size.height,
                )
            }
        }
        Spacer(Modifier.width(6.dp))
        Text(label, style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun OverviewCard(
    overview: Map<String, Double?>,
    loading: Boolean,
    selectedName: String,
    onSelect: (CoastLocation) -> Unit,
) {
    Card(elevation = CardDefaults.cardElevation(defaultElevation = 2.dp)) {
        Column(Modifier.fillMaxWidth().padding(16.dp)) {
            Row(
                Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Resumen de la costa", style = MaterialTheme.typography.titleSmall)
                if (loading) {
                    CircularProgressIndicator(Modifier.width(18.dp).height(18.dp), strokeWidth = 2.dp)
                }
            }
            Spacer(Modifier.height(8.dp))
            Locations.all.forEach { loc ->
                val temp = overview[loc.name]
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { onSelect(loc) }
                        .padding(vertical = 10.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Column {
                        Text(
                            loc.name,
                            fontWeight = if (loc.name == selectedName) FontWeight.Bold else FontWeight.Normal,
                        )
                        Text(
                            loc.region,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Text(
                        text = temp?.let { "%.1f°C".format(it) } ?: "—",
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
        }
    }
}
