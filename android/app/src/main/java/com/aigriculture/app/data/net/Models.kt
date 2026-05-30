package com.aigriculture.app.data.net

import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonElement

// All shapes mirror the exact JSON keys returned by main.py. Unknown keys are
// ignored by the Json config, and every field has a default so a partial payload
// never crashes parsing.

@Serializable
data class LoginResp(
    val ok: Boolean = false,
    val username: String? = null,
    val error: String? = null,
)

@Serializable
data class MeResp(
    val username: String? = null,
    val display_name: String? = null,
    val role: String? = null,
    val avatar_url: String? = null,
    val permissions: List<String> = emptyList(),
)

@Serializable
data class FloraStatusResp(
    val ok: Boolean = false,
    val providers: List<String> = emptyList(),
    val providers_configured: Boolean = false,
    val internet_reachable: Boolean = false,
    val effective_mode: String = "offline",
)

@Serializable
data class PlantsResp(
    val active: List<String> = emptyList(),
    val all: List<String> = emptyList(),
    val names: Map<String, String> = emptyMap(),
    val pumps: List<String> = emptyList(),
)

@Serializable
data class SensorStatus(
    val online: Boolean = false,
    val last_error: String? = null,
    val pct: Double? = null,
    val raw: Int? = null,
)

// GET /api/state and the /ws push share this exact shape (type:"state").
@Serializable
data class StateMsg(
    val type: String = "state",
    val active_plants: List<String> = emptyList(),
    val all_plants: List<String> = emptyList(),
    val plant_names: Map<String, String> = emptyMap(),
    val moisture: Map<String, Double?> = emptyMap(),
    val sensor_status: Map<String, SensorStatus> = emptyMap(),
    val pumps: Map<String, Boolean> = emptyMap(),
    val auto_irr: Boolean = false,
    val at_farm: Boolean = false,
    val burst: Map<String, String> = emptyMap(),
    val alerts: JsonElement? = null,
    val last_watered: JsonElement? = null,
    val farm_monitor: JsonElement? = null,
)

@Serializable
data class PumpResp(
    val ok: Boolean = false,
    val plant: String? = null,
    val on: Boolean? = null,
    val error: String? = null,
    val message: String? = null,
    val moisture: Double? = null,
    val lock_at: Double? = null,
    val warning: String? = null,
    val sensor_error: String? = null,
)

@Serializable
data class AutoIrrReq(val enabled: Boolean)

@Serializable
data class AutoIrrResp(val ok: Boolean = false, val enabled: Boolean = false)

@Serializable
data class FloraChatReq(val content: String, val mode: String, val brief: Boolean = false)

@Serializable
data class FloraChatResp(
    val ok: Boolean = false,
    val response: String = "",
    val error: String? = null,
)

@Serializable
data class PresenceReq(val at_farm: Boolean)

@Serializable
data class PresenceResp(val ok: Boolean = false, val at_farm: Boolean = false)

@Serializable
data class BuzzerReq(val enabled: Boolean)

@Serializable
data class SimpleOk(
    val ok: Boolean = false,
    val message: String? = null,
    val error: String? = null,
    val available: Boolean? = null,
    val enabled: Boolean? = null,
)

@Serializable
data class CameraResp(
    val ok: Boolean = false,
    val camera: String? = null,
    val on: Boolean? = null,
    val security_cam_on: Boolean? = null,
    val farm_cam_on: Boolean? = null,
)

// Summary of a completed FarmMonitor scan (farm_scan_status["last_result"]).
@Serializable
data class FarmResult(
    val event_type: String? = null,
    val label: String? = null,
    val message: String? = null,
    val usable_frames: Int? = null,
    val disease_frames: Int? = null,
    val ripeness_frames: Int? = null,
    val completed_at: String? = null,
    val manual: Boolean? = null,
)

// /api/farm_monitor/status — _farm_status_snapshot(). next_scan_at/last_scan_at
// can be null or a timestamp string, so they stay loose.
@Serializable
data class FarmStatus(
    val state: String? = null,
    val stage: String? = null,
    val message: String? = null,
    val next_scan_at: JsonElement? = null,
    val last_scan_at: JsonElement? = null,
    val last_result: FarmResult? = null,
    val camera_ok: Boolean? = null,
    val camera_error: String? = null,
    val total_cycles: Int? = null,
    val current_cycle: Int? = null,
    val target_frames: Int? = null,
    val captured_frames: Int? = null,
    val usable_frames: Int? = null,
    val disease_frames: Int? = null,
    val ripeness_frames: Int? = null,
)

@Serializable
data class AlertsResp(
    val alerts: List<String> = emptyList(),
    val at_farm: Boolean = false,
)

@Serializable
data class IrrEvent(val t: Long = 0, val plant: String = "")

// /api/analytics — moisture_history is intentionally omitted (heavy, ~288 pts/plant).
@Serializable
data class AnalyticsResp(
    val moisture_current: Map<String, Double?> = emptyMap(),
    val hourly_detections: Map<String, Int> = emptyMap(),
    val species_counts: Map<String, Int> = emptyMap(),
    val storage_summary: Map<String, Int> = emptyMap(),
    val irr_history: List<IrrEvent> = emptyList(),
    val latest_farm_event: StorageMeta? = null,
)

// One stored event's meta.json (security snapshot or farm scan).
@Serializable
data class StorageMeta(
    val event_type: String? = null,
    val label: String? = null,
    val message: String? = null,
    val confidence: Double? = null,
    val timestamp: String? = null,
)

// /api/storage returns { year: { month: { day: [StorageEvent] } } }.
@Serializable
data class StorageEvent(
    val time: String = "",
    val meta: StorageMeta = StorageMeta(),
    val images: List<String> = emptyList(),
)

// ── "+ Add sensors" (runtime sensor discovery) ─────────────────────────────────
@Serializable
data class SensorChannel(
    val addr: Int = 0,
    val channel: Int = 0,
    val raw: Int? = null,
    val plausible: Boolean = false,
    val assigned_to: String? = null,
    val error: String? = null,
)

@Serializable
data class SensorScanResp(
    val ok: Boolean = false,
    val error: String? = null,
    val channels: List<SensorChannel> = emptyList(),
    val unassigned: List<SensorChannel> = emptyList(),
    val i2c_available: Boolean = false,
)

@Serializable
data class AddedSensor(
    val plant: String = "",
    val addr: Int = 0,
    val channel: Int = 0,
    val relay_pin: Int? = null,
)

@Serializable
data class SensorAddResp(
    val ok: Boolean = false,
    val error: String? = null,
    val found: Int? = null,
    val added: List<AddedSensor> = emptyList(),
    val active: List<String> = emptyList(),
    val all: List<String> = emptyList(),
)

@Serializable
data class SensorAddReq(val count: Int)

// ── Notification email (Settings) ──────────────────────────────────────────────
@Serializable
data class NotifEmailResp(
    val configured: Boolean = false,
    val email: String = "",
    val smtp_ready: Boolean = false,
    val ok: Boolean = false,
    val error: String? = null,
)

@Serializable
data class NotifEmailReq(val email: String)

// ── FLORA scheduled tasks (/api/flora/schedule returns a JSON array of these) ──
@Serializable
data class ScheduleTask(
    val job_id: String = "",
    val tool_name: String? = null,
    val tool_args: String = "{}",
    val repeat: String = "once",
    val run_at: String? = null,
    val run_at_iso: String = "",
    val status: String = "pending",
)
