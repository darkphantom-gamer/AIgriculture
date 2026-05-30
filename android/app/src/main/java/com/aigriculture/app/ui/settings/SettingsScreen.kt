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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aigriculture.app.ui.common.AigriCard
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.common.SectionLabel
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText

@Composable
fun SettingsScreen(
    onLoggedOut: () -> Unit,
    vm: SettingsViewModel = viewModel(),
) {
    val ui by vm.ui.collectAsState()
    Column(modifier = Modifier.fillMaxSize().background(AigriBg)) {
        Row(modifier = Modifier.fillMaxWidth().background(AigriSidebar).padding(16.dp)) {
            Text("Settings", color = AigriText, fontWeight = FontWeight.W700, fontSize = 16.sp)
        }
        Column(
            modifier = Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
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
