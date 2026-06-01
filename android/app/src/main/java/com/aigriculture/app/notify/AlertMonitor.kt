package com.aigriculture.app.notify

import android.content.Context
import com.aigriculture.app.data.net.StateMsg
import com.aigriculture.app.data.net.StateSocket
import com.aigriculture.app.data.net.WsStatus
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * App-wide alert watcher. Keeps one /ws connection open for the logged-in app
 * shell and raises phone notifications for farm state changes while the app
 * process is alive. True killed-state delivery still needs server-side push
 * notifications (FCM), but this covers foreground and recently backgrounded use.
 */
object AlertMonitor {
    private const val DRY_THRESHOLD = 45.0
    private const val DRY_REPEAT_MS = 30 * 60 * 1000L

    private var scope: CoroutineScope? = null
    private var socket: StateSocket? = null
    private var appContext: Context? = null

    private var primed = false
    private var prevThreats: Set<String> = emptySet()
    private var prevPumps: Map<String, Boolean> = emptyMap()
    private var prevDryPlants: Set<String> = emptySet()
    private var prevOfflineSensors: Set<String> = emptySet()
    private var prevAutoIrr: Boolean? = null
    private var prevAtFarm: Boolean? = null
    private var prevFarmState: String? = null
    private var prevFarmCameraOk: Boolean? = null
    private var prevSecurityCamOn: Boolean? = null
    private var prevFarmCamOn: Boolean? = null
    private var prevSocketStatus: WsStatus? = null
    private var socketPrimed = false
    private var lastScanSig: String? = null
    private val lastDryNotify = mutableMapOf<String, Long>()

    private val clock = SimpleDateFormat("h:mm a", Locale.getDefault())

    @Synchronized
    fun start(context: Context) {
        if (scope != null) return
        appContext = context.applicationContext
        NotificationHelper.ensureChannel(context)
        val s = StateSocket()
        val cs = CoroutineScope(SupervisorJob() + Dispatchers.Default)
        socket = s
        scope = cs
        cs.launch { s.states.collect { onState(it) } }
        cs.launch { s.status.collect { onSocketStatus(it) } }
        s.connect()
    }

    @Synchronized
    fun stop() {
        socket?.close(); socket = null
        scope?.cancel(); scope = null
        primed = false
        prevThreats = emptySet()
        prevPumps = emptyMap()
        prevDryPlants = emptySet()
        prevOfflineSensors = emptySet()
        prevAutoIrr = null
        prevAtFarm = null
        prevFarmState = null
        prevFarmCameraOk = null
        prevSecurityCamOn = null
        prevFarmCamOn = null
        prevSocketStatus = null
        socketPrimed = false
        lastScanSig = null
        lastDryNotify.clear()
    }

    private fun onSocketStatus(status: WsStatus) {
        val ctx = appContext ?: return
        val prev = prevSocketStatus
        prevSocketStatus = status

        if (!socketPrimed) {
            socketPrimed = status == WsStatus.OPEN || status == WsStatus.ERROR || status == WsStatus.CLOSED
            return
        }
        if (prev == status) return

        if (prev == WsStatus.OPEN && (status == WsStatus.ERROR || status == WsStatus.CLOSED)) {
            NotificationHelper.notify(ctx, "FarmMonitor connection lost", "Live farm alerts are disconnected · ${now()}")
        } else if (prev != WsStatus.OPEN && status == WsStatus.OPEN) {
            NotificationHelper.notify(ctx, "FarmMonitor connection restored", "Live farm alerts are back online · ${now()}")
        }
    }

