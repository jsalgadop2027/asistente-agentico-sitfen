package pe.utec.sstmonitor.ui

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import pe.utec.sstmonitor.data.CoastLocation
import pe.utec.sstmonitor.data.Locations
import pe.utec.sstmonitor.data.SstRepository
import pe.utec.sstmonitor.data.SstSeries

data class SstUiState(
    val selected: CoastLocation = Locations.default,
    val series: SstSeries? = null,
    val loadingChart: Boolean = false,
    val error: String? = null,
    /** Temperatura actual por estacion (nombre -> °C) para el resumen costero. */
    val overview: Map<String, Double?> = emptyMap(),
    val loadingOverview: Boolean = false,
)

class SstViewModel : ViewModel() {

    private val repo: SstRepository = SstRepository()

    private val _state = MutableStateFlow(SstUiState())
    val state: StateFlow<SstUiState> = _state.asStateFlow()

    init {
        loadSeries(_state.value.selected)
        loadOverview()
    }

    fun selectLocation(location: CoastLocation) {
        if (location.name == _state.value.selected.name) return
        _state.update { it.copy(selected = location) }
        loadSeries(location)
    }

    fun refresh() {
        loadSeries(_state.value.selected)
        loadOverview()
    }

    private fun loadSeries(location: CoastLocation) {
        _state.update { it.copy(loadingChart = true, error = null) }
        viewModelScope.launch {
            runCatching { repo.getSeries(location) }
                .onSuccess { series ->
                    _state.update { it.copy(series = series, loadingChart = false) }
                }
                .onFailure { e ->
                    _state.update {
                        it.copy(
                            loadingChart = false,
                            error = e.message ?: "No se pudo obtener los datos. Revisa tu conexion.",
                        )
                    }
                }
        }
    }

    private fun loadOverview() {
        _state.update { it.copy(loadingOverview = true) }
        viewModelScope.launch {
            val results = Locations.all
                .map { loc -> async { loc.name to repo.getCurrentTemp(loc) } }
                .awaitAll()
                .toMap()
            _state.update { it.copy(overview = results, loadingOverview = false) }
        }
    }
}
