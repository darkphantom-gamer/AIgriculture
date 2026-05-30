package com.aigriculture.app.ui.analytics

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
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
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aigriculture.app.data.net.IrrEvent
import com.aigriculture.app.data.net.StorageMeta
import com.aigriculture.app.ui.common.AigriCard
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.common.SectionLabel
import com.aigriculture.app.ui.common.SegmentedSelector
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriBlue
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriDanger
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOk
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.AigriWarn
import kotlin.math.roundToInt

@Composable
fun AnalyticsScreen(vm: AnalyticsViewModel = viewModel()) {
    val ui by vm.ui.collectAsState()
    var tab by rememberSaveable { mutableIntStateOf(0) }

    Column(modifier = Modifier.fillMaxSize().background(AigriBg)) {
        Row(
            modifier = Modifier.fillMaxWidth().background(AigriSidebar)
                .padding(start = 16.dp, end = 8.dp, top = 8.dp, bottom = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Analytics", color = AigriText, fontWeight = FontWeight.W700, fontSize = 16.sp)
            Spacer(Modifier.weight(1f))
            IconButton(onClick = vm::load) {
                Icon(Icons.Filled.Refresh, contentDescription = "Refresh", tint = AigriMuted)
            }
        }
        SegmentedSelector(
            options = listOf("Moisture", "Security Farm", "Plant Health"),
            selected = tab,
            onSelect = { tab = it },
            modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 12.dp),
        )

        when {
            ui.loading && ui.data == null -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                CircularProgressIndicator(color = AigriAccent)
            }
            ui.error != null && ui.data == null -> Column(
                modifier = Modifier.fillMaxSize().padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(ui.error!!, color = AigriMuted)
                Spacer(Modifier.height(16.dp))
                PrimaryButton("Retry", vm::load)
            }
            else -> {
                val d = ui.data
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    when (tab) {
                        0 -> {
                            item { MoistureCard(d?.moisture_current ?: emptyMap()) }
                            item { IrrigationCard(d?.irr_history ?: emptyList()) }
                        }
                        1 -> {
                            item {
                                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Tile("Security events", d?.storage_summary?.get("security") ?: 0, AigriBlue, Modifier.weight(1f))
                                    Tile("Today's detections", (d?.hourly_detections?.values?.sum()) ?: 0, AigriWarn, Modifier.weight(1f))
                                }
                            }
                            item { HourlyCard(d?.hourly_detections ?: emptyMap()) }
                            item { SpeciesCard(d?.species_counts ?: emptyMap()) }
                        }
                        else -> {
                            val ss = d?.storage_summary ?: emptyMap()
                            val disease = (ss["disease"] ?: 0) + (ss["disease_and_ripeness"] ?: 0)
                            val harvest = (ss["ripeness"] ?: 0) + (ss["disease_and_ripeness"] ?: 0)
                            item {
                                Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    Tile("Health alerts", disease, AigriDanger, Modifier.weight(1f))
                                    Tile("Harvest ready", harvest, AigriOk, Modifier.weight(1f))
                                }
                            }
                            item { LatestScanCard(d?.latest_farm_event) }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun MoistureCard(moisture: Map<String, Double?>) {
    AigriCard(Modifier.fillMaxWidth()) {
        SectionLabel("Per-plant moisture")
        Spacer(Modifier.height(10.dp))
        val entries = moisture.entries.filter { it.value != null }.sortedBy { it.key }
        if (entries.isEmpty()) {
            Text("No live moisture readings.", color = AigriMuted, fontSize = 13.sp)
            return@AigriCard
        }
        entries.forEach { (plant, v) ->
            val pct = v ?: 0.0
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 4.dp)) {
                Text("Plant ${plant.uppercase()}", color = AigriText, fontSize = 12.sp, modifier = Modifier.width(90.dp))
                Box(
                    Modifier.weight(1f).height(10.dp).background(AigriBorder, RoundedCornerShape(5.dp)),
                ) {
                    Box(
                        Modifier.fillMaxHeight()
                            .fillMaxWidth((pct / 100.0).coerceIn(0.0, 1.0).toFloat())
                            .background(moistColor(pct), RoundedCornerShape(5.dp)),
                    )
                }
                Spacer(Modifier.width(8.dp))
                Text("${pct.roundToInt()}%", color = AigriText, fontWeight = FontWeight.W700, fontSize = 12.sp)
            }
        }
    }
}

@Composable
private fun LatestScanCard(latest: StorageMeta?) {
    AigriCard(Modifier.fillMaxWidth()) {
        SectionLabel("Latest plant-health scan")
        Spacer(Modifier.height(8.dp))
        Text(latest?.label ?: "No scans recorded yet.", color = AigriText, fontWeight = FontWeight.W700, fontSize = 14.sp)
        val msg = latest?.message
        if (!msg.isNullOrBlank()) {
            Spacer(Modifier.height(4.dp))
            Text(msg, color = AigriMuted, fontSize = 12.sp)
        }
    }
}

@Composable
private fun Tile(label: String, value: Int, accent: Color, modifier: Modifier = Modifier) {
    AigriCard(modifier) {
        Text("$value", color = accent, fontWeight = FontWeight.W800, fontSize = 26.sp)
        Spacer(Modifier.height(2.dp))
        Text(label.uppercase(), color = AigriMuted, fontSize = 9.sp, fontWeight = FontWeight.W600)
    }
}

@Composable
private fun SpeciesCard(species: Map<String, Int>) {
    AigriCard(Modifier.fillMaxWidth()) {
        SectionLabel("Most detected (24h)")
        Spacer(Modifier.height(10.dp))
        if (species.isEmpty()) {
            Text("No detections in the last 24 hours.", color = AigriMuted, fontSize = 13.sp)
            return@AigriCard
        }
        val max = species.values.maxOrNull()?.coerceAtLeast(1) ?: 1
        species.entries.sortedByDescending { it.value }.forEach { (label, count) ->
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 4.dp)) {
                Text(label, color = AigriText, fontSize = 12.sp, modifier = Modifier.width(120.dp))
                Box(Modifier.weight(1f).height(10.dp).background(AigriBorder, RoundedCornerShape(5.dp))) {
                    Box(
                        Modifier.fillMaxHeight().fillMaxWidth(count.toFloat() / max.toFloat())
                            .background(AigriAccent, RoundedCornerShape(5.dp)),
                    )
                }
                Spacer(Modifier.width(8.dp))
                Text("$count", color = AigriText, fontWeight = FontWeight.W700, fontSize = 12.sp)
            }
        }
    }
}

