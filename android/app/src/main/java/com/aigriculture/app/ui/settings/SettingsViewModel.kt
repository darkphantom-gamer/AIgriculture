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
    val email: String = "",
    val smtpReady: Boolean = false,
    val emailSaving: Boolean = false,
    val sirenEnabled: Boolean = true,
    val sirenBusy: Boolean = false,
    val toast: String? = null,
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
        viewModelScope.launch {
            (AigriRepository.getNotifEmail() as? ApiResult.Ok)?.let { r ->
                _ui.update { it.copy(email = r.value.email, smtpReady = r.value.smtp_ready) }
            }
        }
    }

    fun setEmail(v: String) = _ui.update { it.copy(email = v) }

    fun saveEmail() {
        _ui.update { it.copy(emailSaving = true) }
        viewModelScope.launch {
            val msg = when (val r = AigriRepository.setNotifEmail(_ui.value.email.trim())) {
                is ApiResult.Ok ->
                    if (r.value.smtp_ready) "Saved — a confirmation email is on the way."
                    else "Saved. (Server SMTP isn't configured yet.)"
                is ApiResult.Err -> r.message
            }
            _ui.update { it.copy(emailSaving = false, toast = msg, smtpReady = it.smtpReady) }
        }
    }

    fun toggleSiren(enabled: Boolean) {
        _ui.update { it.copy(sirenBusy = true) }
        viewModelScope.launch {
            when (val r = AigriRepository.setSiren(enabled)) {
                is ApiResult.Ok -> _ui.update { it.copy(sirenEnabled = r.value, sirenBusy = false) }
                is ApiResult.Err -> _ui.update { it.copy(sirenBusy = false, toast = r.message) }
            }
        }
    }

    fun clearToast() = _ui.update { it.copy(toast = null) }

    fun logout(done: () -> Unit) {
        _ui.update { it.copy(loggingOut = true) }
        viewModelScope.launch {
            AigriRepository.logout()
            done()
        }
    }
}
