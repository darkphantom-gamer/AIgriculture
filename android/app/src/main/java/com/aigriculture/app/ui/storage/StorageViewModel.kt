package com.aigriculture.app.ui.storage

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.ApiResult
import com.aigriculture.app.data.net.Net
import com.aigriculture.app.data.net.StorageEvent
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class StorageEventRow(
    val date: String,
    val time: String,
    val type: String,
    val label: String,
    val images: Int,
    val firstImage: String? = null,
)

data class StorageUi(
    val events: List<StorageEventRow> = emptyList(),
    val loading: Boolean = true,
    val error: String? = null,
)

/** Dedicated Storage browser — every stored security/farm/moisture event. */
class StorageViewModel : ViewModel() {
    private val _ui = MutableStateFlow(StorageUi())
    val ui: StateFlow<StorageUi> = _ui

    init { load() }

    fun load() {
        _ui.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = AigriRepository.storage()) {
                is ApiResult.Ok -> _ui.update { it.copy(events = flatten(r.value), loading = false, error = null) }
                is ApiResult.Err -> _ui.update { it.copy(loading = false, error = r.message) }
            }
        }
    }

    private fun flatten(tree: Map<String, Map<String, Map<String, List<StorageEvent>>>>): List<StorageEventRow> {
        val rows = mutableListOf<StorageEventRow>()
        tree.forEach { (y, months) ->
            months.forEach { (m, days) ->
                days.forEach { (d, events) ->
                    events.forEach { e ->
                        val first = e.images.firstOrNull()
                        val img = if (first != null) Net.absUrl("storage_img/$y/$m/$d/${e.time}/$first") else null
                        rows.add(
                            StorageEventRow(
                                date = "$y/$m/$d",
                                time = e.time,
                                type = e.meta.event_type ?: e.meta.label ?: "event",
                                label = e.meta.label ?: e.meta.message ?: "",
                                images = e.images.size,
                                firstImage = img,
                            )
                        )
                    }
                }
            }
        }
        return rows
            .sortedWith(compareByDescending<StorageEventRow> { it.date }.thenByDescending { it.time })
            .take(60)
    }
}
