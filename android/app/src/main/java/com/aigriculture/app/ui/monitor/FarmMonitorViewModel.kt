package com.aigriculture.app.ui.monitor

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.ApiResult
import com.aigriculture.app.data.net.FarmStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class MonitorUi(
    val status: FarmStatus? = null,
    val loaded: Boolean = false,
    val error: String? = null,
    val toast: String? = null,
    val scanBusy: Boolean = false,
)

/** FarmMonitor tab — live field camera, scan status, and on-demand scans. */
class FarmMonitorViewModel : ViewModel() {

    private val _ui = MutableStateFlow(MonitorUi())
    val ui: StateFlow<MonitorUi> = _ui

    fun refresh() {
        viewModelScope.launch {
            when (val r = AigriRepository.farmStatus()) {
                is ApiResult.Ok -> _ui.update { it.copy(status = r.value, loaded = true, error = null) }
                is ApiResult.Err -> _ui.update { it.copy(error = r.message) }
            }
        }
    }

    fun scanNow() {
        _ui.update { it.copy(scanBusy = true) }
        viewModelScope.launch {
            val msg = when (val r = AigriRepository.scanNow()) {
                is ApiResult.Ok -> r.value
                is ApiResult.Err -> r.message
            }
            _ui.update { it.copy(scanBusy = false, toast = msg) }
            refresh()
        }
    }

    fun stopScan() {
        _ui.update { it.copy(scanBusy = true) }
        viewModelScope.launch {
            val msg = when (val r = AigriRepository.scanStop()) {
                is ApiResult.Ok -> r.value
                is ApiResult.Err -> r.message
            }
            _ui.update { it.copy(scanBusy = false, toast = msg) }
            refresh()
        }
    }

    fun clearToast() = _ui.update { it.copy(toast = null) }
}
