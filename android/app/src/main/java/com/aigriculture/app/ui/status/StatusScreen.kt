package com.aigriculture.app.ui.status

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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aigriculture.app.data.net.StateMsg
import com.aigriculture.app.ui.common.AigriCard
import com.aigriculture.app.ui.common.ErrorBanner
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriBlue
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriCard as CardBg
import com.aigriculture.app.ui.theme.AigriDanger
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOk
import com.aigriculture.app.ui.theme.AigriOnAccent
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.AigriWarn
import com.aigriculture.app.ui.theme.Dimens
import kotlinx.coroutines.delay
import kotlinx.serialization.json.JsonArray
import kotlin.math.roundToInt

@Composable
fun StatusScreen(vm: StatusViewModel = viewModel()) {
    val ui by vm.ui.collectAsState()
    LaunchedEffect(ui.toast) {
        if (ui.toast != null) { delay(3500); vm.clearToast() }
    }
    val state = ui.state

    Column(modifier = Modifier.fillMaxSize().background(AigriBg)) {
        Row(
            modifier = Modifier.fillMaxWidth().background(AigriSidebar).padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("Status", color = AigriText, fontWeight = FontWeight.W700, fontSize = 16.sp)
            Spacer(Modifier.weight(1f))
            Box(Modifier.size(8.dp).background(if (ui.connected) AigriOk else AigriMuted, CircleShape))
            Spacer(Modifier.width(6.dp))
            Text(if (ui.connected) "Live" else "Offline", color = AigriMuted, fontSize = 12.sp)
        }

        if (ui.toast != null) {
            ErrorBanner(ui.toast!!, Modifier.fillMaxWidth().padding(start = 16.dp, end = 16.dp, top = 12.dp))
        }

        when {
            ui.loading && state == null -> Box(Modifier.fillMaxSize(), Alignment.Center) {
                CircularProgressIndicator(color = AigriAccent)
            }
            ui.error != null && state == null -> Column(
                modifier = Modifier.fillMaxSize().padding(24.dp),
                verticalArrangement = Arrangement.Center,
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(ui.error!!, color = AigriMuted)
                Spacer(Modifier.height(16.dp))
                PrimaryButton("Retry", vm::retry)
            }
            state != null -> LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item { OverviewCard(state) }
                item { AutoCard(state, vm::toggleAuto) }
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(Dimens.radiusSm))
                            .border(1.dp, AigriBorder, RoundedCornerShape(Dimens.radiusSm))
                            .clickable { vm.openSensorPicker() }
                            .padding(14.dp),
                        contentAlignment = Alignment.Center,
                    ) {
                        Text("+ Add sensors", color = AigriAccent, fontWeight = FontWeight.W700, fontSize = 14.sp)
                    }
                }
                val plants = state.active_plants
                if (plants.isEmpty()) {
                    item {
                        AigriCard(Modifier.fillMaxWidth()) {
                            Text("No active sensors yet.", color = AigriText, fontWeight = FontWeight.W600)
                            Spacer(Modifier.height(4.dp))
                            Text("Use “+ Add sensors” on the dashboard to register them.", color = AigriMuted, fontSize = 12.sp)
                        }
                    }
                }
                items(plants, key = { it }) { p ->
                    PlantCard(p, state, p in ui.busyPlants, vm::pump)
                }
            }
        }
    }

    val picker = ui.sensorPicker
    if (picker != null) {
        AlertDialog(
            onDismissRequest = vm::closeSensorPicker,
            confirmButton = {
                if (picker.available > 0) {
                    Button(
                        onClick = vm::addSensors,
                        enabled = !picker.adding,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = AigriAccent,
                            contentColor = AigriOnAccent,
                        ),
                    ) {
                        if (picker.adding) {
                            CircularProgressIndicator(Modifier.size(16.dp), color = AigriOnAccent, strokeWidth = 2.dp)
                        } else {
                            Text("Add ${picker.available}", fontWeight = FontWeight.W700)
                        }
                    }
                }
            },
            dismissButton = {
                TextButton(onClick = vm::closeSensorPicker) {
                    Text(if (picker.available > 0) "Cancel" else "Close", color = AigriMuted)
                }
            },
            title = { Text("Add sensors", color = AigriText, fontWeight = FontWeight.W700) },
            text = {
                if (picker.scanning) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(Modifier.size(18.dp), color = AigriAccent, strokeWidth = 2.dp)
                        Spacer(Modifier.width(12.dp))
                        Text("Scanning the I²C bus…", color = AigriMuted, fontSize = 13.sp)
                    }
                } else {
                    Text(picker.message ?: "", color = AigriMuted, fontSize = 13.sp)
                }
            },
            containerColor = CardBg,
        )
    }
}

