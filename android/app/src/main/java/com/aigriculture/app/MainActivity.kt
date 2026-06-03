package com.aigriculture.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.Surface
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import com.aigriculture.app.nav.AppNav
import com.aigriculture.app.notify.NotificationHelper
import com.aigriculture.app.notify.NotificationLaunchBus
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigricultureTheme

class MainActivity : ComponentActivity() {

    // Result is ignored — if the farmer declines, alerts simply don't post; the
    // rest of the app is unaffected and they can re-enable in system settings.
    private val notifPermLauncher =
        registerForActivityResult(ActivityResultContracts.RequestPermission()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        NotificationHelper.ensureChannel(this)
        NotificationLaunchBus.publish(intent)
        requestNotificationPermission()
        setContent {
            AigricultureTheme {
                Surface(modifier = Modifier.fillMaxSize(), color = AigriBg) {
                    AppNav()
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        NotificationLaunchBus.publish(intent)
    }

    /** Ask for POST_NOTIFICATIONS on first launch (Android 13+ only). */
    private fun requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            val granted = ContextCompat.checkSelfPermission(
                this, Manifest.permission.POST_NOTIFICATIONS,
            ) == PackageManager.PERMISSION_GRANTED
            if (!granted) {
                notifPermLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
    }
}
