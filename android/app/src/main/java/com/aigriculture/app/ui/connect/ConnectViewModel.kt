package com.aigriculture.app.ui.connect

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.ApiResult
import com.aigriculture.app.data.net.Net
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

data class ConnectUi(
    val address: String = "",
    val loading: Boolean = false,
    val error: String? = null,
)

class ConnectViewModel : ViewModel() {
    private val _ui = MutableStateFlow(ConnectUi(address = Net.baseUrl ?: ""))
    val ui: StateFlow<ConnectUi> = _ui

    fun onAddressChange(v: String) {
        _ui.value = _ui.value.copy(address = v, error = null)
    }

    fun connect(onConnected: () -> Unit) {
        val addr = _ui.value.address.trim()
        if (addr.isEmpty()) {
            _ui.value = _ui.value.copy(error = "Enter your Pi's address, e.g. 192.168.1.50:8000")
            return
        }
        _ui.value = _ui.value.copy(loading = true, error = null)
        viewModelScope.launch {
            when (val r = AigriRepository.probeServer(addr)) {
                is ApiResult.Ok -> {
                    _ui.value = _ui.value.copy(loading = false)
                    onConnected()
                }
                is ApiResult.Err -> _ui.value = _ui.value.copy(loading = false, error = r.message)
            }
        }
    }
}
