package com.aigriculture.app.notify

import android.Manifest
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.content.ContentResolver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.media.AudioAttributes
import android.media.MediaPlayer
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.aigriculture.app.R

/**
 * Posts the farm's phone notifications. Security threats get their own channel
 * with the bundled siren sound; routine farm events use a normal high-importance
 * channel. Safe to call from any thread; a no-op if the user denied
 * POST_NOTIFICATIONS on Android 13+.
 */
object NotificationHelper {
    const val CHANNEL_EVENTS = "aigri_events_v3"
    const val CHANNEL_THREATS = "aigri_threats_v3"

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
                val channel = NotificationChannel(
                    CHANNEL_THREATS,
                    "Security threats",
                    NotificationManager.IMPORTANCE_HIGH,
                ).apply {
                    description = "Security camera threat alerts with siren sound"
                    enableVibration(true)
                    setSound(threatSoundUri(context), threatAudioAttributes(AudioAttributes.USAGE_ALARM))
                }
                mgr.createNotificationChannel(channel)
            }
        }
    }

    fun canPostNotifications(context: Context): Boolean {
        val managerAllowed = NotificationManagerCompat.from(context).areNotificationsEnabled()
        val runtimeAllowed = Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU ||
            ContextCompat.checkSelfPermission(
                context,
                Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
        return managerAllowed && runtimeAllowed
    }

    fun openNotificationSettings(context: Context) {
        val app = context.applicationContext
        val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Intent(Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                .putExtra(Settings.EXTRA_APP_PACKAGE, app.packageName)
        } else {
            Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                .setData(Uri.parse("package:${app.packageName}"))
        }
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        try {
            app.startActivity(intent)
        } catch (_: Exception) {
            app.startActivity(
                Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS)
                    .setData(Uri.parse("package:${app.packageName}"))
                    .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
            )
        }
    }

    fun notify(
        context: Context,
        title: String,
        body: String,
        threat: Boolean = false,
        picture: Bitmap? = null,
    ): Boolean {
        ensureChannel(context)
        if (!canPostNotifications(context)) return false
        val manager = NotificationManagerCompat.from(context)
        val builder = NotificationCompat.Builder(
            context,
            if (threat) CHANNEL_THREATS else CHANNEL_EVENTS,
        )
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setPriority(if (threat) NotificationCompat.PRIORITY_MAX else NotificationCompat.PRIORITY_HIGH)
            .setCategory(if (threat) NotificationCompat.CATEGORY_ALARM else NotificationCompat.CATEGORY_STATUS)
            .setAutoCancel(true)
            .setOnlyAlertOnce(false)
            .setSilent(false)
            .apply {
                if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) {
                    if (threat) setSound(threatSoundUri(context))
                    else setDefaults(Notification.DEFAULT_SOUND or Notification.DEFAULT_VIBRATE)
                }
            }
        if (picture != null) {
            builder
                .setLargeIcon(picture)
                .setStyle(
                    NotificationCompat.BigPictureStyle()
                        .bigPicture(picture)
                        .bigLargeIcon(null as Bitmap?)
                        .setSummaryText(body),
                )
        } else {
            builder.setStyle(NotificationCompat.BigTextStyle().bigText(body))
        }
        try {
            manager.notify(nextId++, builder.build())
            return true
        } catch (_: SecurityException) {
            // POST_NOTIFICATIONS not granted (Android 13+) — ignore silently.
            return false
        }
    }

    fun notifyThreat(context: Context, title: String, body: String, picture: Bitmap? = null) {
        playThreatSound(context)
        notify(context, title, body, threat = true, picture = picture)
    }

    private fun threatSoundUri(context: Context): Uri =
        Uri.parse("${ContentResolver.SCHEME_ANDROID_RESOURCE}://${context.packageName}/${R.raw.threat}")

    private fun threatAudioAttributes(usage: Int): AudioAttributes =
        AudioAttributes.Builder()
            .setUsage(usage)
            .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
            .build()

    private fun playThreatSound(context: Context) {
        try {
            MediaPlayer.create(
                context.applicationContext,
                R.raw.threat,
                threatAudioAttributes(AudioAttributes.USAGE_ALARM),
                0,
            )?.apply {
                setOnCompletionListener { mp -> mp.release() }
                setOnErrorListener { mp, _, _ -> mp.release(); true }
                start()
            }
        } catch (_: Exception) {
            // A notification still posts even if the device refuses local playback.
        }
    }
}
