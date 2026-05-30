package com.aigriculture.app.ui.common

import android.graphics.Bitmap
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.sp
import com.aigriculture.app.data.net.MjpegFrameCache
import com.aigriculture.app.data.net.MjpegStream
import com.aigriculture.app.data.net.Net
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriMuted
import kotlinx.coroutines.flow.catch

/**
 * Renders a live MJPEG feed (e.g. "stream", "farm_stream") by collecting decoded
 * frames from [MjpegStream]. The stream starts when this enters composition and is
 * cancelled the moment it leaves — so switching tabs stops the camera automatically.
 * The OkHttp cookie jar replays the auth cookie, so no token plumbing is needed here.
 */
@Composable
fun MjpegView(
    path: String,
    modifier: Modifier = Modifier,
    contentScale: ContentScale = ContentScale.Fit,
) {
    var bitmap by remember(path) { mutableStateOf(MjpegFrameCache.get(path)) }
    var error by remember(path) { mutableStateOf<String?>(null) }

    LaunchedEffect(path) {
        error = null
        if (Net.baseUrl == null) {
            error = "Not connected"
            return@LaunchedEffect
        }
        MjpegStream(Net.absUrl(path))
            .frames()
            .catch { e -> error = e.message ?: "Stream unavailable" }
            .collect { frame ->
                MjpegFrameCache.put(path, frame)
                bitmap = frame
                error = null
            }
    }

    Box(modifier.background(Color.Black), contentAlignment = Alignment.Center) {
        val bmp = bitmap
        when {
            bmp != null -> Image(
                bitmap = bmp.asImageBitmap(),
                contentDescription = "Live camera feed",
                modifier = Modifier.fillMaxSize(),
                contentScale = contentScale,
            )
            error != null -> Text(error!!, color = AigriMuted, fontSize = 12.sp)
            else -> CircularProgressIndicator(color = AigriAccent)
        }
    }
}
