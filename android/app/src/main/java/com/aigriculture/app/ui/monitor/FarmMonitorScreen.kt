package com.aigriculture.app.ui.monitor

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.aspectRatio
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
import com.aigriculture.app.data.net.FarmStatus
import com.aigriculture.app.ui.common.AccentCard
import com.aigriculture.app.ui.common.AigriCard
import com.aigriculture.app.ui.common.ErrorBanner
import com.aigriculture.app.ui.common.MjpegView
import com.aigriculture.app.ui.common.Pill
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.common.SectionLabel
import com.aigriculture.app.ui.common.StatTile
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriAccentBright
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
import com.aigriculture.app.ui.theme.MonoFontFamily
import kotlinx.coroutines.delay
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.jsonPrimitive

@Composable
fun FarmMonitorScreen(showHeader: Boolean = true, vm: FarmMonitorViewModel = viewModel()) {
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
        if (showHeader) {
            Row(
                modifier = Modifier.fillMaxWidth().background(AigriSidebar).padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("FarmMonitor", color = AigriText, fontWeight = FontWeight.W700, fontSize = 16.sp)
                Spacer(Modifier.weight(1f))
                StateBadge(state)
            }
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
                        Box {
                            val cameraModifier = Modifier.fillMaxWidth().aspectRatio(4f / 3f)
                            if (s?.camera_ok == false) {
                                Box(
                                    cameraModifier.background(Color.Black),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    Text(
                                        s.camera_error ?: "Farm camera offline",
                                        color = AigriMuted, fontSize = 12.sp,
                                    )
                                }
                            } else {
                                MjpegView("farm_stream", cameraModifier)
                            }
                            LiveFeedOverlay(
                                scanning = scanning,
                                modifier = cameraModifier,
                            )
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

            if (s != null) {
                item { StatsGrid(s) }
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
                    FrameProgressBar(s)
                }
            }

            if (s?.stage != null) {
                item { ScanStageGrid(s.stage) }
            }

            s?.last_result?.let { r ->
                item { ScanFindingCard(r) }
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

/** REC pill + corner reticle layered over the live feed; REC only when scanning. */
@Composable
private fun LiveFeedOverlay(scanning: Boolean, modifier: Modifier = Modifier) {
    Box(modifier.padding(12.dp)) {
        // Thin corner reticle (top-left + bottom-right L-brackets).
        Box(Modifier.align(Alignment.TopStart)) {
            Box(Modifier.size(width = 18.dp, height = 2.dp).background(AigriAccentBright.copy(alpha = 0.7f)))
            Box(Modifier.size(width = 2.dp, height = 18.dp).background(AigriAccentBright.copy(alpha = 0.7f)))
        }
        Box(Modifier.align(Alignment.BottomEnd)) {
            Box(Modifier.align(Alignment.BottomEnd).size(width = 18.dp, height = 2.dp).background(AigriAccentBright.copy(alpha = 0.7f)))
            Box(Modifier.align(Alignment.BottomEnd).size(width = 2.dp, height = 18.dp).background(AigriAccentBright.copy(alpha = 0.7f)))
        }
        if (scanning) {
            val transition = rememberInfiniteTransition(label = "rec")
            val dotAlpha by transition.animateFloat(
                initialValue = 1f,
                targetValue = 0.25f,
                animationSpec = infiniteRepeatable(
                    animation = tween(700),
                    repeatMode = RepeatMode.Reverse,
                ),
                label = "recDot",
            )
            Pill(
                text = "REC",
                modifier = Modifier.align(Alignment.TopEnd),
                dotColor = AigriDanger.copy(alpha = dotAlpha),
                bg = AigriBg.copy(alpha = 0.66f),
                fg = AigriText,
            )
        }
    }
}

/** Three Stitch stat tiles fed strictly by FarmStatus / last_result. */
@Composable
private fun StatsGrid(s: FarmStatus) {
    Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
        StatTile(
            value = formatNextScan(s.next_scan_at),
            label = "Next Scan",
            modifier = Modifier.weight(1f),
        )
        StatTile(
            value = s.last_result?.disease_frames?.toString() ?: "—",
            label = "Plant Health",
            modifier = Modifier.weight(1f),
            accent = AigriAccentBright,
        )
        StatTile(
            value = s.last_result?.ripeness_frames?.toString() ?: "—",
            label = "Harvest",
            modifier = Modifier.weight(1f),
            accent = AigriAccentBright,
        )
    }
}

/** Captured/target frame progress — hidden unless a real target exists. */
@Composable
private fun FrameProgressBar(s: FarmStatus?) {
    val target = s?.target_frames ?: return
    if (target <= 0) return
    val captured = (s.captured_frames ?: 0).coerceIn(0, target)
    Spacer(Modifier.height(12.dp))
    LinearProgressIndicator(
        progress = { captured.toFloat() / target.toFloat() },
        modifier = Modifier.fillMaxWidth().height(6.dp),
        color = AigriAccent,
        trackColor = AigriBorder,
    )
    Spacer(Modifier.height(6.dp))
    Text(
        "$captured/$target frames",
        color = AigriMuted,
        fontSize = 11.sp,
        fontFamily = MonoFontFamily,
    )
}

/** Four scan-stage chips; the chip matching the real 'stage' string lights up. */
@Composable
private fun ScanStageGrid(stage: String) {
    val active = stageIndex(stage)
    AigriCard(Modifier.fillMaxWidth()) {
        SectionLabel("Scan pipeline")
        Spacer(Modifier.height(10.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth()) {
            StageChips.forEachIndexed { i, label ->
                StageChip(label = label, active = i == active, modifier = Modifier.weight(1f))
            }
        }
    }
}

@Composable
private fun StageChip(label: String, active: Boolean, modifier: Modifier = Modifier) {
    Box(
        modifier = modifier
            .background(
                if (active) AigriAccent.copy(alpha = 0.16f) else AigriBorder.copy(alpha = 0.35f),
                RoundedCornerShape(8.dp),
            )
            .padding(horizontal = 8.dp, vertical = 8.dp),
        contentAlignment = Alignment.Center,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            if (active) Box(Modifier.size(6.dp).background(AigriAccentBright, CircleShape))
            Text(
                label,
                color = if (active) AigriAccentBright else AigriMuted,
                fontSize = 10.sp,
                fontWeight = if (active) FontWeight.W700 else FontWeight.W600,
                maxLines = 1,
            )
        }
    }
}

/** Stitch top-accent card surfacing the latest scan finding from last_result. */
@Composable
private fun ScanFindingCard(r: FarmResult) {
    val clear = r.event_type == "clear" || r.event_type == null
    val hasContent = !r.label.isNullOrBlank() || !r.message.isNullOrBlank() || !r.event_type.isNullOrBlank()
    if (!hasContent) return
    AccentCard(Modifier.fillMaxWidth()) {
        SectionLabel("Latest finding")
        Spacer(Modifier.height(10.dp))
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Box(Modifier.size(9.dp).background(if (clear) AigriOk else AigriWarn, CircleShape))
            Text(
                r.label ?: r.event_type ?: "—",
                color = AigriText,
                fontWeight = FontWeight.W700,
                fontSize = 16.sp,
            )
        }
        if (!r.message.isNullOrBlank()) {
            Spacer(Modifier.height(8.dp))
            Text(r.message, color = AigriMuted, fontSize = 13.sp)
        }
        if (!r.event_type.isNullOrBlank()) {
            Spacer(Modifier.height(10.dp))
            Pill(
                text = r.event_type.replace('_', ' ').replaceFirstChar { it.uppercase() },
                dotColor = if (clear) AigriOk else AigriWarn,
            )
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
            Text(
                "Completed ${ts.take(19).replace('T', ' ')}",
                color = AigriMuted,
                fontSize = 11.sp,
                fontFamily = MonoFontFamily,
            )
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
                color = accent,
                fontWeight = FontWeight.W700,
                fontSize = 12.sp,
                fontFamily = MonoFontFamily,
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

// ── helpers (data formatting only — no fabricated values) ────────────────────

private val StageChips = listOf("Capture", "Plant Health", "Harvest", "Decision")

/** Map the backend 'stage' string onto one of the four pipeline chips; -1 = none. */
private fun stageIndex(stage: String): Int {
    val k = stage.lowercase()
    return when {
        "capture" in k || "scan" in k || "frame" in k -> 0
        "disease" in k || "health" in k || "plant" in k -> 1
        "ripe" in k || "harvest" in k -> 2
        "decision" in k || "decide" in k || "summary" in k || "report" in k -> 3
        else -> -1
    }
}

/** next_scan_at is a loose JsonElement (null or a timestamp string). */
private fun formatNextScan(el: kotlinx.serialization.json.JsonElement?): String {
    if (el == null || el is JsonNull) return "—"
    val raw = runCatching { el.jsonPrimitive.content }.getOrNull()
    if (raw.isNullOrBlank() || raw == "null") return "—"
    // Show just the HH:MM of an ISO timestamp; fall back to the raw value.
    val t = raw.substringAfter('T', "")
    return if (t.length >= 5) t.take(5) else raw
}
