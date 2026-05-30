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

data class StatusUi(
    val state: StateMsg? = null,
    val connected: Boolean = false,
    val loading: Boolean = true,
    val error: String? = null,
    val toast: String? = null,
    val busyPlants: Set<String> = emptySet(),
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
