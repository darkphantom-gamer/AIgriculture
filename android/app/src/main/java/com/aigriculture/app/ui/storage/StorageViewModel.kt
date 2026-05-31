package com.aigriculture.app.ui.storage

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.ApiResult
import com.aigriculture.app.data.net.StorageEvent
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

// Nested storage hierarchy preserved from the backend tree
// (GET /api/storage -> {year:{month:{day:[event]}}}), so the UI can render the
// real Year > Month > Day > Time folder structure instead of a flat list.
data class StorageDay(val day: String, val events: List<StorageEvent>)
data class StorageMonth(val month: String, val days: List<StorageDay>, val count: Int)
data class StorageYear(val year: String, val months: List<StorageMonth>, val count: Int)

data class StorageUi(
    val years: List<StorageYear> = emptyList(),
    val total: Int = 0,
    val security: Int = 0,
    val disease: Int = 0,
    val harvest: Int = 0,
    val loading: Boolean = true,
    val error: String? = null,
)

/** Dedicated Storage browser — the real nested Year/Month/Day/Time event tree. */
class StorageViewModel : ViewModel() {
    private val _ui = MutableStateFlow(StorageUi())
    val ui: StateFlow<StorageUi> = _ui

    init { load() }

    fun load() {
        _ui.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            when (val r = AigriRepository.storage()) {
                is ApiResult.Ok -> _ui.update { build(r.value) }
                is ApiResult.Err -> _ui.update { it.copy(loading = false, error = r.message) }
            }
        }
    }

    private fun build(
        tree: Map<String, Map<String, Map<String, List<StorageEvent>>>>,
    ): StorageUi {
        var total = 0
        var sec = 0
        var dis = 0
        var har = 0
        // Newest first at every level (descending y/m/d, descending time).
        val years = tree.entries.sortedByDescending { it.key }.map { (y, months) ->
            val ms = months.entries.sortedByDescending { it.key }.map { (m, days) ->
                val ds = days.entries.sortedByDescending { it.key }.map { (d, events) ->
                    events.forEach { e ->
                        total++
                        val t = (e.meta.event_type ?: e.meta.label ?: "").lowercase()
                        when {
                            t.contains("ripe") || t.contains("harvest") -> har++
                            t.contains("disease") || t.contains("plant") ||
                                t.contains("leaf") || t.contains("fruit") || t.contains("health") -> dis++
                            else -> sec++
                        }
                    }
                    StorageDay(d, events.sortedByDescending { it.time })
                }
                StorageMonth(m, ds, ds.sumOf { it.events.size })
            }
            StorageYear(y, ms, ms.sumOf { it.count })
        }
        return StorageUi(
            years = years,
            total = total,
            security = sec,
            disease = dis,
            harvest = har,
            loading = false,
            error = null,
        )
    }
}