    private fun onState(s: StateMsg) {
        val ctx = appContext ?: return
        try {
            val threats = threatNames(s)
            val pumps = s.pumps
            val dryPlants = dryPlantIds(s)
            val offlineSensors = offlineSensorIds(s)
            val scanSig = scanSignature(s)
            val farmState = farmState(s)
            val farmCameraOk = farmCameraOk(s)

            // First snapshot establishes the comparison baseline, but still raises
            // urgent current conditions so reconnecting during an active problem
            // does not hide it.
            if (!primed) {
                prevThreats = threats
                prevPumps = pumps
                prevDryPlants = dryPlants
                prevOfflineSensors = offlineSensors
                prevAutoIrr = s.auto_irr
                prevAtFarm = s.at_farm
                prevFarmState = farmState
                prevFarmCameraOk = farmCameraOk
                prevSecurityCamOn = s.security_cam_on
                prevFarmCamOn = s.farm_cam_on
                lastScanSig = scanSig
                primed = true
                notifyInitialActiveState(ctx, s, threats, dryPlants, farmState, farmCameraOk)
                return
            }

            val freshThreats = threats - prevThreats
            if (freshThreats.isNotEmpty()) {
                val names = freshThreats.joinToString(", ") { threatLabel(it) }
                NotificationHelper.notifyThreat(ctx, "Security threat detected", "$names near the farm · ${now()}")
            }
            prevThreats = threats

            for ((plant, on) in pumps) {
                val was = prevPumps[plant] ?: false
                if (on != was) {
                    val label = plantLabel(s, plant)
                    if (on) {
                        NotificationHelper.notify(ctx, "Irrigation started", "$label is being watered · ${now()}")
                    } else {
                        NotificationHelper.notify(ctx, "Irrigation stopped", "$label watering finished · ${now()}")
                    }
                }
            }
            prevPumps = pumps

            notifyDryPlants(ctx, s, dryPlants)
            prevDryPlants = dryPlants

            for (plant in offlineSensors - prevOfflineSensors) {
                NotificationHelper.notify(
                    ctx,
                    "Sensor offline",
                    "${plantLabel(s, plant)} moisture sensor stopped reporting · ${now()}",
                )
            }
            for (plant in prevOfflineSensors - offlineSensors) {
                NotificationHelper.notify(
                    ctx,
                    "Sensor online",
                    "${plantLabel(s, plant)} moisture sensor recovered · ${now()}",
                )
            }
            prevOfflineSensors = offlineSensors

            notifyBooleanChange(ctx, prevAutoIrr, s.auto_irr, "Auto irrigation", "enabled", "disabled")
            prevAutoIrr = s.auto_irr

            notifyBooleanChange(ctx, prevAtFarm, s.at_farm, "Guard mode", "disarmed: owner at farm", "armed: owner away")
            prevAtFarm = s.at_farm

            notifyBooleanChange(ctx, prevSecurityCamOn, s.security_cam_on, "Security camera", "monitoring resumed", "monitoring paused")
            prevSecurityCamOn = s.security_cam_on

            notifyBooleanChange(ctx, prevFarmCamOn, s.farm_cam_on, "FarmMonitor camera", "monitoring resumed", "monitoring paused")
            prevFarmCamOn = s.farm_cam_on

            if (farmCameraOk != null && prevFarmCameraOk != null && farmCameraOk != prevFarmCameraOk) {
                NotificationHelper.notify(
                    ctx,
                    "FarmMonitor camera",
                    if (farmCameraOk) "Camera feed recovered · ${now()}" else "Camera feed is offline · ${now()}",
                )
            }
            prevFarmCameraOk = farmCameraOk

            if (farmState != null && farmState != prevFarmState) {
                when (farmState.lowercase(Locale.US)) {
                    "queued" -> NotificationHelper.notify(ctx, "FarmMonitor scan queued", "A plant-health scan is waiting · ${now()}")
                    "scanning" -> NotificationHelper.notify(ctx, "FarmMonitor scan running", "Plant-health analysis started · ${now()}")
                    "error" -> NotificationHelper.notify(ctx, "FarmMonitor needs attention", "${farmMessage(s) ?: "Scan failed"} · ${now()}")
                }
            }
            prevFarmState = farmState

            if (scanSig != null && scanSig != lastScanSig) {
                val msg = scanMessage(s) ?: "A new plant-health scan is ready."
                NotificationHelper.notify(ctx, "Farm scan complete", "$msg · ${now()}")
            }
            if (scanSig != null) lastScanSig = scanSig
        } catch (_: Exception) {
            // Malformed state push — skip this frame, keep watching.
        }
    }