@Composable
private fun HourlyCard(hourly: Map<String, Int>) {
    AigriCard(Modifier.fillMaxWidth()) {
        SectionLabel("Detections by hour (24h)")
        Spacer(Modifier.height(12.dp))
        val counts = (0..23).map { hourly[it.toString()] ?: 0 }
        val max = counts.maxOrNull()?.coerceAtLeast(1) ?: 1
        Row(
            modifier = Modifier.fillMaxWidth().height(64.dp),
            verticalAlignment = Alignment.Bottom,
            horizontalArrangement = Arrangement.spacedBy(2.dp),
        ) {
            counts.forEach { c ->
                val frac = (c.toFloat() / max.toFloat()).coerceIn(0.04f, 1f)
                Box(
                    Modifier.weight(1f).fillMaxHeight(frac)
                        .background(if (c > 0) AigriWarn else AigriBorder, RoundedCornerShape(2.dp)),
                )
            }
        }
        Spacer(Modifier.height(4.dp))
        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Text("00", color = AigriMuted, fontSize = 9.sp)
            Text("12", color = AigriMuted, fontSize = 9.sp)
            Text("23", color = AigriMuted, fontSize = 9.sp)
        }
    }
}

@Composable
private fun IrrigationCard(events: List<IrrEvent>) {
    AigriCard(Modifier.fillMaxWidth()) {
        SectionLabel("Recent irrigation")
        Spacer(Modifier.height(8.dp))
        if (events.isEmpty()) {
            Text("No irrigation events recorded.", color = AigriMuted, fontSize = 13.sp)
            return@AigriCard
        }
        events.takeLast(8).reversed().forEach { e ->
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 3.dp)) {
                Box(Modifier.size(6.dp).background(AigriBlue, CircleShape))
                Spacer(Modifier.width(8.dp))
                Text("Plant ${e.plant.uppercase()}", color = AigriText, fontSize = 13.sp)
                Spacer(Modifier.weight(1f))
                Text(relTime(e.t), color = AigriMuted, fontSize = 11.sp)
            }
        }
    }
}

private fun moistColor(v: Double): Color = when {
    v < 45 -> AigriWarn
    v <= 65 -> AigriAccent
    else -> AigriBlue
}

private fun relTime(epochSec: Long): String {
    if (epochSec <= 0) return ""
    val diff = System.currentTimeMillis() / 1000 - epochSec
    return when {
        diff < 60 -> "just now"
        diff < 3600 -> "${diff / 60}m ago"
        diff < 86400 -> "${diff / 3600}h ago"
        else -> "${diff / 86400}d ago"
    }
}
