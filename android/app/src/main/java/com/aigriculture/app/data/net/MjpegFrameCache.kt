package com.aigriculture.app.data.net

import android.graphics.Bitmap

/**
 * Caches the last decoded frame per stream path. When you leave a camera tab and
 * come back, [MjpegView] seeds itself from here so the previous frame shows
 * instantly instead of a black "reconnecting" box — switching tabs feels snappy.
 */
object MjpegFrameCache {
    private val frames = HashMap<String, Bitmap>()

    fun get(path: String): Bitmap? = frames[path]

    fun put(path: String, bitmap: Bitmap) {
        frames[path] = bitmap
    }
}
