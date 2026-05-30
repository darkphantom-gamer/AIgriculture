package com.aigriculture.app.ui.security

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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
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
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText
import kotlinx.coroutines.delay

@Composable
fun SecurityScreen(vm: SecurityViewModel = viewModel()) {
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

    Column(modifier = Modifier.fillMaxSize().background(AigriBg)) {
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
                        MjpegView("stream", Modifier.fillMaxWidth().height(320.dp))
                        Text(
                            "Live security camera",
                            color = AigriMuted,
                            fontSize = 12.sp,
                            modifier = Modifier.padding(12.dp),
                        )
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

            item {
                AigriCard(Modifier.fillMaxWidth()) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Test siren", color = AigriText, fontWeight = FontWeight.W700, fontSize = 15.sp)
                            Spacer(Modifier.height(4.dp))
                            Text("Sends three short beeps to the buzzer.", color = AigriMuted, fontSize = 12.sp)
                        }
                        Spacer(Modifier.width(12.dp))
                        PrimaryButton("Beep", vm::testSiren, loading = ui.sirenBusy)
                    }
                }
            }

            item { SectionLabel("Active alerts") }
            if (ui.alerts.isEmpty()) {
                item {
                    AigriCard(Modifier.fillMaxWidth()) {
                        Text("All clear — no active alerts.", color = AigriMuted, fontSize = 13.sp)
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
