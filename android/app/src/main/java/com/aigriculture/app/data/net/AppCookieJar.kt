package com.aigriculture.app.data.net

import android.content.Context
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import okhttp3.Cookie
import okhttp3.CookieJar
import okhttp3.HttpUrl
import java.util.concurrent.ConcurrentHashMap

/**
 * Persistent cookie jar. The server authenticates this native client exactly the
 * way it authenticates the browser: /auth/login returns a `pmc_token` cookie,
 * and we replay it on every REST call and the WebSocket handshake. HttpOnly and
 * SameSite are browser-only protections and do not affect an OkHttp client, so
 * no backend change is needed.
 */
class AppCookieJar(context: Context) : CookieJar {

    private val prefs = context.applicationContext
        .getSharedPreferences("aigri_cookies", Context.MODE_PRIVATE)
    private val json = Json { ignoreUnknownKeys = true }
    private val store = ConcurrentHashMap<String, MutableList<Cookie>>()

    @Serializable
    private data class C(
        val name: String, val value: String, val domain: String, val path: String,
        val expiresAt: Long, val secure: Boolean, val httpOnly: Boolean, val hostOnly: Boolean,
    )

    init { loadAll() }

    @Synchronized
    override fun saveFromResponse(url: HttpUrl, cookies: List<Cookie>) {
        if (cookies.isEmpty()) return
        val list = store.getOrPut(url.host) { mutableListOf() }
        for (c in cookies) {
            list.removeAll { it.name == c.name }
            // A cleared cookie (logout) has an expiry in the past — drop it.
            if (c.expiresAt > System.currentTimeMillis()) list.add(c)
        }
        persist(url.host)
    }

    @Synchronized
    override fun loadForRequest(url: HttpUrl): List<Cookie> {
        val now = System.currentTimeMillis()
        val list = store[url.host] ?: return emptyList()
        list.removeAll { it.expiresAt <= now }
        return list.filter { it.matches(url) }
    }

    @Synchronized
    fun clear(host: String? = null) {
        if (host == null) {
            store.clear(); prefs.edit().clear().apply()
        } else {
            store.remove(host); prefs.edit().remove("h_$host").apply()
        }
    }

    private fun persist(host: String) {
        val list = store[host] ?: return
        val data = list.map {
            C(it.name, it.value, it.domain, it.path, it.expiresAt, it.secure, it.httpOnly, it.hostOnly)
        }
        prefs.edit()
            .putString("h_$host", json.encodeToString(ListSerializer(C.serializer()), data))
            .apply()
    }

    private fun loadAll() {
        for ((k, v) in prefs.all) {
            if (!k.startsWith("h_") || v !is String) continue
            val host = k.removePrefix("h_")
            try {
                val data = json.decodeFromString(ListSerializer(C.serializer()), v)
                store[host] = data.map { c ->
                    val b = Cookie.Builder().name(c.name).value(c.value).path(c.path)
                        .expiresAt(c.expiresAt)
                    if (c.hostOnly) b.hostOnlyDomain(c.domain) else b.domain(c.domain)
                    if (c.secure) b.secure()
                    if (c.httpOnly) b.httpOnly()
                    b.build()
                }.toMutableList()
            } catch (_: Exception) { /* ignore corrupt entry */ }
        }
    }
}
