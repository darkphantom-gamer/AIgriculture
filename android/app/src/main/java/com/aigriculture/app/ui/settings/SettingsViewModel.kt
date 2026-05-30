package com.aigriculture.app.ui.settings

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.ApiResult
import com.aigriculture.app.data.net.MeResp
import com.aigriculture.app.data.net.Net
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class SettingsUi(
    val me: MeResp? = null,
    val host: String = "",
    val loggingOut: Boolean = false,
)

class SettingsViewModel : ViewModel() {
    private val _ui = MutableStateFlow(
        SettingsUi(host = Net.baseUrl?.removePrefix("https://")?.removePrefix("http://") ?: "—")
    )
    val ui: StateFlow<SettingsUi> = _ui

    init {
        viewModelScope.launch {
            (AigriRepository.me() as? ApiResult.Ok)?.let { r -> _ui.update { it.copy(me = r.value) } }
        }
    }

    fun logout(done: () -> Unit) {
        _ui.update { it.copy(loggingOut = true) }
        viewModelScope.launch {
            AigriRepository.logout()
            done()
        }
    }
}
