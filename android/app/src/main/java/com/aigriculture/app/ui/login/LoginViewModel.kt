package com.aigriculture.app.ui.login

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.ApiResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class LoginUi(
    val username: String = "",
    val password: String = "",
    val loading: Boolean = false,
    val error: String? = null,
)

class LoginViewModel : ViewModel() {
    private val _ui = MutableStateFlow(LoginUi())
    val ui: StateFlow<LoginUi> = _ui

    fun onUsername(v: String) { _ui.value = _ui.value.copy(username = v, error = null) }
    fun onPassword(v: String) { _ui.value = _ui.value.copy(password = v, error = null) }

    fun submit(onLoggedIn: () -> Unit) {
        val s = _ui.value
        if (s.username.isBlank() || s.password.isBlank()) {
            _ui.value = s.copy(error = "Enter your username and password.")
            return
        }
        _ui.value = s.copy(loading = true, error = null)
        viewModelScope.launch {
            when (val r = AigriRepository.login(s.username.trim(), s.password)) {
                is ApiResult.Ok -> {
                    _ui.value = _ui.value.copy(loading = false, password = "")
                    onLoggedIn()
                }
                is ApiResult.Err -> _ui.value = _ui.value.copy(loading = false, error = r.message)
            }
        }
    }
}
