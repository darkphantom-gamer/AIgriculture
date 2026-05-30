package com.aigriculture.app.data

import android.content.Context

/** Tiny store for the server address the user entered on the Connect screen. */
class ServerPrefs(context: Context) {
    private val p = context.applicationContext
        .getSharedPreferences("aigri_server", Context.MODE_PRIVATE)

    var baseUrl: String?
        get() = p.getString("base_url", null)
        set(v) { p.edit().putString("base_url", v).apply() }

    fun clear() { p.edit().remove("base_url").apply() }
}
