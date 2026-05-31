package com.aigriculture.app.notify

import android.content.Context
import com.aigriculture.app.data.net.StateMsg
import com.aigriculture.app.data.net.StateSocket
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.contentOrNull
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * App-wide alert watcher. Keeps ONE /ws connection open for the whole logged-in
 * session (started by the app shell) and raises a phone notification when the
 * server reports a new security-camera threat, a finished FarmMonitor scan, or an
 * irrigation pump starting/stopping — each stamped with the time. This makes the
 * app alert like a regular app while it is running (foreground or recently
 * backgrounded). True killed-state delivery would need server-side push (FCM).
 */
object AlertMonitor {
    private var scope: CoroutineScope? = null
    private var socket: StateSocket? = null
    private var appContext: Context? = null

    private var primed = false
    private var prevThreats: Set<String> = emptySet()
    private var prevPumps: Map<String, Boolean> = emptyMap()
    private var lastScanSig: String? = null

    private val clock = SimpleDateFormat("h:mm a", Locale.getDefault())

    @Synchronized
    fun start(context: Context) {
        if (scope != null) return // already running
        appContext = context.applicationContext
        NotificationHelper.ensureChannel(context)
        val s = StateSocket()
        val cs = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        socket = s
        scope = cs
        cs.launch { s.states.collect { onState(it) } }
        s.connect()
    }

    @Synchronized
    fun stop() {
        socket?.close(); socket = null
        scope?.cancel(); scope = null
        primed = false
        prevThreats = emptySet()
        prevPumps = emptyMap()
        lastScanSig = null
    }

    private fun onState(s: StateMsg) {
        val ctx = appContext ?: return
        try {
            val threats = threatNames(s)
            val pumps = s.pumps
            val scanSig = scanSignature(s)

            // First snapshot establishes a baseline silently — never notify for
            // state that was already true when the app connected.
            if (!primed) {
                prevThreats = threats
                prevPumps = pumps
                lastScanSig = scanSig
                primed = true
                return
            }

            val freshThreats = threats - prevThreats
            if (freshThreats.isNotEmpty()) {
                val names = freshThreats.joinToString(", ") { it.replaceFirstChar(Char::uppercase) }
                NotificationHelper.notify(ctx, "⚠ Security threat detected", "$names near the farm · ${now()}")
            }
            prevThreats = threats

            for ((plant, on) in pumps) {
                val was = prevPumps[plant] ?: false
                if (on != was) {
                    val label = "Plant ${plant.uppercase()}"
                    if (on) {
                        NotificationHelper.notify(ctx, "💧 Irrigation started", "$label is being watered · ${now()}")
                    } else {
                        NotificationHelper.notify(ctx, "Irrigation stopped", "$label watering finished · ${now()}")
                    }
                }
            }
            prevPumps = pumps

            if (scanSig != null && scanSig != lastScanSig) {
                val msg = scanMessage(s) ?: "A new plant-health scan is ready."
                NotificationHelper.notify(ctx, "🌿 Farm scan complete", "$msg · ${now()}")
            }
            if (scanSig != null) lastScanSig = scanSig
        } catch (_: Exception) {
            // Malformed state push — skip this frame, keep watching.
        }
    }

    private fun now(): String = clock.format(Date())

    private fun str(el: kotlinx.serialization.json.JsonElement?): String? =
        (el as? JsonPrimitive)?.contentOrNull

    private fun threatNames(s: StateMsg): Set<String> {
        val arr = s.alerts as? JsonArray ?: return emptySet()
        return arr.mapNotNull { el -> str((el as? JsonObject)?.get("name")) }.toSet()
    }

    private fun farmObj(s: StateMsg): JsonObject? = s.farm_monitor as? JsonObject

    /** A stable signature for the latest finished scan, so we notify once per scan. */
    private fun scanSignature(s: StateMsg): String? {
        val lr = farmObj(s)?.get("last_result") as? JsonObject ?: return null
        return str(lr["completed_at"]) ?: str(lr["message"])
    }

    private fun scanMessage(s: StateMsg): String? {
        val lr = farmObj(s)?.get("last_result") as? JsonObject ?: return null
        return str(lr["message"]) ?: str(lr["label"])
    }
}
