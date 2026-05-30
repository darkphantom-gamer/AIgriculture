package com.aigriculture.app.ui.flora

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.aigriculture.app.data.net.AigriRepository
import com.aigriculture.app.data.net.ApiResult
import com.aigriculture.app.data.net.FloraSocket
import com.aigriculture.app.data.net.WsStatus
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.jsonPrimitive

enum class Role { USER, FLORA, SYS }
data class ChatMsg(val id: Long, val role: Role, val text: String)

data class FloraUi(
    val messages: List<ChatMsg> = emptyList(),
    val typing: Boolean = false,
    val mode: String = "offline", // "cloud" | "offline"
    val connected: Boolean = false,
    val input: String = "",
)

/**
 * Mirrors the dashboard's FLORA chat: sends {type:"message",...} over /ws/flora and
 * renders the server's event stream. Falls back to POST /api/flora/chat if the
 * socket can't open.
 */
class FloraViewModel : ViewModel() {

    private val socket = FloraSocket()
    private var counter = 0L
    private fun nextId() = ++counter

    private val _ui = MutableStateFlow(
        FloraUi(
            messages = listOf(
                ChatMsg(
                    nextId(), Role.FLORA,
                    "Hi, I'm FLORA. Ask about your farm, or tell me to water a plant, run a scan, or arm the guard."
                )
            )
        )
    )
    val ui: StateFlow<FloraUi> = _ui

    init {
        viewModelScope.launch {
            (AigriRepository.floraStatus() as? ApiResult.Ok)?.let { r ->
                _ui.update { it.copy(mode = r.value.effective_mode) }
            }
        }
        viewModelScope.launch {
            socket.status.collect { st -> _ui.update { it.copy(connected = st == WsStatus.OPEN) } }
        }
        viewModelScope.launch {
            socket.events.collect { handleEvent(it) }
        }
        socket.connect()
    }

    fun onInput(v: String) = _ui.update { it.copy(input = v) }
    fun setMode(m: String) = _ui.update { it.copy(mode = m) }
    fun reconnect() = socket.connect()

    fun send() {
        val text = _ui.value.input.trim()
        if (text.isEmpty()) return
        addMsg(Role.USER, text)
        _ui.update { it.copy(input = "") }
        val mode = _ui.value.mode
        val sent = socket.send(text, mode)
        if (!sent) {
            _ui.update { it.copy(typing = true) }
            viewModelScope.launch {
                when (val r = AigriRepository.floraChat(text, mode)) {
                    is ApiResult.Ok -> {
                        _ui.update { it.copy(typing = false) }
                        addMsg(Role.FLORA, r.value.ifBlank { "FLORA finished without text." })
                    }
                    is ApiResult.Err -> {
                        _ui.update { it.copy(typing = false) }
                        addMsg(Role.SYS, "⚠️ ${r.message}")
                    }
                }
            }
        }
    }

    private fun handleEvent(m: JsonObject) {
        when (m["type"]?.jsonPrimitive?.content ?: return) {
            "typing" -> {
                val active = m["active"]?.jsonPrimitive?.booleanOrNull ?: false
                _ui.update { it.copy(typing = active) }
            }
            "response" -> { _ui.update { it.copy(typing = false) }; addMsg(Role.FLORA, str(m, "content")) }
            "error" -> { _ui.update { it.copy(typing = false) }; addMsg(Role.SYS, "⚠️ " + str(m, "content")) }
            "thinking" -> addMsg(Role.SYS, str(m, "content"))
            "auto_offline" -> {
                _ui.update { it.copy(mode = "offline") }
                addMsg(Role.SYS, "📡 Offline: " + str(m, "reason"))
            }
            "tool_call" -> addMsg(Role.SYS, "🔧 " + str(m, "tool") + "…")
            "scheduled_result" -> {
                val summary = m["summary"]?.jsonPrimitive?.content
                addMsg(Role.FLORA, summary ?: ("✅ " + str(m, "tool") + " completed"))
            }
            // tool_result and other intermediate events: the final 'response' carries the text.
        }
    }

    private fun str(m: JsonObject, key: String): String = m[key]?.jsonPrimitive?.content ?: ""

    private fun addMsg(role: Role, text: String) {
        if (text.isBlank() && role != Role.SYS) return
        _ui.update { it.copy(messages = it.messages + ChatMsg(nextId(), role, text)) }
    }

    override fun onCleared() {
        socket.close()
        super.onCleared()
    }
}
