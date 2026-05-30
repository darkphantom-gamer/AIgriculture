package com.aigriculture.app.ui.shell

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Spa
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aigriculture.app.ui.flora.FloraScreen
import com.aigriculture.app.ui.settings.SettingsScreen
import com.aigriculture.app.ui.status.StatusScreen
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOnAccent
import com.aigriculture.app.ui.theme.AigriSidebar

private enum class Tab(val label: String, val icon: ImageVector) {
    FLORA("FLORA", Icons.Filled.AutoAwesome),
    STATUS("Status", Icons.Filled.Spa),
    SETTINGS("Settings", Icons.Filled.Settings),
}

@Composable
fun AppShell(onLoggedOut: () -> Unit) {
    var index by rememberSaveable { mutableIntStateOf(0) }
    val tabs = Tab.values()

    Scaffold(
        containerColor = AigriBg,
        bottomBar = {
            NavigationBar(containerColor = AigriSidebar, tonalElevation = 0.dp) {
                tabs.forEachIndexed { i, t ->
                    NavigationBarItem(
                        selected = i == index,
                        onClick = { index = i },
                        icon = { Icon(t.icon, contentDescription = t.label) },
                        label = { Text(t.label, fontSize = 11.sp) },
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
                Tab.SETTINGS -> SettingsScreen(onLoggedOut = onLoggedOut)
            }
        }
    }
}
