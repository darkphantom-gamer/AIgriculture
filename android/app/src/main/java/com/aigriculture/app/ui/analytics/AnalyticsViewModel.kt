package com.aigriculture.app.ui.analytics

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.AnalyticsResp
import com.aigriculture.app.data.net.ApiResult
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class AnalyticsUi(
    val data: AnalyticsResp? = null,
    val loading: Boolean = true,
    val error: String? = null,
)

class AnalyticsViewModel : ViewModel() {

    private val _ui = MutableStateFlow(AnalyticsUi())
    val ui: StateFlow<AnalyticsUi> = _ui

    init { load() }

    fun load() {
        _ui.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val a = AigriRepository.analytics()) {
                is ApiResult.Ok -> _ui.update { it.copy(data = a.value, loading = false, error = null) }
                is ApiResult.Err -> _ui.update { it.copy(loading = false, error = a.message) }
            }
        }
    }
}
