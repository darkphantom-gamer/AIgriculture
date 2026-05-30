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
