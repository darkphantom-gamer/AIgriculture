package com.aigriculture.app.data.net

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.put
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * FLORA chat socket. Sends {type:"message", content, mode, brief} and streams the
 * server's events (typing, response, tool_call, tool_result, auto_offline, error,
 * thinking, scheduled_result) — the exact protocol the dashboard's chat uses.
 * The pmc_token cookie rides the handshake via the shared OkHttp client.
 */
class FloraSocket {

    private var ws: WebSocket? = null

    private val _events = MutableSharedFlow<JsonObject>(extraBufferCapacity = 128)
    val events: SharedFlow<JsonObject> = _events

    private val _status = MutableSharedFlow<WsStatus>(replay = 1, extraBufferCapacity = 8)
    val status: SharedFlow<WsStatus> = _status

    fun connect() {
        close()
        _status.tryEmit(WsStatus.CONNECTING)
        val url = Net.wsUrl("ws/flora")
        if (url.isEmpty()) { _status.tryEmit(WsStatus.ERROR); return }
        val req = Request.Builder().url(url).build()
        ws = Net.client.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                _status.tryEmit(WsStatus.OPEN)
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching { Net.json.parseToJsonElement(text).jsonObject }
                    .getOrNull()?.let { _events.tryEmit(it) }
            }
            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                _status.tryEmit(WsStatus.CLOSED)
                webSocket.close(1000, null)
            }
            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                _status.tryEmit(WsStatus.ERROR)
            }
        })
    }

    fun send(content: String, mode: String, brief: Boolean = false): Boolean {
        val socket = ws ?: return false
        val payload = buildJsonObject {
            put("type", "message")
            put("content", content)
            put("mode", mode)
            put("brief", brief)
        }
        return socket.send(payload.toString())
    }

    fun close() {
        ws?.close(1000, null)
        ws = null
    }
}
