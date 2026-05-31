package com.aigriculture.app.notify

import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.Context
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import com.aigriculture.app.R

/**
 * Posts the farm's phone notifications (security threats, scan results, irrigation
 * events) on a single high-importance channel. Safe to call from any thread; a
 * no-op if the user denied POST_NOTIFICATIONS on Android 13+.
 */
object NotificationHelper {
    const val CHANNEL_ALERTS = "aigri_alerts"

    // Distinct ids so a burst of events stacks instead of replacing each other.
    @Volatile private var nextId = 2000

    fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val mgr = context.getSystemService(NotificationManager::class.java) ?: return
            if (mgr.getNotificationChannel(CHANNEL_ALERTS) == null) {
                val channel = NotificationChannel(
                    CHANNEL_ALERTS,
                    "Farm alerts",
                    NotificationManager.IMPORTANCE_HIGH,
                ).apply {
                    description = "Security threats, plant-health scans, and irrigation events"
                    enableVibration(true)
                }
                mgr.createNotificationChannel(channel)
            }
        }
    }

    fun notify(context: Context, title: String, body: String) {
        ensureChannel(context)
        val manager = NotificationManagerCompat.from(context)
        if (!manager.areNotificationsEnabled()) return
        val notification = NotificationCompat.Builder(context, CHANNEL_ALERTS)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .build()
        try {
            manager.notify(nextId++, notification)
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS not granted (Android 13+) — ignore silently.
        }
    }
}
