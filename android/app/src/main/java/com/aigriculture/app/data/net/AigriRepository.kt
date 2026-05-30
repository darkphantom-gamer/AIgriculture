package com.aigriculture.app.data.net

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

    suspend fun floraChat(content: String, mode: String): ApiResult<String> = try {
        val resp = Net.api.floraChat(FloraChatReq(content, mode))
        val b = resp.body()
        if (resp.isSuccessful && b?.ok == true) ApiResult.Ok(b.response)
        else ApiResult.Err(b?.error ?: "FLORA request failed (${resp.code()}).", resp.code())
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
