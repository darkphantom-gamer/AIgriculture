package com.aigriculture.app.ui.analytics

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.AnalyticsResp
import com.aigriculture.app.data.net.ApiResult
import com.aigriculture.app.data.net.StorageEvent
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

/** One row in the "Recent events" list, flattened from the nested storage tree. */
data class EventRow(
    val date: String,
    val time: String,
    val type: String,
    val label: String,
    val images: Int,
)

data class AnalyticsUi(
    val data: AnalyticsResp? = null,
    val events: List<EventRow> = emptyList(),
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
        // Events are secondary — a failure here shouldn't blank the analytics view.
        viewModelScope.launch {
            when (val s = AigriRepository.storage()) {
                is ApiResult.Ok -> _ui.update { it.copy(events = flatten(s.value)) }
                is ApiResult.Err -> Unit
            }
        }
    }

    private fun flatten(tree: Map<String, Map<String, Map<String, List<StorageEvent>>>>): List<EventRow> {
        val rows = mutableListOf<EventRow>()
        tree.forEach { (y, months) ->
            months.forEach { (m, days) ->
                days.forEach { (d, events) ->
                    events.forEach { e ->
                        rows.add(
                            EventRow(
                                date = "$y/$m/$d",
                                time = e.time,
                                type = e.meta.event_type ?: e.meta.label ?: "event",
                                label = e.meta.label ?: e.meta.message ?: "",
                                images = e.images.size,
                            )
                        )
                    }
                }
            }
        }
        return rows
            .sortedWith(compareByDescending<EventRow> { it.date }.thenByDescending { it.time })
            .take(30)
    }
}