@Composable
private fun AutoCard(state: StateMsg, onToggle: (Boolean) -> Unit) {
    val avg = avgMoisture(state)
    AigriCard(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Average moisture", color = AigriMuted, fontSize = 12.sp)
                Text(
                    if (avg != null) "$avg%" else "—",
                    color = colorFor(avg?.toDouble()),
                    fontWeight = FontWeight.W800,
                    fontSize = 30.sp,
                )
            }
            Column(horizontalAlignment = Alignment.End) {
                Text("Auto-irrigation", color = AigriText, fontWeight = FontWeight.W600, fontSize = 13.sp)
                Spacer(Modifier.height(4.dp))
                Switch(
                    checked = state.auto_irr,
                    onCheckedChange = onToggle,
                    colors = SwitchDefaults.colors(
                        checkedThumbColor = Color.White,
                        checkedTrackColor = AigriAccent,
                        uncheckedThumbColor = AigriMuted,
                        uncheckedTrackColor = AigriBorder,
                        uncheckedBorderColor = AigriBorder,
                    ),
                )
                Text("45% → 65%, lock 70%", color = AigriMuted, fontSize = 10.sp)
            }
        }
    }
}

@Composable
private fun PlantCard(
    plant: String,
    state: StateMsg,
    busy: Boolean,
    onPump: (String, Boolean) -> Unit,
) {
    val name = state.plant_names[plant] ?: "Plant ${plant.uppercase()}"
    val moisture = state.moisture[plant]
    val pumpOn = state.pumps[plant] == true
    val hasPump = state.pumps.containsKey(plant)
    val online = state.sensor_status[plant]?.online ?: false

    AigriCard(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(name, color = AigriText, fontWeight = FontWeight.W700, fontSize = 15.sp)
                    Spacer(Modifier.width(8.dp))
                    Box(Modifier.size(7.dp).background(if (online) AigriOk else AigriMuted, CircleShape))
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    moisture?.let { "${it.roundToInt()}%" } ?: "— no reading",
                    color = colorFor(moisture),
                    fontWeight = FontWeight.W800,
                    fontSize = 22.sp,
                )
                Spacer(Modifier.height(6.dp))
                LinearProgressIndicator(
                    progress = { ((moisture ?: 0.0) / 100.0).coerceIn(0.0, 1.0).toFloat() },
                    modifier = Modifier.fillMaxWidth().height(6.dp),
                    color = colorFor(moisture),
                    trackColor = AigriBorder,
                )
                if (pumpOn) {
                    Spacer(Modifier.height(6.dp))
                    Text("💧 watering…", color = AigriBlue, fontSize = 12.sp)
                }
            }
            Spacer(Modifier.width(12.dp))
            if (hasPump) {
                Button(
                    onClick = { onPump(plant, !pumpOn) },
                    enabled = !busy,
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (pumpOn) AigriDanger else AigriAccent,
                        contentColor = if (pumpOn) Color.White else AigriOnAccent,
                        disabledContainerColor = AigriBorder,
                        disabledContentColor = AigriMuted,
                    ),
                ) {
                    if (busy) {
                        CircularProgressIndicator(Modifier.size(16.dp), color = AigriOnAccent, strokeWidth = 2.dp)
                    } else {
                        Text(if (pumpOn) "Stop" else "Water", fontWeight = FontWeight.W700)
                    }
                }
            } else {
                Text("sensor\nonly", color = AigriMuted, fontSize = 11.sp)
            }
        }
    }
}

@Composable
private fun OverviewCard(state: StateMsg) {
    val online = state.sensor_status.values.count { it.online }
    val total = state.active_plants.size
    val pumpsOn = state.pumps.values.count { it }
    val alertsN = (state.alerts as? JsonArray)?.size ?: 0
    val away = !state.at_farm
    val avg = avgMoisture(state)
    AigriCard(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(10.dp).background(if (alertsN > 0) AigriDanger else AigriOk, CircleShape))
            Spacer(Modifier.width(8.dp))
            Text(
                if (alertsN > 0) "$alertsN active alert${if (alertsN > 1) "s" else ""}" else "All clear",
                color = AigriText, fontWeight = FontWeight.W700, fontSize = 15.sp,
            )
            Spacer(Modifier.weight(1f))
            Text(if (away) "Guard armed" else "At farm", color = AigriMuted, fontSize = 11.sp)
        }
        Spacer(Modifier.height(12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            MiniStat("Avg moist", avg?.let { "$it%" } ?: "—", colorFor(avg?.toDouble()), Modifier.weight(1f))
            MiniStat("Sensors", "$online/$total", AigriAccent, Modifier.weight(1f))
            MiniStat("Pumps on", "$pumpsOn", if (pumpsOn > 0) AigriBlue else AigriMuted, Modifier.weight(1f))
        }
    }
}

@Composable
private fun MiniStat(label: String, value: String, accent: Color, modifier: Modifier = Modifier) {
    Box(
        modifier
            .background(AigriBorder.copy(alpha = 0.3f), RoundedCornerShape(10.dp))
            .padding(vertical = 10.dp, horizontal = 6.dp),
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(value, color = accent, fontWeight = FontWeight.W800, fontSize = 18.sp)
            Spacer(Modifier.height(2.dp))
            Text(label, color = AigriMuted, fontSize = 9.sp)
        }
    }
}

private fun colorFor(v: Double?): Color = when {
    v == null -> AigriMuted
    v < 45 -> AigriWarn
    v <= 65 -> AigriAccent
    else -> AigriBlue
}

private fun avgMoisture(s: StateMsg): Int? {
    val vals = s.active_plants.mapNotNull { s.moisture[it] }
    if (vals.isEmpty()) return null
    return vals.average().roundToInt()
}
