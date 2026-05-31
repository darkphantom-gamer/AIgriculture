package com.aigriculture.app.ui.storage

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import com.aigriculture.app.data.net.Net
import com.aigriculture.app.data.net.StorageEvent
import com.aigriculture.app.ui.common.AigriCard
import com.aigriculture.app.ui.common.Pill
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.common.StatTile
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriBlue
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriCard as CardBg
import com.aigriculture.app.ui.theme.AigriDanger
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOk
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.AigriWarn
import com.aigriculture.app.ui.theme.MonoFontFamily

@Composable
fun StorageScreen(vm: StorageViewModel = viewModel()) {
    val ui by vm.ui.collectAsState()
    var viewerUrl by remember { mutableStateOf<String?>(null) }
    val expanded = remember { mutableStateMapOf<String, Boolean>() }

    // On first load, open the newest Year > Month > Day so recent events show.
    LaunchedEffect(ui.years) {
        if (ui.years.isNotEmpty() && expanded.isEmpty()) {
            val y = ui.years.first()
            expanded["y:${y.year}"] = true
            y.months.firstOrNull()?.let { m ->
                expanded["m:${y.year}/${m.month}"] = true
                m.days.firstOrNull()?.let { d ->
                    expanded["d:${y.year}/${m.month}/${d.day}"] = true
                }
            }
        }
    }

    Column(modifier = Modifier.fillMaxSize().background(AigriBg)) {
        Row(
            modifier = Modifier.fillMaxWidth().background(AigriSidebar)
                .padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Event Storage", color = AigriText, fontWeight = FontWeight.W700, fontSize = 16.sp)
            Spacer(Modifier.weight(1f))
            if (ui.total > 0) Pill("${ui.total} events", fg = AigriMuted)
            IconButton(onClick = vm::load) {
                Icon(Icons.Filled.Refresh, contentDescription = "Refresh", tint = AigriMuted)
            }
        }

        when {
            ui.loading && ui.years.isEmpty() -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                CircularProgressIndicator(color = AigriAccent)
            }
            ui.error != null && ui.years.isEmpty() -> Column(
                modifier = Modifier.fillMaxSize().padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(ui.error!!, color = AigriMuted)
                Spacer(Modifier.height(16.dp))
                PrimaryButton("Retry", vm::load)
            }
            else -> LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        StatTile("${ui.security}", "Security", Modifier.weight(1f), AigriBlue)
                        StatTile("${ui.disease}", "Plant health", Modifier.weight(1f), AigriDanger)
                        StatTile("${ui.harvest}", "Harvest", Modifier.weight(1f), AigriOk)
                    }
                }
                item {
                    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 4.dp)) {
                        Text("/Storage_Data", color = AigriMuted, fontSize = 12.sp, fontFamily = MonoFontFamily)
                    }
                }

                if (ui.years.isEmpty()) {
                    item {
                        AigriCard(Modifier.fillMaxWidth()) {
                            Text("No stored events yet.", color = AigriMuted, fontSize = 13.sp)
                        }
                    }
                }

                // Year > Month > Day > Event, emitted by expansion state.
                ui.years.forEach { yr ->
                    val yKey = "y:${yr.year}"
                    item(key = yKey) {
                        FolderNode(yr.year, yr.count, 0, expanded[yKey] == true, AigriAccent) {
                            expanded[yKey] = !(expanded[yKey] ?: false)
                        }
                    }
                    if (expanded[yKey] == true) {
                        yr.months.forEach { mo ->
                            val mKey = "m:${yr.year}/${mo.month}"
                            item(key = mKey) {
                                FolderNode(monthName(mo.month), mo.count, 1, expanded[mKey] == true, AigriAccent) {
                                    expanded[mKey] = !(expanded[mKey] ?: false)
                                }
                            }
                            if (expanded[mKey] == true) {
                                mo.days.forEach { day ->
                                    val dKey = "d:${yr.year}/${mo.month}/${day.day}"
                                    item(key = dKey) {
                                        FolderNode("${day.day} ${monthName(mo.month)}", day.events.size, 2, expanded[dKey] == true, AigriWarn) {
                                            expanded[dKey] = !(expanded[dKey] ?: false)
                                        }
                                    }
                                    if (expanded[dKey] == true) {
                                        day.events.forEach { ev ->
                                            item(key = "$dKey/${ev.time}") {
                                                EventNode(yr.year, mo.month, day.day, ev) { url -> viewerUrl = url }
                                            }
                                        }
                                    }
                                }
                            }
                        }
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
private fun FolderNode(
    label: String,
    count: Int,
    indent: Int,
    expanded: Boolean,
    accent: Color,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = (indent * 16).dp)
            .clip(RoundedCornerShape(10.dp))
            .background(CardBg)
            .border(1.dp, AigriBorder, RoundedCornerShape(10.dp))
            .clickable(onClick = onClick)
            .padding(horizontal = 12.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            Icons.Filled.KeyboardArrowDown,
            contentDescription = if (expanded) "Collapse" else "Expand",
            tint = AigriMuted,
            modifier = Modifier.size(18.dp).rotate(if (expanded) 0f else -90f),
        )
        Spacer(Modifier.width(6.dp))
        Icon(Icons.Filled.Folder, contentDescription = null, tint = accent, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(10.dp))
        Text(label, color = AigriText, fontWeight = FontWeight.W700, fontSize = 14.sp, modifier = Modifier.weight(1f))
        Text(
            if (count == 1) "1 event" else "$count events",
            color = AigriMuted, fontSize = 11.sp,
        )
    }
}

