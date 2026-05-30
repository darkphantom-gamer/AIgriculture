package com.aigriculture.app.ui.storage

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import com.aigriculture.app.ui.common.AigriCard
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.common.SectionLabel
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriBlue
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriDanger
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOk
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText

@Composable
fun StorageScreen(vm: StorageViewModel = viewModel()) {
    val ui by vm.ui.collectAsState()
    var viewerUrl by remember { mutableStateOf<String?>(null) }

    Column(modifier = Modifier.fillMaxSize().background(AigriBg)) {
        Row(
            modifier = Modifier.fillMaxWidth().background(AigriSidebar)
                .padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Storage", color = AigriText, fontWeight = FontWeight.W700, fontSize = 16.sp)
            Spacer(Modifier.weight(1f))
            IconButton(onClick = vm::load) {
                Icon(Icons.Filled.Refresh, contentDescription = "Refresh", tint = AigriMuted)
            }
        }

        when {
            ui.loading && ui.events.isEmpty() -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                CircularProgressIndicator(color = AigriAccent)
            }
            ui.error != null && ui.events.isEmpty() -> Column(
                modifier = Modifier.fillMaxSize().padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(ui.error!!, color = AigriMuted)
                Spacer(Modifier.height(16.dp))
                PrimaryButton("Retry", vm::load)
            }
            else -> {
                val security = ui.events.count { it.type.contains("person", true) || it.type == "security" }
                val disease = ui.events.count { it.type.contains("disease", true) }
                val harvest = ui.events.count { it.type.contains("ripeness", true) || it.type.contains("harvest", true) }
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item {
                        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Tile("Security", security, AigriBlue, Modifier.weight(1f))
                            Tile("Plant health", disease, AigriDanger, Modifier.weight(1f))
                            Tile("Harvest", harvest, AigriOk, Modifier.weight(1f))
                        }
                    }
                    item { SectionLabel("Stored events") }
                    if (ui.events.isEmpty()) {
                        item {
                            AigriCard(Modifier.fillMaxWidth()) {
                                Text("No stored events yet.", color = AigriMuted, fontSize = 13.sp)
                            }
                        }
                    } else {
                        items(ui.events) { ev -> EventCard(ev) { url -> viewerUrl = url } }
                    }
                }
            }
        }
    }

    viewerUrl?.let { url ->
        Dialog(
            onDismissRequest = { viewerUrl = null },
            properties = DialogProperties(usePlatformDefaultWidth = false),
        ) {
            Box(
                modifier = Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.95f))
                    .clickable { viewerUrl = null },
                contentAlignment = Alignment.Center,
            ) {
                AsyncImage(model = url, contentDescription = "Snapshot", modifier = Modifier.fillMaxWidth(), contentScale = ContentScale.Fit)
            }
        }
    }
}

@Composable
private fun Tile(label: String, value: Int, accent: Color, modifier: Modifier = Modifier) {
    AigriCard(modifier) {
        Text("$value", color = accent, fontWeight = FontWeight.W800, fontSize = 24.sp)
        Spacer(Modifier.height(2.dp))
        Text(label.uppercase(), color = AigriMuted, fontSize = 9.sp, fontWeight = FontWeight.W600)
    }
}

@Composable
private fun EventCard(ev: StorageEventRow, onImageClick: (String) -> Unit) {
    val danger = ev.type.contains("disease", true) || ev.type.equals("person", true) || ev.type == "security"
    val img = ev.firstImage
    AigriCard(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (img != null) {
                AsyncImage(
                    model = img,
                    contentDescription = "Snapshot",
                    modifier = Modifier.size(46.dp).clip(RoundedCornerShape(8.dp)).clickable { onImageClick(img) },
                    contentScale = ContentScale.Crop,
                )
                Spacer(Modifier.width(10.dp))
            } else {
                Box(Modifier.size(8.dp).background(if (danger) AigriDanger else AigriOk, CircleShape))
                Spacer(Modifier.width(10.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(
                    ev.label.ifBlank { ev.type }.replaceFirstChar { it.uppercase() },
                    color = AigriText, fontWeight = FontWeight.W600, fontSize = 13.sp,
                )
                Text("${ev.date}  ·  ${ev.time}", color = AigriMuted, fontSize = 11.sp)
            }
            if (ev.images > 0) {
                Text("${ev.images} 📷", color = AigriMuted, fontSize = 11.sp)
            }
        }
    }
}
