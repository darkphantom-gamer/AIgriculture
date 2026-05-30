package com.aigriculture.app.data.net

import android.content.Context
import com.aigriculture.app.data.ServerPrefs
import kotlinx.serialization.json.Json
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Central networking. One OkHttp client (with the persistent cookie jar) is reused
 * for every server; the Retrofit instance is rebuilt whenever the base URL changes.
 */
object Net {
    val json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        isLenient = true
        explicitNulls = false
    }

    lateinit var client: OkHttpClient
        private set
    lateinit var cookieJar: AppCookieJar
        private set
    private lateinit var prefs: ServerPrefs

    @Volatile var baseUrl: String? = null
        private set
    @Volatile private var apiRef: ApiService? = null

    fun init(context: Context) {
        cookieJar = AppCookieJar(context)
        prefs = ServerPrefs(context)
        client = OkHttpClient.Builder()
            .cookieJar(cookieJar)
            .connectTimeout(15, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .pingInterval(25, TimeUnit.SECONDS) // keep FLORA / state sockets alive
            .retryOnConnectionFailure(true)
            .build()
        prefs.baseUrl?.let { setBaseUrl(it, persist = false) }
    }

    /** Accepts "ip:port", "http://host:port", "https://host" → normalized base. */
    fun normalize(input: String): String? {
        var s = input.trim()
        if (s.isEmpty()) return null
        if (!s.startsWith("http://", true) && !s.startsWith("https://", true)) s = "http://$s"
        val url = s.toHttpUrlOrNull() ?: return null
        return url.toString().trimEnd('/')
    }

    fun setBaseUrl(input: String, persist: Boolean = true): Boolean {
        val norm = normalize(input) ?: return false
        baseUrl = norm
        if (persist) prefs.baseUrl = norm
        apiRef = Retrofit.Builder()
            .baseUrl("$norm/")
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()
            .create(ApiService::class.java)
        return true
    }

    val api: ApiService
        get() = apiRef ?: error("Server not configured")

    fun hasBaseUrl(): Boolean = baseUrl != null

    fun wsUrl(path: String): String {
        val b = baseUrl ?: return ""
        val ws = b.replaceFirst("https://", "wss://").replaceFirst("http://", "ws://")
        return "$ws/${path.trimStart('/')}"
    }

    fun absUrl(path: String): String {
        val b = baseUrl ?: return path
        return "$b/${path.trimStart('/')}"
    }

    /** Forget the session for the current host (after logout). */
    fun clearSession() {
        baseUrl?.toHttpUrlOrNull()?.host?.let { cookieJar.clear(it) }
    }

    fun forgetServer() {
        clearSession()
        baseUrl = null
        apiRef = null
        prefs.clear()
    }
}
