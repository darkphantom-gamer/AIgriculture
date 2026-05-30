package com.aigriculture.app.data.net

import android.graphics.Bitmap
import android.graphics.BitmapFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.Request
import java.io.BufferedInputStream
import java.io.ByteArrayOutputStream
import java.io.IOException

/**
 * Decodes an `multipart/x-mixed-replace` MJPEG stream (e.g. /stream, /farm_stream).
 * The server sends each frame without a Content-Length, so we scan the byte stream
 * for JPEG start (FFD8) / end (FFD9) markers and decode each complete frame.
 */
class MjpegStream(private val url: String) {

    fun frames(): Flow<Bitmap> = callbackFlow {
        val request = Request.Builder().url(url).build()
        val call = Net.client.newCall(request)
        val job = launch(Dispatchers.IO) {
            try {
                call.execute().use { resp ->
                    if (!resp.isSuccessful) {
                        close(IOException("HTTP ${resp.code}"))
                        return@use
                    }
                    val body = resp.body ?: run { close(IOException("empty stream")); return@use }
                    val src = BufferedInputStream(body.byteStream(), 1 shl 16)
                    val frame = ByteArrayOutputStream(1 shl 16)
                    var inFrame = false
                    var prev = -1
                    while (isActive) {
                        val cur = src.read()
                        if (cur == -1) break
                        if (!inFrame) {
                            if (prev == 0xFF && cur == 0xD8) {
                                inFrame = true
                                frame.reset(); frame.write(0xFF); frame.write(0xD8)
                            }
                        } else {
                            frame.write(cur)
                            if (prev == 0xFF && cur == 0xD9) {
                                val bytes = frame.toByteArray()
                                inFrame = false
                                BitmapFactory.decodeByteArray(bytes, 0, bytes.size)?.let { trySend(it) }
                            }
                        }
                        prev = cur
                    }
                }
            } catch (e: Exception) {
                if (isActive) close(e) else close()
            }
        }
        awaitClose { call.cancel(); job.cancel() }
    }
}
