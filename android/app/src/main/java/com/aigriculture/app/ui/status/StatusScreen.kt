package com.aigriculture.app.ui.status

import androidx.compose.foundation.background
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
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import com.aigriculture.app.ui.theme.AigriDanger
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOk
import com.aigriculture.app.ui.theme.AigriOnAccent
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.AigriWarn
import kotlinx.coroutines.delay
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
                item { AutoCard(state, vm::toggleAuto) }
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
