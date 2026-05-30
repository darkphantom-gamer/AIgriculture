package com.aigriculture.app.ui.monitor

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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.LinearProgressIndicator
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
import com.aigriculture.app.data.net.FarmResult
import com.aigriculture.app.ui.common.AigriCard
import com.aigriculture.app.ui.common.ErrorBanner
import com.aigriculture.app.ui.common.MjpegView
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.common.SectionLabel
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriDanger
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOk
import com.aigriculture.app.ui.theme.AigriOnAccent
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.AigriWarn
import com.aigriculture.app.ui.theme.Dimens
import kotlinx.coroutines.delay

@Composable
fun FarmMonitorScreen(vm: FarmMonitorViewModel = viewModel()) {
    val ui by vm.ui.collectAsState()

    LaunchedEffect(Unit) {
        vm.refresh()
        while (true) {
            delay(3000)
            vm.refresh()
        }
    }
    LaunchedEffect(ui.toast) {
        if (ui.toast != null) { delay(3500); vm.clearToast() }
    }

    val s = ui.status
    val state = s?.state ?: "idle"
    val scanning = state == "scanning" || state == "queued"

    Column(modifier = Modifier.fillMaxSize().background(AigriBg)) {
        Row(
            modifier = Modifier.fillMaxWidth().background(AigriSidebar).padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("FarmMonitor", color = AigriText, fontWeight = FontWeight.W700, fontSize = 16.sp)
            Spacer(Modifier.weight(1f))
            StateBadge(state)
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (ui.toast != null) {
                item { ErrorBanner(ui.toast!!, Modifier.fillMaxWidth()) }
            }
            if (ui.error != null && !ui.loaded) {
                item { ErrorBanner(ui.error!!, Modifier.fillMaxWidth()) }
            }

            item {
                AigriCard(Modifier.fillMaxWidth(), padding = PaddingValues(0.dp)) {
                    Column {
                        if (s?.camera_ok == false) {
                            Box(
                                Modifier.fillMaxWidth().height(320.dp).background(Color.Black),
                                contentAlignment = Alignment.Center,
                            ) {
                                Text(
                                    s.camera_error ?: "Farm camera offline",
                                    color = AigriMuted, fontSize = 12.sp,
                                )
                            }
                        } else {
                            MjpegView("farm_stream", Modifier.fillMaxWidth().height(320.dp))
                        }
                        Text(
                            "Live field camera",
                            color = AigriMuted,
                            fontSize = 12.sp,
                            modifier = Modifier.padding(12.dp),
                        )
                    }
                }
            }

            item {
                AigriCard(Modifier.fillMaxWidth()) {
                    Text(s?.message ?: "Waiting for scheduled scan", color = AigriText, fontSize = 13.sp)
                    if (scanning && s?.total_cycles != null) {
                        val total = s.total_cycles.coerceAtLeast(1)
                        val current = (s.current_cycle ?: 0).coerceIn(0, total)
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "Cycle $current / $total" + (s.stage?.let { "  •  ${it.replace('_', ' ')}" } ?: ""),
                            color = AigriMuted, fontSize = 11.sp,
                        )
                        Spacer(Modifier.height(6.dp))
                        LinearProgressIndicator(
                            progress = { current.toFloat() / total.toFloat() },
                            modifier = Modifier.fillMaxWidth().height(6.dp),
                            color = AigriWarn,
                            trackColor = AigriBorder,
                        )
                    }
                }
            }

            s?.last_result?.let { r ->
                item { LastResultCard(r) }
            }

            item {
                if (scanning) {
                    Button(
                        onClick = vm::stopScan,
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !ui.scanBusy,
                        shape = RoundedCornerShape(Dimens.radiusSm),
                        colors = ButtonDefaults.buttonColors(
                            containerColor = AigriDanger,
                            contentColor = Color.White,
                            disabledContainerColor = AigriBorder,
                            disabledContentColor = AigriMuted,
                        ),
                    ) {
                        Text(if (ui.scanBusy) "Stopping…" else "Stop scan", fontWeight = FontWeight.W700)
                    }
                } else {
                    PrimaryButton(
                        text = "Scan now",
                        onClick = vm::scanNow,
                        modifier = Modifier.fillMaxWidth(),
                        loading = ui.scanBusy,
                    )
                }
            }
        }
    }
}

@Composable
private fun LastResultCard(r: FarmResult) {
    val clear = r.event_type == "clear" || r.event_type == null
    AigriCard(Modifier.fillMaxWidth()) {
        SectionLabel("Last scan result")
        Spacer(Modifier.height(8.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(8.dp).background(if (clear) AigriOk else AigriWarn, CircleShape))
            Spacer(Modifier.width(8.dp))
            Text(r.label ?: "—", color = AigriText, fontWeight = FontWeight.W700, fontSize = 15.sp)
        }
        if (!r.message.isNullOrBlank()) {
            Spacer(Modifier.height(6.dp))
            Text(r.message, color = AigriMuted, fontSize = 12.sp)
        }
        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Stat("Disease", r.disease_frames, r.usable_frames, AigriDanger)
            Stat("Harvest", r.ripeness_frames, r.usable_frames, AigriAccent)
        }
        r.completed_at?.let { ts ->
            Spacer(Modifier.height(8.dp))
            Text("Completed ${ts.take(19).replace('T', ' ')}", color = AigriMuted, fontSize = 11.sp)
        }
    }
}

@Composable
private fun Stat(label: String, value: Int?, total: Int?, accent: Color) {
    Box(
        Modifier
            .background(AigriBorder.copy(alpha = 0.35f), RoundedCornerShape(8.dp))
            .padding(horizontal = 10.dp, vertical = 6.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text("$label ", color = AigriMuted, fontSize = 11.sp)
            Text(
                "${value ?: 0}" + (total?.let { "/$it" } ?: ""),
                color = accent, fontWeight = FontWeight.W700, fontSize = 12.sp,
            )
        }
    }
}

@Composable
private fun StateBadge(state: String) {
    val (bg, fg, label) = when (state) {
        "scanning" -> Triple(AigriWarn, AigriOnAccent, "Scanning")
        "queued" -> Triple(AigriWarn, AigriOnAccent, "Queued")
        "error" -> Triple(AigriDanger, Color.White, "Error")
        "done", "complete", "idle" -> Triple(AigriBorder, AigriMuted, if (state == "idle") "Idle" else "Done")
        else -> Triple(AigriBorder, AigriMuted, state.replaceFirstChar { it.uppercase() })
    }
    Box(
        Modifier.background(bg, RoundedCornerShape(20.dp)).padding(horizontal = 12.dp, vertical = 5.dp),
    ) {
        Text(label, color = fg, fontSize = 11.sp, fontWeight = FontWeight.W700)
    }
}
