package com.aigriculture.app.data.net

import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener

/**
 * Read-only socket on /ws. The server pushes the full StateMsg every second; we
 * decode and emit it so the Status screen updates live, exactly like the web UI.
 */
class StateSocket {

    private var ws: WebSocket? = null

    private val _states = MutableSharedFlow<StateMsg>(replay = 1, extraBufferCapacity = 16)
    val states: SharedFlow<StateMsg> = _states

    private val _status = MutableSharedFlow<WsStatus>(replay = 1, extraBufferCapacity = 8)
    val status: SharedFlow<WsStatus> = _status

    fun connect() {
        close()
        _status.tryEmit(WsStatus.CONNECTING)
        val url = Net.wsUrl("ws")
        if (url.isEmpty()) { _status.tryEmit(WsStatus.ERROR); return }
        val req = Request.Builder().url(url).build()
        ws = Net.client.newWebSocket(req, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                _status.tryEmit(WsStatus.OPEN)
            }
            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching { Net.json.decodeFromString(StateMsg.serializer(), text) }
                    .getOrNull()?.let { if (it.type == "state") _states.tryEmit(it) }
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

    fun close() {
        ws?.close(1000, null)
        ws = null
    }
}