    private fun notifyDryPlants(ctx: Context, s: StateMsg, dryPlants: Set<String>) {
        val nowMs = System.currentTimeMillis()
        for (plant in dryPlants) {
            val becameDry = plant !in prevDryPlants
            val dueAgain = nowMs - (lastDryNotify[plant] ?: 0L) >= DRY_REPEAT_MS
            if (becameDry || dueAgain) {
                val pct = s.moisture[plant]?.toInt()
                val value = pct?.let { " ($it%)" }.orEmpty()
                NotificationHelper.notify(
                    ctx,
                    "Plant running dry",
                    "${plantLabel(s, plant)} moisture is low$value · ${now()}",
                )
                lastDryNotify[plant] = nowMs
            }
        }
        (lastDryNotify.keys - dryPlants).forEach { lastDryNotify.remove(it) }
    }

    private fun notifyInitialActiveState(
        ctx: Context,
        s: StateMsg,
        threats: Set<String>,
        dryPlants: Set<String>,
        farmState: String?,
        farmCameraOk: Boolean?,
    ) {
        if (threats.isNotEmpty()) {
            val names = threats.joinToString(", ") { threatLabel(it) }
            NotificationHelper.notifyThreat(ctx, "Security threat active", "$names near the farm · ${now()}")
        }
        if (dryPlants.isNotEmpty()) {
            val labels = dryPlants.take(3).joinToString(", ") { plantLabel(s, it) }
            val more = if (dryPlants.size > 3) " +${dryPlants.size - 3} more" else ""
            NotificationHelper.notify(ctx, "Plants running dry", "$labels$more need water · ${now()}")
            val nowMs = System.currentTimeMillis()
            dryPlants.forEach { lastDryNotify[it] = nowMs }
        }
        when (farmState?.lowercase(Locale.US)) {
            "queued" -> NotificationHelper.notify(ctx, "FarmMonitor scan queued", "A plant-health scan is waiting · ${now()}")
            "scanning" -> NotificationHelper.notify(ctx, "FarmMonitor scan running", "Plant-health analysis is active · ${now()}")
            "error" -> NotificationHelper.notify(ctx, "FarmMonitor needs attention", "${farmMessage(s) ?: "Scan failed"} · ${now()}")
        }
        if (farmCameraOk == false) {
            NotificationHelper.notify(ctx, "FarmMonitor camera", "Camera feed is offline · ${now()}")
        }
    }

    private fun notifyBooleanChange(
        ctx: Context,
        previous: Boolean?,
        current: Boolean?,
        title: String,
        trueText: String,
        falseText: String,
    ) {
        if (previous == null || current == null || previous == current) return
        NotificationHelper.notify(ctx, title, "${if (current) trueText else falseText} · ${now()}")
    }

    private fun now(): String = clock.format(Date())

    private fun str(el: JsonElement?): String? =
        (el as? JsonPrimitive)?.contentOrNull

    private fun bool(el: JsonElement?): Boolean? =
        (el as? JsonPrimitive)?.booleanOrNull

    private fun threatNames(s: StateMsg): Set<String> {
        val arr = s.alerts as? JsonArray ?: return emptySet()
        return arr.mapNotNull { el -> str((el as? JsonObject)?.get("name")) }.toSet()
    }

    private fun dryPlantIds(s: StateMsg): Set<String> {
        val active = s.active_plants.toSet().ifEmpty { s.moisture.keys }
        return s.moisture.mapNotNull { (plant, value) ->
            if (plant in active && value != null && value < DRY_THRESHOLD) plant else null
        }.toSet()
    }

    private fun offlineSensorIds(s: StateMsg): Set<String> {
        val active = s.active_plants.toSet().ifEmpty { s.sensor_status.keys }
        return s.sensor_status.mapNotNull { (plant, status) ->
            if (plant in active && !status.online && status.last_error != "not_read_yet") plant else null
        }.toSet()
    }

    private fun plantLabel(s: StateMsg, plant: String): String =
        s.plant_names[plant]?.takeIf { it.isNotBlank() } ?: "Plant ${plant.uppercase(Locale.US)}"

    private fun threatLabel(name: String): String =
        name.replace('_', ' ').replaceFirstChar { it.titlecase(Locale.getDefault()) }

    private fun farmObj(s: StateMsg): JsonObject? = s.farm_monitor as? JsonObject

    private fun farmState(s: StateMsg): String? = str(farmObj(s)?.get("state"))

    private fun farmMessage(s: StateMsg): String? = str(farmObj(s)?.get("message"))

    private fun farmCameraOk(s: StateMsg): Boolean? = bool(farmObj(s)?.get("camera_ok"))

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