@Composable
private fun EventNode(
    year: String,
    month: String,
    day: String,
    ev: StorageEvent,
    onImage: (String) -> Unit,
) {
    val type = (ev.meta.event_type ?: ev.meta.label ?: "event")
    val isDisease = type.contains("disease", true) || type.contains("plant", true) ||
        type.contains("leaf", true) || type.contains("fruit", true)
    val isHarvest = type.contains("ripe", true) || type.contains("harvest", true)
    val dot = when {
        isHarvest -> AigriOk
        isDisease -> AigriDanger
        else -> AigriBlue
    }
    val title = ev.meta.label ?: ev.meta.message ?: type
    val first = ev.images.firstOrNull()
    val imgUrl = if (first != null) Net.absUrl("storage_img/$year/$month/$day/${ev.time}/$first") else null

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(start = 48.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(AigriBg)
            .border(1.dp, AigriBorder, RoundedCornerShape(10.dp))
            .padding(10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (imgUrl != null) {
            AsyncImage(
                model = imgUrl,
                contentDescription = "Snapshot",
                modifier = Modifier.size(48.dp).clip(RoundedCornerShape(8.dp)).clickable { onImage(imgUrl) },
                contentScale = ContentScale.Crop,
            )
            Spacer(Modifier.width(10.dp))
        } else {
            Box(Modifier.size(8.dp).background(dot, CircleShape))
            Spacer(Modifier.width(12.dp))
        }
        Column(Modifier.weight(1f)) {
            Text(ev.time, color = AigriAccent, fontSize = 12.sp, fontWeight = FontWeight.W700, fontFamily = MonoFontFamily)
            Spacer(Modifier.height(2.dp))
            Text(
                title.replaceFirstChar { it.uppercase() },
                color = AigriText, fontWeight = FontWeight.W600, fontSize = 13.sp, maxLines = 2,
            )
            ev.meta.message?.takeIf { it.isNotBlank() && it != title }?.let { msg ->
                Spacer(Modifier.height(2.dp))
                Text(msg, color = AigriMuted, fontSize = 11.sp, maxLines = 2)
            }
        }
        if (ev.images.isNotEmpty()) {
            Spacer(Modifier.width(8.dp))
            Text("${ev.images.size} 📷", color = AigriMuted, fontSize = 11.sp)
        }
    }
}

private fun monthName(m: String): String {
    val n = m.toIntOrNull() ?: return m
    val names = listOf(
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    )
    return if (n in 1..12) "${names[n - 1]} ($m)" else m
}
