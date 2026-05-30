package com.aigriculture.app.ui.security

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.ApiResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SecurityUi(
    val armed: Boolean = false,           // guard ON == you're away
    val alerts: List<String> = emptyList(),
    val loaded: Boolean = false,
    val error: String? = null,
    val toast: String? = null,
    val guardBusy: Boolean = false,
    val sirenBusy: Boolean = false,
)

/** Security tab — guard arm/disarm, siren test, and live threat alerts. */
class SecurityViewModel : ViewModel() {

    private val _ui = MutableStateFlow(SecurityUi())
    val ui: StateFlow<SecurityUi> = _ui

    /** /alerts returns both the active alert names and at_farm in one call. */
    fun refresh() {
        viewModelScope.launch {
            when (val r = AigriRepository.alerts()) {
                is ApiResult.Ok -> _ui.update {
                    it.copy(armed = !r.value.at_farm, alerts = r.value.alerts, loaded = true, error = null)
                }
                is ApiResult.Err -> _ui.update { it.copy(error = r.message) }
            }
        }
    }

    fun setGuard(armed: Boolean) {
        _ui.update { it.copy(guardBusy = true) }
        viewModelScope.launch {
            val r = AigriRepository.setGuard(armed)
            _ui.update { it.copy(guardBusy = false) }
            when (r) {
                is ApiResult.Ok -> _ui.update { it.copy(armed = r.value) }
                is ApiResult.Err -> _ui.update { it.copy(toast = r.message) }
            }
        }
    }

    fun testSiren() {
        _ui.update { it.copy(sirenBusy = true) }
        viewModelScope.launch {
            val msg = when (val r = AigriRepository.testSiren()) {
                is ApiResult.Ok -> r.value
                is ApiResult.Err -> r.message
            }
            _ui.update { it.copy(sirenBusy = false, toast = msg) }
        }
    }

    fun clearToast() = _ui.update { it.copy(toast = null) }
}
