package com.aigriculture.app.ui.status

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.ApiResult
import com.aigriculture.app.data.net.StateMsg
import com.aigriculture.app.data.net.StateSocket
import com.aigriculture.app.data.net.WsStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SensorPickerUi(
    val scanning: Boolean = true,
    val available: Int = 0,
    val message: String? = null,
    val adding: Boolean = false,
)

data class StatusUi(
    val state: StateMsg? = null,
    val connected: Boolean = false,
    val loading: Boolean = true,
    val error: String? = null,
    val toast: String? = null,
    val busyPlants: Set<String> = emptySet(),
    val sensorPicker: SensorPickerUi? = null,
)

class StatusViewModel : ViewModel() {

    private val socket = StateSocket()
    private val _ui = MutableStateFlow(StatusUi())
    val ui: StateFlow<StatusUi> = _ui

    init {
        viewModelScope.launch {
            when (val r = AigriRepository.state()) {
                is ApiResult.Ok -> _ui.update { it.copy(state = r.value, loading = false, error = null) }
                is ApiResult.Err -> _ui.update { it.copy(loading = false, error = r.message) }
            }
        }
        viewModelScope.launch {
            socket.status.collect { st -> _ui.update { it.copy(connected = st == WsStatus.OPEN) } }
        }
        viewModelScope.launch {
            socket.states.collect { s -> _ui.update { it.copy(state = s, loading = false, error = null) } }
        }
        socket.connect()
    }

    fun pump(plant: String, on: Boolean) {
        _ui.update { it.copy(busyPlants = it.busyPlants + plant) }
        viewModelScope.launch {
            val r = AigriRepository.pump(plant, on)
            _ui.update { it.copy(busyPlants = it.busyPlants - plant) }
            if (r is ApiResult.Err) _ui.update { it.copy(toast = r.message) }
        }
    }

    fun toggleAuto(enabled: Boolean) {
        viewModelScope.launch {
            val r = AigriRepository.setAuto(enabled)
            if (r is ApiResult.Err) _ui.update { it.copy(toast = r.message) }
        }
    }

    fun clearToast() = _ui.update { it.copy(toast = null) }

    fun openSensorPicker() {
        _ui.update { it.copy(sensorPicker = SensorPickerUi(scanning = true)) }
        viewModelScope.launch {
            when (val r = AigriRepository.scanSensors()) {
                is ApiResult.Ok -> {
                    val n = r.value.unassigned.size
                    _ui.update {
                        it.copy(
                            sensorPicker = SensorPickerUi(
                                scanning = false,
                                available = n,
                                message = if (n == 0)
                                    "No new sensors found. Check that a moisture sensor is wired in correctly, then scan again."
                                else "Found $n available channel(s) ready to add.",
                            )
                        )
                    }
                }
                is ApiResult.Err -> _ui.update {
                    it.copy(sensorPicker = SensorPickerUi(scanning = false, available = 0, message = r.message))
                }
            }
        }
    }

    fun addSensors() {
        val n = _ui.value.sensorPicker?.available ?: return
        if (n <= 0) return
        _ui.update { it.copy(sensorPicker = it.sensorPicker?.copy(adding = true)) }
        viewModelScope.launch {
            val msg = when (val r = AigriRepository.addSensors(n)) {
                is ApiResult.Ok -> "Added ${r.value.added.size} sensor(s)."
                is ApiResult.Err -> r.message
            }
            // The /ws push will surface the new plants automatically.
            _ui.update { it.copy(sensorPicker = null, toast = msg) }
        }
    }

    fun closeSensorPicker() = _ui.update { it.copy(sensorPicker = null) }

    fun retry() {
        _ui.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = AigriRepository.state()) {
                is ApiResult.Ok -> _ui.update { it.copy(state = r.value, loading = false, error = null) }
                is ApiResult.Err -> _ui.update { it.copy(loading = false, error = r.message) }
            }
        }
        socket.connect()
    }

    override fun onCleared() {
        socket.close()
        super.onCleared()
    }
}
