package com.aigriculture.app.notify

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ContentResolver
import android.content.Context
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.aigriculture.app.R

/**
 * Posts the farm's phone notifications. Security threats get their own channel
 * with the bundled siren sound; routine farm events use a normal high-importance
 * channel. Safe to call from any thread; a no-op if the user denied
 * POST_NOTIFICATIONS on Android 13+.
 */
object NotificationHelper {
    const val CHANNEL_EVENTS = "aigri_events_v2"
    const val CHANNEL_THREATS = "aigri_threats_v2"

    // Distinct ids so a burst of events stacks instead of replacing each other.
    @Volatile private var nextId = 2000

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = context.getSystemService(NotificationManager::class.java) ?: return
            if (mgr.getNotificationChannel(CHANNEL_EVENTS) == null) {
                val channel = NotificationChannel(
                    CHANNEL_EVENTS,
                    "Farm events",
                    NotificationManager.IMPORTANCE_HIGH,
                ).apply {
                    description = "Plant moisture, irrigation, FarmMonitor, FLORA, and camera events"
                    enableVibration(true)
                }
                mgr.createNotificationChannel(channel)
            }
            if (mgr.getNotificationChannel(CHANNEL_THREATS) == null) {
                val attrs = AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_NOTIFICATION_EVENT)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
                val channel = NotificationChannel(
                    CHANNEL_THREATS,
                    "Security threats",
                    NotificationManager.IMPORTANCE_HIGH,
                ).apply {
                    description = "Security camera threat alerts with siren sound"
                    enableVibration(true)
                    setSound(threatSoundUri(context), attrs)
                }
                mgr.createNotificationChannel(channel)
            }
        }
    }

    fun notify(context: Context, title: String, body: String, threat: Boolean = false) {
        ensureChannel(context)
        val manager = NotificationManagerCompat.from(context)
        if (!manager.areNotificationsEnabled()) return
        val notification = NotificationCompat.Builder(
            context,
            if (threat) CHANNEL_THREATS else CHANNEL_EVENTS,
        )
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .apply {
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
                    if (threat) setSound(threatSoundUri(context))
                    else setDefaults(Notification.DEFAULT_SOUND or Notification.DEFAULT_VIBRATE)
                }
            }
            .build()
        try {
            manager.notify(nextId++, notification)
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS not granted (Android 13+) — ignore silently.
        }
    }

    fun notifyThreat(context: Context, title: String, body: String) {
        playThreatSound(context)
        notify(context, title, body, threat = true)
    }

    private fun threatSoundUri(context: Context): Uri =
        Uri.parse("${ContentResolver.SCHEME_ANDROID_RESOURCE}://${context.packageName}/${R.raw.threat}")

    private fun playThreatSound(context: Context) {
        try {
            MediaPlayer.create(context.applicationContext, R.raw.threat)?.apply {
                setOnCompletionListener { mp -> mp.release() }
                setOnErrorListener { mp, _, _ -> mp.release(); true }
                start()
            }
        } catch (_: Exception) {
            // A notification still posts even if the device refuses local playback.
        }
    }
}
