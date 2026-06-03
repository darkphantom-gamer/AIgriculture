package com.aigriculture.app.notify

import android.content.Intent
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.util.concurrent.atomic.AtomicLong

data class NotificationLaunch(
    val id: Long,
    val target: String,
    val title: String,
    val body: String,
)

object NotificationRoute {
    const val EXTRA_TARGET = "com.aigriculture.app.notification.TARGET"
    const val EXTRA_TITLE = "com.aigriculture.app.notification.TITLE"
    const val EXTRA_BODY = "com.aigriculture.app.notification.BODY"

    const val STATUS = "status"
    const val SECURITY = "security"
    const val FARM_MONITOR = "farm_monitor"
    const val FLORA = "flora"
}

object NotificationLaunchBus {
    private val seq = AtomicLong(0)
    private val _launch = MutableStateFlow<NotificationLaunch?>(null)
    val launch: StateFlow<NotificationLaunch?> = _launch

    fun publish(intent: Intent?) {
        val target = intent?.getStringExtra(NotificationRoute.EXTRA_TARGET) ?: return
        _launch.value = NotificationLaunch(
            id = seq.incrementAndGet(),
            target = target,
            title = intent.getStringExtra(NotificationRoute.EXTRA_TITLE).orEmpty(),
            body = intent.getStringExtra(NotificationRoute.EXTRA_BODY).orEmpty(),
        )
    }

    fun clear(id: Long) {
        if (_launch.value?.id == id) {
            _launch.value = null
        }
    }
}
