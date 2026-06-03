package com.aigriculture.app.ui.shell

import android.Manifest
import android.content.pm.PackageManager
import android.os.Build
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.BarChart
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Spa
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Videocam
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import com.aigriculture.app.notify.AlertMonitor
import com.aigriculture.app.notify.NotificationLaunchBus
import com.aigriculture.app.notify.NotificationRoute
import com.aigriculture.app.ui.analytics.AnalyticsScreen
import com.aigriculture.app.ui.camera.LiveCameraScreen
import com.aigriculture.app.ui.flora.FloraScreen
import com.aigriculture.app.ui.settings.SettingsScreen
import com.aigriculture.app.ui.status.StatusScreen
import com.aigriculture.app.ui.storage.StorageScreen
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOnAccent
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText
import kotlinx.coroutines.delay

private enum class Tab(val label: String, val icon: ImageVector) {
    FLORA("FLORA", Icons.Filled.AutoAwesome),
    STATUS("Status", Icons.Filled.Spa),
    CAMERA("Camera", Icons.Filled.Videocam),
    STORAGE("Storage", Icons.Filled.Storage),
    ANALYTICS("Analytics", Icons.Filled.BarChart),
    SETTINGS("Settings", Icons.Filled.Settings),
}

@Composable
fun AppShell(onLoggedOut: () -> Unit) {
    var index by rememberSaveable { mutableIntStateOf(0) }
    var cameraInitialTab by rememberSaveable { mutableIntStateOf(0) }
    var cameraTabSignal by rememberSaveable { mutableStateOf(0L) }
    var notificationBanner by rememberSaveable { mutableStateOf<String?>(null) }
    val tabs = Tab.values()
    val context = LocalContext.current
    val notificationLaunch by NotificationLaunchBus.launch.collectAsState()

    NotificationPermissionGate()

    // Watch the farm server for the whole logged-in session and raise phone
    // notifications for threats / scans / irrigation. Stops on logout (dispose).
    DisposableEffect(Unit) {
        AlertMonitor.start(context)
        onDispose { AlertMonitor.stop() }
    }

    LaunchedEffect(notificationLaunch?.id) {
        val launch = notificationLaunch ?: return@LaunchedEffect
        when (launch.target) {
            NotificationRoute.SECURITY -> {
                cameraInitialTab = 0
                cameraTabSignal = launch.id
                index = tabs.indexOf(Tab.CAMERA)
            }
            NotificationRoute.FARM_MONITOR -> {
                cameraInitialTab = 1
                cameraTabSignal = launch.id
                index = tabs.indexOf(Tab.CAMERA)
            }
            NotificationRoute.FLORA -> index = tabs.indexOf(Tab.FLORA)
            else -> index = tabs.indexOf(Tab.STATUS)
        }
        notificationBanner = listOf(launch.title, launch.body)
            .filter { it.isNotBlank() }
            .joinToString("\n")
            .ifBlank { "Opening farm alert" }
        NotificationLaunchBus.clear(launch.id)
    }

    LaunchedEffect(notificationBanner) {
        if (notificationBanner != null) {
            delay(4_500)
            notificationBanner = null
        }
    }

    Scaffold(
        containerColor = AigriBg,
        bottomBar = {
            NavigationBar(containerColor = AigriSidebar, tonalElevation = 0.dp) {
                tabs.forEachIndexed { i, t ->
                    NavigationBarItem(
                        selected = i == index,
                        onClick = { index = i },
                        icon = { Icon(t.icon, contentDescription = t.label) },
                        label = { Text(t.label, fontSize = 9.sp, maxLines = 1) },
                        colors = NavigationBarItemDefaults.colors(
                            selectedIconColor = AigriOnAccent,
                            indicatorColor = AigriAccent,
                            selectedTextColor = AigriAccent,
                            unselectedIconColor = AigriMuted,
                            unselectedTextColor = AigriMuted,
                        ),
                    )
                }
            }
        },
    ) { padding ->
        Box(modifier = Modifier.fillMaxSize().padding(padding)) {
            when (tabs[index]) {
                Tab.FLORA -> FloraScreen()
                Tab.STATUS -> StatusScreen()
                Tab.CAMERA -> LiveCameraScreen(initialTab = cameraInitialTab, tabSignal = cameraTabSignal)
                Tab.STORAGE -> StorageScreen()
                Tab.ANALYTICS -> AnalyticsScreen()
                Tab.SETTINGS -> SettingsScreen(onLoggedOut = onLoggedOut)
            }
            notificationBanner?.let { text ->
                Box(
                    modifier = Modifier
                        .align(Alignment.TopCenter)
                        .padding(12.dp)
                        .fillMaxWidth()
                        .background(AigriSidebar, RoundedCornerShape(14.dp))
                        .padding(12.dp),
                ) {
                    Text(text, color = AigriText, fontSize = 12.sp)
                }
            }
        }
    }
}

@Composable
private fun NotificationPermissionGate() {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.TIRAMISU) return
    val context = LocalContext.current
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }

    LaunchedEffect(Unit) {
        val granted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.POST_NOTIFICATIONS,
        ) == PackageManager.PERMISSION_GRANTED
        if (!granted) {
            launcher.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
    }
}
