package com.aigriculture.app.data.net

import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive
import retrofit2.HttpException
import java.net.ConnectException
import java.net.SocketTimeoutException
import java.net.UnknownHostException

sealed class ApiResult<out T> {
    data class Ok<T>(val value: T) : ApiResult<T>()
    data class Err(val message: String, val code: Int = 0) : ApiResult<Nothing>()
}

/** All server tasking goes through here so error handling stays consistent. */
object AigriRepository {

    /** Validate that [input] points at a reachable AIgriculture server. */
    suspend fun probeServer(input: String): ApiResult<Unit> {
        if (!Net.setBaseUrl(input)) return ApiResult.Err("That doesn't look like a valid address.")
        return try {
            val resp = Net.api.probeLogin()
            if (!resp.isSuccessful) {
                return ApiResult.Err("Server responded ${resp.code()} — check the address and port.")
            }
            val body = resp.body()?.string().orEmpty()
            if (body.contains("AIgriculture", true) || body.contains("pmc_token", true) ||
                body.contains("password", true)
            ) ApiResult.Ok(Unit)
            else ApiResult.Err("Reached a server, but it doesn't look like AIgriculture.")
        } catch (e: Exception) {
            ApiResult.Err(friendly(e))
        }
    }

    suspend fun login(username: String, password: String): ApiResult<String> = try {
        val resp = Net.api.login(username, password)
        val body = resp.body()
        when {
            resp.isSuccessful && body?.ok == true -> ApiResult.Ok(body.username ?: username)
            resp.code() == 429 -> ApiResult.Err(body?.error ?: "Too many attempts. Try again in 15 minutes.", 429)
            resp.code() == 401 -> ApiResult.Err(body?.error ?: "Invalid credentials.", 401)
            resp.code() == 503 -> ApiResult.Err(body?.error ?: "Auth backend unavailable — check server logs.", 503)
            else -> ApiResult.Err(body?.error ?: "Login failed (${resp.code()}).", resp.code())
        }
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun me(): ApiResult<MeResp> = call { Net.api.me() }
    suspend fun floraStatus(): ApiResult<FloraStatusResp> = call { Net.api.floraStatus() }
    suspend fun plants(): ApiResult<PlantsResp> = call { Net.api.plants() }
    suspend fun state(): ApiResult<StateMsg> = call { Net.api.state() }

    suspend fun pump(plant: String, on: Boolean): ApiResult<PumpResp> = try {
        val resp = Net.api.pump(plant, if (on) "on" else "off")
        val b = resp.body()
        when {
            resp.isSuccessful && b?.ok == true -> ApiResult.Ok(b)
            b?.error == "locked" -> ApiResult.Err("Soil already wet — pump hard-locked at ${b.lock_at?.toInt() ?: 70}%.", 409)
            b?.error == "sensor_only" -> ApiResult.Err(b.message ?: "No relay/pump configured for this plant.", 409)
            else -> ApiResult.Err(b?.message ?: b?.error ?: "Pump command failed (${resp.code()}).", resp.code())
        }
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun setAuto(enabled: Boolean): ApiResult<Boolean> = try {
        val resp = Net.api.autoIrrigation(AutoIrrReq(enabled))
        val b = resp.body()
        if (resp.isSuccessful && b?.ok == true) ApiResult.Ok(b.enabled)
        else ApiResult.Err("Couldn't change auto-irrigation (${resp.code()}).", resp.code())
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun floraSchedule(): ApiResult<List<ScheduleTask>> = try {
        val resp = Net.api.floraSchedule()
        val body = resp.body()
        if (resp.isSuccessful && body is JsonArray) {
            ApiResult.Ok(
                body.mapNotNull {
                    runCatching { Net.json.decodeFromJsonElement(ScheduleTask.serializer(), it) }.getOrNull()
                }
            )
        } else {
            ApiResult.Ok(emptyList())
        }
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun floraChat(content: String, mode: String): ApiResult<String> = try {
        val resp = Net.api.floraChat(FloraChatReq(content, mode))
        val b = resp.body()
        if (resp.isSuccessful && b?.ok == true) ApiResult.Ok(b.response)
        else ApiResult.Err(b?.error ?: "FLORA request failed (${resp.code()}).", resp.code())
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    // Guard ON ("armed") means you're away → server's at_farm = false.
    suspend fun setGuard(armed: Boolean): ApiResult<Boolean> = try {
        val resp = Net.api.setPresence(PresenceReq(at_farm = !armed))
        val b = resp.body()
        if (resp.isSuccessful && b?.ok == true) ApiResult.Ok(!b.at_farm)
        else ApiResult.Err("Couldn't change guard (${resp.code()}).", resp.code())
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun testSiren(): ApiResult<String> = try {
        val resp = Net.api.buzzerTest()
        val b = resp.body()
        if (resp.isSuccessful && b?.ok == true) ApiResult.Ok(b.message ?: "Test beep sent.")
        else ApiResult.Err(b?.error ?: "Buzzers not connected.", resp.code())
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun alerts(): ApiResult<AlertsResp> = call { Net.api.alerts() }

    suspend fun analytics(): ApiResult<AnalyticsResp> = call { Net.api.analytics() }

    suspend fun storage(): ApiResult<Map<String, Map<String, Map<String, List<StorageEvent>>>>> =
        call { Net.api.storage() }

    suspend fun scanSensors(): ApiResult<SensorScanResp> = try {
        val resp = Net.api.sensorsScan()
        val b = resp.body()
        when {
            resp.isSuccessful && b != null && b.ok -> ApiResult.Ok(b)
            b?.error != null -> ApiResult.Err(mapSensorErr(b.error), resp.code())
            else -> ApiResult.Err("Sensor scan failed (${resp.code()}).", resp.code())
        }
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun addSensors(count: Int): ApiResult<SensorAddResp> = try {
        val resp = Net.api.sensorsAdd(SensorAddReq(count))
        val b = resp.body()
        when {
            resp.isSuccessful && b?.ok == true -> ApiResult.Ok(b)
            b?.error != null -> ApiResult.Err(mapSensorErr(b.error), resp.code())
            else -> ApiResult.Err("Couldn't add sensors (${resp.code()}).", resp.code())
        }
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun getNotifEmail(): ApiResult<NotifEmailResp> = call { Net.api.notifEmailGet() }

    suspend fun setNotifEmail(email: String): ApiResult<NotifEmailResp> = try {
        val resp = Net.api.notifEmailSet(NotifEmailReq(email))
        val b = resp.body()
        if (resp.isSuccessful && b?.ok == true) ApiResult.Ok(b)
        else ApiResult.Err(b?.error ?: "Couldn't save email (${resp.code()}).", resp.code())
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun setSiren(enabled: Boolean): ApiResult<Boolean> = try {
        val resp = Net.api.buzzerMute(BuzzerReq(enabled))
        val b = resp.body()
        if (resp.isSuccessful && b?.ok == true) ApiResult.Ok(b.enabled ?: enabled)
        else ApiResult.Err(b?.error ?: "Couldn't change siren (${resp.code()}).", resp.code())
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    private fun mapSensorErr(err: String): String = when {
        err.contains("i2c_unavailable", true) ->
            "No sensor bus detected — check the sensor wiring and that the board is connected, then try again."
        // The server occasionally names the chip; keep the message beginner-friendly.
        else -> err.replace("ADS1115", "sensor board").replace("ADDR pin", "wiring")
    }

    suspend fun farmStatus(): ApiResult<FarmStatus> = call { Net.api.farmStatus() }

    suspend fun scanNow(): ApiResult<String> = try {
        val resp = Net.api.scanNow()
        val b = resp.body()
        if (resp.isSuccessful && b?.ok == true) ApiResult.Ok(b.message ?: "Scan queued.")
        else ApiResult.Err(b?.error ?: "Couldn't start scan (${resp.code()}).", resp.code())
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun logout() {
        runCatching { Net.api.logout() }
        Net.clearSession()
    }

    private suspend fun <T> call(block: suspend () -> T): ApiResult<T> = try {
        ApiResult.Ok(block())
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    private fun friendly(e: Throwable): String = when (e) {
        is UnknownHostException -> "Can't reach the server. Check the address and that the Pi is on."
        is ConnectException -> "Connection refused — is the server running on that port?"
        is SocketTimeoutException -> "The server took too long to respond."
        is HttpException -> "Server error ${e.code()}."
        else -> e.message ?: "Network error."
    }

    @Suppress("unused")
    private fun JsonObject.errorField(): String? =
        runCatching { this["error"]?.jsonPrimitive?.content }.getOrNull()
}
