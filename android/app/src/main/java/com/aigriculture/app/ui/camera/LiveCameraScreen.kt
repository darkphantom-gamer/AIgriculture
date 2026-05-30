package com.aigriculture.app.ui.camera

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aigriculture.app.ui.common.SegmentedSelector
import com.aigriculture.app.ui.monitor.FarmMonitorScreen
import com.aigriculture.app.ui.security.SecurityScreen
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText

/** One "Live Camera" tab that hosts both feeds, mirroring the web Cameras page. */
@Composable
fun LiveCameraScreen() {
    var tab by rememberSaveable { mutableIntStateOf(0) }
    Column(Modifier.fillMaxSize().background(AigriBg)) {
        Column(Modifier.fillMaxWidth().background(AigriSidebar).padding(16.dp)) {
            Text("Live Camera", color = AigriText, fontWeight = FontWeight.W700, fontSize = 16.sp)
        }
        SegmentedSelector(
            options = listOf("Security", "Farm Monitor"),
            selected = tab,
            onSelect = { tab = it },
            modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 12.dp),
        )
        Box(Modifier.weight(1f).fillMaxWidth()) {
            when (tab) {
                0 -> SecurityScreen(showHeader = false)
                else -> FarmMonitorScreen(showHeader = false)
            }
        }
    }
}
