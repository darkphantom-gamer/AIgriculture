package com.aigriculture.app.ui.security

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.ExperimentalLayoutApi
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
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
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
import com.aigriculture.app.data.net.AlertDetail
import com.aigriculture.app.ui.common.AccentCard
import com.aigriculture.app.ui.common.AigriCard
import com.aigriculture.app.ui.common.ErrorBanner
import com.aigriculture.app.ui.common.MjpegView
import com.aigriculture.app.ui.common.Pill
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.common.SectionLabel
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriAccentBright
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriDanger
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOk
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.AigriWarn
import com.aigriculture.app.ui.theme.MonoFontFamily
import kotlin.math.roundToInt
import kotlinx.coroutines.delay

/** Map an AlertDetail.level string to its severity color (high>medium>low). */
private fun levelColor(level: String): Color = when (level.lowercase()) {
    "high" -> AigriDanger
    "medium" -> AigriWarn
    else -> AigriOk
}

/** Numeric rank so we can pick the worst level across all active threats. */
private fun levelRank(level: String): Int = when (level.lowercase()) {
    "high" -> 3
    "medium" -> 2
    "low" -> 1
    else -> 0
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SecurityScreen(showHeader: Boolean = true, vm: SecurityViewModel = viewModel()) {
    val ui by vm.ui.collectAsState()

    LaunchedEffect(Unit) {
        vm.refresh()
        while (true) {
            delay(4000)
            vm.refresh()
        }
    }
    LaunchedEffect(ui.toast) {
        if (ui.toast != null) { delay(3500); vm.clearToast() }
    }

    // Overall threat is the worst level present in the real detail list; when the
    // list is empty there's nothing to escalate, so we stay in the calm state.
    val worst: AlertDetail? = ui.detail.maxByOrNull { levelRank(it.level) }
    val overallColor = if (worst == null) AigriOk else levelColor(worst.level)

    Column(modifier = Modifier.fillMaxSize().background(AigriBg)) {
        if (showHeader) {
            Row(
                modifier = Modifier.fillMaxWidth().background(AigriSidebar).padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Security", color = AigriText, fontWeight = FontWeight.W700, fontSize = 16.sp)
                Spacer(Modifier.weight(1f))
                Box(Modifier.size(8.dp).background(if (ui.armed) AigriDanger else AigriOk, CircleShape))
                Spacer(Modifier.width(6.dp))
                Text(if (ui.armed) "Guard ON" else "Guard off", color = AigriMuted, fontSize = 12.sp)
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
                            MjpegView("stream", Modifier.fillMaxWidth().aspectRatio(4f / 3f))
                            // "REC" pill only when the guard is actually armed (away).
                            if (ui.armed) {
                                Pill(
                                    "REC",
                                    modifier = Modifier
                                        .align(Alignment.TopStart)
                                        .padding(10.dp),
                                    dotColor = AigriDanger,
                                    bg = AigriBg.copy(alpha = 0.7f),
                                    fg = AigriText,
                                    border = AigriBorder,
                                )
                            }
                        }
                        Row(
                            modifier = Modifier.fillMaxWidth().padding(12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Text("Live security camera", color = AigriMuted, fontSize = 12.sp)
                            Spacer(Modifier.weight(1f))
                            Pill(
                                if (ui.armed) "Armed" else "At farm",
                                dotColor = if (ui.armed) AigriDanger else AigriOk,
                                fg = AigriMuted,
                            )
                        }
                    }
                }
            }

            // ── Threat panel, derived entirely from ui.detail ──────────────────
            item {
                AccentCard(Modifier.fillMaxWidth()) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            SectionLabel("Threat status")
                            Spacer(Modifier.height(6.dp))
                            Text(
                                if (worst == null) "All clear"
                                else worst.level.replaceFirstChar { it.uppercase() },
                                color = if (worst == null) AigriAccentBright else overallColor,
                                fontWeight = FontWeight.W800,
                                fontSize = 22.sp,
                            )
                        }
                        Box(Modifier.size(11.dp).background(overallColor, CircleShape))
                    }

                    Spacer(Modifier.height(12.dp))

                    if (ui.detail.isEmpty()) {
                        Text(
                            "No active threats detected.",
                            color = AigriMuted,
                            fontSize = 13.sp,
                        )
                    } else {
                        FlowRow(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp),
                            verticalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            ui.detail.forEach { d ->
                                ThreatPill(d)
                            }
                        }
                    }
                }
            }

            item {
                AigriCard(Modifier.fillMaxWidth()) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Guard mode", color = AigriText, fontWeight = FontWeight.W700, fontSize = 15.sp)
                            Spacer(Modifier.height(4.dp))
                            Text(
                                if (ui.armed) "Armed — away. A detected threat sounds the siren."
                                else "Disarmed — you're at the farm, no alerts.",
                                color = AigriMuted, fontSize = 12.sp,
                            )
                        }
                        Spacer(Modifier.width(12.dp))
                        if (ui.guardBusy) {
                            CircularProgressIndicator(Modifier.size(22.dp), color = AigriAccent, strokeWidth = 2.dp)
                        } else {
                            Switch(
                                checked = ui.armed,
                                onCheckedChange = { vm.setGuard(it) },
                                colors = SwitchDefaults.colors(
                                    checkedThumbColor = Color.White,
                                    checkedTrackColor = AigriDanger,
                                    uncheckedThumbColor = AigriMuted,
                                    uncheckedTrackColor = AigriBorder,
                                    uncheckedBorderColor = AigriBorder,
                                ),
                            )
                        }
                    }
                }
            }

            item { SectionLabel("Active alerts") }
            if (ui.alerts.isEmpty()) {
                item {
                    AigriCard(Modifier.fillMaxWidth()) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(7.dp).background(AigriOk, CircleShape))
                            Spacer(Modifier.width(8.dp))
                            Text("All clear — no active alerts.", color = AigriMuted, fontSize = 13.sp)
                        }
                    }
                }
            } else {
                items(ui.alerts) { a ->
                    AigriCard(Modifier.fillMaxWidth()) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.size(7.dp).background(AigriDanger, CircleShape))
                            Spacer(Modifier.width(8.dp))
                            Text(a, color = AigriText, fontSize = 13.sp)
                        }
                    }
                }
            }
        }
    }
}

/**
 * One active threat rendered as a tinted pill: real emoji icon + name from the
 * model, with conf (0..1) shown as a whole percentage in the mono face. Color
 * keys off the threat's own level so high/medium/low read at a glance.
 */
@Composable
private fun ThreatPill(d: AlertDetail) {
    val color = levelColor(d.level)
    val pct = (d.conf.coerceIn(0.0, 1.0) * 100).roundToInt()
    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(50))
            .background(color.copy(alpha = 0.14f))
            .padding(horizontal = 10.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (d.icon.isNotEmpty()) Text(d.icon, fontSize = 13.sp)
        if (d.name.isNotEmpty()) {
            Text(d.name, color = color, fontSize = 12.sp, fontWeight = FontWeight.W700, maxLines = 1)
        }
        Text(
            "$pct%",
            color = color,
            fontSize = 12.sp,
            fontWeight = FontWeight.W700,
            fontFamily = MonoFontFamily,
            maxLines = 1,
        )
    }
}
