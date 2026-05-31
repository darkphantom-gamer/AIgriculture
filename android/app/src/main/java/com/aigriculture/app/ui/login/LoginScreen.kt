package com.aigriculture.app.ui.login

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Visibility
import androidx.compose.material.icons.filled.VisibilityOff
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.blur
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aigriculture.app.data.net.Net
import com.aigriculture.app.ui.common.AccentCard
import com.aigriculture.app.ui.common.AigriTextField
import com.aigriculture.app.ui.common.BrandHeader
import com.aigriculture.app.ui.common.ErrorBanner
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriAccentBright
import com.aigriculture.app.ui.theme.AigriAccentGlow
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriCard
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.Dimens

@Composable
fun LoginScreen(
    onLoggedIn: () -> Unit,
    onChangeServer: () -> Unit,
    vm: LoginViewModel = viewModel(),
) {
    val ui by vm.ui.collectAsState()
    var passwordVisible by remember { mutableStateOf(false) }
    val host = Net.baseUrl?.removePrefix("https://")?.removePrefix("http://") ?: "—"
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
            // Soft accent halo behind the wordmark — the Stitch hero glow treatment.
            Box(contentAlignment = Alignment.Center) {
                Box(
                    modifier = Modifier
                        .size(160.dp)
                        .blur(48.dp)
                        .background(
                            brush = Brush.radialGradient(
                                listOf(AigriAccentGlow.copy(alpha = 0.30f), AigriBg.copy(alpha = 0f)),
                            ),
                        ),
                )
                BrandHeader(subtitle = "Strawberry Monitoring")
            }
            Spacer(Modifier.height(28.dp))
            AccentCard(modifier = Modifier.fillMaxWidth()) {
                Text("Sign in", color = AigriText, fontWeight = FontWeight.W700, fontSize = 18.sp)
                Spacer(Modifier.height(4.dp))
                Text("Server  $host", color = AigriMuted, fontSize = 12.sp)
                Spacer(Modifier.height(18.dp))
                AigriTextField(
                    value = ui.username,
                    onValueChange = vm::onUsername,
                    label = "Username",
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                // Inline field mirroring AigriTextField's exact colors, plus a
                // reveal toggle (AigriTextField doesn't expose a trailingIcon).
                OutlinedTextField(
                    value = ui.password,
                    onValueChange = vm::onPassword,
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Password") },
                    singleLine = true,
                    visualTransformation =
                        if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
                    shape = RoundedCornerShape(Dimens.radiusSm),
                    trailingIcon = {
                        IconButton(onClick = { passwordVisible = !passwordVisible }) {
                            Icon(
                                imageVector =
                                    if (passwordVisible) Icons.Filled.Visibility else Icons.Filled.VisibilityOff,
                                contentDescription =
                                    if (passwordVisible) "Hide password" else "Show password",
                                tint = AigriAccentBright,
                            )
                        }
                    },
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = AigriAccent,
                        unfocusedBorderColor = AigriBorder,
                        focusedLabelColor = AigriAccent,
                        unfocusedLabelColor = AigriMuted,
                        cursorColor = AigriAccent,
                        focusedTextColor = AigriText,
                        unfocusedTextColor = AigriText,
                        focusedContainerColor = AigriCard,
                        unfocusedContainerColor = AigriCard,
                    ),
                )
                if (ui.error != null) {
                    Spacer(Modifier.height(12.dp))
                    ErrorBanner(ui.error!!, Modifier.fillMaxWidth())
                }
                Spacer(Modifier.height(18.dp))
                PrimaryButton(
                    text = if (ui.loading) "Signing in…" else "Sign in",
                    onClick = { vm.submit(onLoggedIn) },
                    modifier = Modifier.fillMaxWidth(),
                    loading = ui.loading,
                )
            }
            Spacer(Modifier.height(10.dp))
            TextButton(onClick = onChangeServer) {
                Text("Change server", color = AigriAccent, fontSize = 13.sp)
            }
        }
    }
}
