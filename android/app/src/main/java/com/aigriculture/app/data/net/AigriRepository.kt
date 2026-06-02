package com.aigriculture.app.data.net

import android.os.Build
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.HttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import retrofit2.HttpException
import retrofit2.Response
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
        val trimmed = input.trim()
        val hadScheme = trimmed.startsWith("http://", true) || trimmed.startsWith("https://", true)
        val first = Net.normalize(input) ?: return ApiResult.Err("That doesn't look like a valid address.")
        val candidates = buildList {
            add(first)
            if (!hadScheme) {
                Net.altScheme(first)?.takeIf { it != first }?.let { add(it) }
            }
        }
        var lastError: ApiResult.Err? = null
        for (candidate in candidates) {
            when (val result = tryProbe(candidate)) {
                is ApiResult.Ok -> {
                    if (Net.setBaseUrl(result.value, persist = true)) return ApiResult.Ok(Unit)
                    return ApiResult.Err("Reached AIgriculture, but the server address was invalid.")
                }
                is ApiResult.Err -> lastError = result
            }
        }
        return lastError ?: ApiResult.Err("Couldn't reach AIgriculture at that address.")
    }

    private suspend fun tryProbe(baseUrl: String): ApiResult<String> = try {
        val api = Net.probeApi(baseUrl)
        val resp = api.mobileProbe()
        val body = resp.body()
        if (resp.isSuccessful && body?.ok == true && body.service.equals("aigriculture", true)) {
            ApiResult.Ok(canonicalBase(resp.raw().request.url))
        } else if (resp.code() == 404) {
            tryLegacyProbe(api, baseUrl)
        } else {
            ApiResult.Err("Server responded ${resp.code()} — check the address and port.", resp.code())
        }
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    private suspend fun tryLegacyProbe(api: ApiService, baseUrl: String): ApiResult<String> = try {
        val resp = api.probeLogin()
        if (!resp.isSuccessful) {
            ApiResult.Err("Server responded ${resp.code()} — check the address and port.", resp.code())
        } else {
            val body = resp.body()?.string().orEmpty()
            if (body.contains("AIgriculture", true) || body.contains("pmc_token", true) ||
                body.contains("password", true)
            ) ApiResult.Ok(canonicalBase(resp.raw().request.url))
            else ApiResult.Err("Reached a server, but it doesn't look like AIgriculture.")
        }
    } catch (_: Exception) {
        ApiResult.Err("Couldn't reach AIgriculture at $baseUrl.")
    }

    private fun canonicalBase(url: HttpUrl): String =
        url.newBuilder()
            .encodedPath("/")
            .query(null)
            .fragment(null)
            .build()
            .toString()
            .trimEnd('/')

    suspend fun login(username: String, password: String): ApiResult<String> = try {
        val device = listOf(Build.MANUFACTURER, Build.MODEL)
            .filter { it.isNotBlank() }
            .joinToString(" ")
            .ifBlank { "Android" }
        val resp = Net.api.login(username, password, client = "android_apk", device = device)
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

    suspend fun scanStop(): ApiResult<String> = try {
        val resp = Net.api.scanStop()
        val b = resp.body()
        if (resp.isSuccessful && b?.ok == true) ApiResult.Ok(b.message ?: "Stopping scan.")
        else ApiResult.Err(b?.error ?: "Couldn't stop scan (${resp.code()}).", resp.code())
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    suspend fun uploadAvatar(bytes: ByteArray, mime: String): ApiResult<String> = try {
        // Send the picked image with its real MIME so the server's allow-list check is
        // honest; the part filename's extension just mirrors it. The server stores
        // avatars as content-hashed runtime files so web and app caches never fight.
        val mediaType = mime.toMediaTypeOrNull() ?: "image/jpeg".toMediaType()
        val ext = when {
            mime.contains("png", true) -> "png"
            mime.contains("webp", true) -> "webp"
            mime.contains("gif", true) -> "gif"
            else -> "jpg"
        }
        val body = bytes.toRequestBody(mediaType)
        val part = MultipartBody.Part.createFormData("file", "avatar.$ext", body)
        val resp = Net.api.uploadAvatar(part)
        val b = resp.body()
        when {
            resp.isSuccessful && b?.ok == true -> ApiResult.Ok(b.avatar_url ?: "")
            else -> ApiResult.Err(
                parseUploadError(resp) ?: b?.error ?: "Upload failed (${resp.code()}).",
                resp.code(),
            )
        }
    } catch (e: Exception) {
        ApiResult.Err(friendly(e))
    }

    /** Pull the server's friendly message out of a non-2xx avatar-upload error body. */
    private fun parseUploadError(resp: Response<UploadAvatarResp>): String? = try {
        resp.errorBody()?.string()?.takeIf { it.isNotBlank() }?.let {
            Net.json.decodeFromString(UploadAvatarResp.serializer(), it).error
        }
    } catch (_: Exception) {
        null
    }

    suspend fun logout() {
        runCatching { Net.api.logout() }
        Net.clearSession()
    }

    private suspend fun <T> call(block: suspend () -> T): ApiResult<T> = try {
        ApiResult.Ok(block())
    } catch (e: Exception) {
        ApiResult.Err(friendly(e), if (e is HttpException) e.code() else 0)
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
