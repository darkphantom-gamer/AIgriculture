package com.aigriculture.app.ui.connect

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aigriculture.app.ui.common.AccentCard
import com.aigriculture.app.ui.common.AigriTextField
import com.aigriculture.app.ui.common.BrandHeader
import com.aigriculture.app.ui.common.ErrorBanner
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.common.SectionLabel
import com.aigriculture.app.ui.theme.AigriAccentBright
import com.aigriculture.app.ui.theme.AigriAccentGlow
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.MonoFontFamily

@Composable
fun ConnectScreen(
    onConnected: () -> Unit,
    vm: ConnectViewModel = viewModel(),
) {
    val ui by vm.ui.collectAsState()
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(AigriBg)
            .padding(24.dp),
        contentAlignment = Alignment.Center,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .widthIn(max = 440.dp)
                .verticalScroll(rememberScrollState()),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            // Atmospheric accent halo behind the wordmark — soft, not loud.
            Box(contentAlignment = Alignment.Center) {
                Box(
                    modifier = Modifier
                        .size(220.dp)
                        .background(
                            brush = Brush.radialGradient(
                                colors = listOf(
                                    AigriAccentGlow.copy(alpha = 0.16f),
                                    Color.Transparent,
                                ),
                                center = Offset.Unspecified,
                            ),
                        ),
                )
                BrandHeader(subtitle = "Farm Monitoring Console")
            }
            Spacer(Modifier.height(28.dp))
            AccentCard(modifier = Modifier.fillMaxWidth()) {
                Text("Connect to your farm", color = AigriText, fontWeight = FontWeight.W700, fontSize = 18.sp)
                Spacer(Modifier.height(8.dp))
                Text(
                    "Enter the address of the Raspberry Pi running AIgriculture.",
                    color = AigriMuted, fontSize = 13.sp,
                )
                Spacer(Modifier.height(18.dp))
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Icon(
                        Icons.Filled.Dns,
                        contentDescription = null,
                        tint = AigriAccentBright,
                        modifier = Modifier.size(15.dp),
                    )
                    SectionLabel("Server address")
                }
                Spacer(Modifier.height(8.dp))
                AigriTextField(
                    value = ui.address,
                    onValueChange = vm::onAddressChange,
                    label = "Server address",
                    modifier = Modifier.fillMaxWidth(),
                    keyboardType = KeyboardType.Uri,
                )
                Spacer(Modifier.height(6.dp))
                Text(
                    "e.g. 192.168.1.50:8000   or   https://farm.example.com",
                    color = AigriMuted, fontSize = 11.sp, fontFamily = MonoFontFamily,
                )
                if (ui.error != null) {
                    Spacer(Modifier.height(12.dp))
                    ErrorBanner(ui.error!!, Modifier.fillMaxWidth())
                }
                Spacer(Modifier.height(18.dp))
                PrimaryButton(
                    text = if (ui.loading) "Connecting…" else "Connect",
                    onClick = { vm.connect(onConnected) },
                    modifier = Modifier.fillMaxWidth(),
                    loading = ui.loading,
                )
            }
            Spacer(Modifier.height(16.dp))
            Text(
                "Tip: on the Pi, run  hostname -I  to find its IP address.",
                color = AigriMuted, fontSize = 11.sp, textAlign = TextAlign.Center,
            )
        }
    }
}
