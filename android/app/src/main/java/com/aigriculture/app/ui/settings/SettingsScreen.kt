package com.aigriculture.app.ui.settings

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
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
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aigriculture.app.ui.common.AigriCard
import com.aigriculture.app.ui.common.AigriTextField
import com.aigriculture.app.ui.common.ErrorBanner
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.common.SectionLabel
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.AigriWarn
import kotlinx.coroutines.delay

@Composable
fun SettingsScreen(
    onLoggedOut: () -> Unit,
    vm: SettingsViewModel = viewModel(),
) {
    val ui by vm.ui.collectAsState()
    LaunchedEffect(ui.toast) {
        if (ui.toast != null) { delay(3500); vm.clearToast() }
    }

    Column(modifier = Modifier.fillMaxSize().background(AigriBg)) {
        Row(modifier = Modifier.fillMaxWidth().background(AigriSidebar).padding(16.dp)) {
            Text("Settings", color = AigriText, fontWeight = FontWeight.W700, fontSize = 16.sp)
        }
        Column(
            modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (ui.toast != null) {
                ErrorBanner(ui.toast!!, Modifier.fillMaxWidth())
            }

            AigriCard(Modifier.fillMaxWidth()) {
                SectionLabel("Account")
                Spacer(Modifier.height(10.dp))
                InfoRow("Signed in as", ui.me?.display_name ?: ui.me?.username ?: "—")
                InfoRow("Username", ui.me?.username ?: "—")
                InfoRow("Role", ui.me?.role ?: "—")
            }

            AigriCard(Modifier.fillMaxWidth()) {
                SectionLabel("Server")
                Spacer(Modifier.height(10.dp))
                InfoRow("Address", ui.host)
            }

            AigriCard(Modifier.fillMaxWidth()) {
                SectionLabel("Alert email")
                Spacer(Modifier.height(10.dp))
                Text(
                    "Where FarmMonitor disease alerts and FLORA reports are sent.",
                    color = AigriMuted, fontSize = 12.sp,
                )
                Spacer(Modifier.height(10.dp))
                AigriTextField(
                    value = ui.email,
                    onValueChange = vm::setEmail,
                    label = "you@example.com",
                    modifier = Modifier.fillMaxWidth(),
                    keyboardType = KeyboardType.Email,
                )
                Spacer(Modifier.height(10.dp))
                PrimaryButton(
                    text = "Save email",
                    onClick = vm::saveEmail,
                    modifier = Modifier.fillMaxWidth(),
                    loading = ui.emailSaving,
                )
                if (!ui.smtpReady) {
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "⚠ Server SMTP isn't configured — emails won't actually send until config.yaml has SMTP.",
                        color = AigriWarn, fontSize = 11.sp,
                    )
                }
            }

            AigriCard(Modifier.fillMaxWidth()) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Security siren", color = AigriText, fontWeight = FontWeight.W700, fontSize = 15.sp)
                        Spacer(Modifier.height(4.dp))
                        Text(
                            if (ui.sirenEnabled) "On — sounds the buzzer when a threat is detected."
                            else "Muted — threats are still logged, but no buzzer.",
                            color = AigriMuted, fontSize = 12.sp,
                        )
                    }
                    Spacer(Modifier.width(12.dp))
                    if (ui.sirenBusy) {
                        CircularProgressIndicator(Modifier.height(22.dp).width(22.dp), color = AigriAccent, strokeWidth = 2.dp)
                    } else {
                        Switch(
                            checked = ui.sirenEnabled,
                            onCheckedChange = { vm.toggleSiren(it) },
                            colors = SwitchDefaults.colors(
                                checkedThumbColor = Color.White,
                                checkedTrackColor = AigriAccent,
                                uncheckedThumbColor = AigriMuted,
                                uncheckedTrackColor = AigriBorder,
                                uncheckedBorderColor = AigriBorder,
                            ),
                        )
                    }
                }
            }

            Spacer(Modifier.height(4.dp))
            PrimaryButton(
                text = if (ui.loggingOut) "Signing out…" else "Sign out",
                onClick = { vm.logout(onLoggedOut) },
                modifier = Modifier.fillMaxWidth(),
                loading = ui.loggingOut,
            )
            Text(
                "AIgriculture · mobile",
                color = AigriMuted,
                fontSize = 11.sp,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )
        }
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(label, color = AigriMuted, fontSize = 13.sp, modifier = Modifier.weight(1f))
        Text(value, color = AigriText, fontSize = 13.sp, fontWeight = FontWeight.W600)
    }
}
