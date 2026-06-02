package com.aigriculture.app.ui.settings

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.ImageDecoder
import android.net.Uri
import android.os.Build
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.AlternateEmail
import androidx.compose.material.icons.filled.Badge
import androidx.compose.material.icons.filled.CameraAlt
import androidx.compose.material.icons.filled.Dns
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
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
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import coil.compose.AsyncImage
import coil.request.ImageRequest
import com.aigriculture.app.R
import com.aigriculture.app.data.net.Net
import com.aigriculture.app.ui.common.AccentCard
import com.aigriculture.app.ui.common.AigriCard
import com.aigriculture.app.ui.common.AigriTextField
import com.aigriculture.app.ui.common.ErrorBanner
import com.aigriculture.app.ui.common.Pill
import com.aigriculture.app.ui.common.PrimaryButton
import com.aigriculture.app.ui.common.SectionLabel
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriAccentBright
import com.aigriculture.app.ui.theme.AigriAccentGlow
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriDanger
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOk
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.AigriWarn
import com.aigriculture.app.ui.theme.Dimens
import com.aigriculture.app.ui.theme.MonoFontFamily
import kotlinx.coroutines.delay
import java.io.ByteArrayOutputStream
import java.util.Locale

@Composable
fun SettingsScreen(
    onLoggedOut: () -> Unit,
    vm: SettingsViewModel = viewModel(),
) {
    val ui by vm.ui.collectAsState()
    val context = LocalContext.current

    LaunchedEffect(ui.toast) {
        if (ui.toast != null) { delay(3500); vm.clearToast() }
    }

    val avatarLauncher = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) {
            val avatar = readAvatarUpload(context, uri)
            if (avatar != null) vm.uploadAvatar(avatar.bytes, avatar.mime)
            else vm.uploadAvatar(ByteArray(0), "image/jpeg")
        }
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

            // ── Profile card: avatar (tap to change) + name + role ──────────────
            ProfileCard(
                avatarUrl = ui.me?.avatar_url,
                displayName = ui.me?.display_name ?: ui.me?.username ?: "—",
                username = ui.me?.username,
                role = ui.me?.role,
                avatarUploading = ui.avatarUploading,
                avatarVersion = ui.avatarVersion,
                onEditAvatar = { avatarLauncher.launch("image/*") },
            )

            // ── Account / Server rows ────────────────────────────────────────────
            AigriCard(Modifier.fillMaxWidth()) {
                SectionLabel("Account")
                Spacer(Modifier.height(12.dp))
                IconSettingRow(
                    icon = Icons.Filled.Person,
                    label = "Username",
                    value = ui.me?.username ?: "—",
                )
                Spacer(Modifier.height(12.dp))
                IconSettingRow(
                    icon = Icons.Filled.Badge,
                    label = "Role",
                    value = ui.me?.role ?: "—",
                )
                Spacer(Modifier.height(12.dp))
                IconSettingRow(
                    icon = Icons.Filled.Dns,
                    label = "Server",
                    value = ui.host,
                    valueMono = true,
                )
            }

            // ── Notification email ───────────────────────────────────────────────
            AccentCard(Modifier.fillMaxWidth()) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    AccentIcon(Icons.Filled.AlternateEmail)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text("Alert email", color = AigriText, fontWeight = FontWeight.W700, fontSize = 15.sp)
                        Spacer(Modifier.height(2.dp))
                        Text(
                            "Where FarmMonitor disease alerts and FLORA reports are sent.",
                            color = AigriMuted, fontSize = 12.sp,
                        )
                    }
                }
                Spacer(Modifier.height(12.dp))
                AigriTextField(
                    value = ui.email,
                    onValueChange = vm::setEmail,
                    label = "you@example.com",
                    modifier = Modifier.fillMaxWidth(),
                    keyboardType = KeyboardType.Email,
                )
                Spacer(Modifier.height(10.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (ui.smtpReady) {
                        Pill(text = "SMTP ready", dotColor = AigriOk, fg = AigriOk)
                    } else {
                        Pill(text = "SMTP not configured", dotColor = AigriWarn, fg = AigriWarn)
                    }
                    Spacer(Modifier.weight(1f))
                }
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

            // ── Security siren toggle ────────────────────────────────────────────
            AigriCard(Modifier.fillMaxWidth()) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    AccentIcon(Icons.Filled.VolumeUp)
                    Spacer(Modifier.width(12.dp))
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
            DangerButton(
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
private fun ProfileCard(
    avatarUrl: String?,
    displayName: String,
    username: String?,
    role: String?,
    avatarUploading: Boolean,
    avatarVersion: Long,
    onEditAvatar: () -> Unit,
) {
    AccentCard(Modifier.fillMaxWidth()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            // Avatar with glow halo + tappable camera-edit badge
            Box(contentAlignment = Alignment.Center) {
                Box(
                    Modifier
                        .size(74.dp)
                        .background(
                            Brush.radialGradient(listOf(AigriAccentGlow.copy(alpha = 0.35f), Color.Transparent)),
                            CircleShape,
                        )
                )
                // 64dp outer box so the 20dp badge (at BottomEnd) doesn't clip under the circle
                Box(Modifier.size(64.dp)) {
                    val resolved = avatarUrl?.takeIf { it.isNotBlank() }?.let {
                        if (it.startsWith("http")) it else Net.absUrl(it)
                    }?.let { cacheBustAvatar(it, avatarVersion) }
                    val avatarModel = ImageRequest.Builder(LocalContext.current)
                        .data(resolved ?: R.drawable.farmer_default)
                        .placeholder(R.drawable.farmer_default)
                        .error(R.drawable.farmer_default)
                        .crossfade(true)
                        .build()
                    Box(
                        modifier = Modifier
                            .size(60.dp)
                            .clip(CircleShape)
                            .background(AigriBg)
                            .clickable(onClick = onEditAvatar),
                        contentAlignment = Alignment.Center,
                    ) {
                        if (avatarUploading) {
                            CircularProgressIndicator(Modifier.size(28.dp), color = AigriAccent, strokeWidth = 2.dp)
                        } else {
                            AsyncImage(
                                model = avatarModel,
                                contentDescription = "Avatar",
                                modifier = Modifier.size(60.dp).clip(CircleShape),
                                contentScale = ContentScale.Crop,
                            )
                        }
                    }
                    // Camera badge — bottom-right of the 64dp box
                    Box(
                        modifier = Modifier
                            .size(20.dp)
                            .align(Alignment.BottomEnd)
                            .background(AigriAccent, CircleShape),
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(Icons.Filled.CameraAlt, contentDescription = "Change photo", modifier = Modifier.size(11.dp), tint = Color.White)
                    }
                }
            }
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    displayName,
                    color = AigriText,
                    fontWeight = FontWeight.W800,
                    fontSize = 18.sp,
                    maxLines = 1,
                )
                if (username != null) {
                    Spacer(Modifier.height(2.dp))
                    Text("@$username", color = AigriMuted, fontSize = 12.sp, maxLines = 1)
                }
                if (role != null) {
                    Spacer(Modifier.height(8.dp))
                    Pill(text = role, dotColor = AigriAccent, fg = AigriAccentBright)
                }
            }
        }
    }
}

private fun cacheBustAvatar(url: String, version: Long): String {
    if (version <= 0L) return url
    val sep = if (url.contains("?")) "&" else "?"
    return "$url${sep}v=$version"
}

private data class AvatarUpload(val bytes: ByteArray, val mime: String)

private val supportedAvatarMimes = setOf("image/jpeg", "image/jpg", "image/png", "image/webp", "image/gif")

private fun readAvatarUpload(context: Context, uri: Uri): AvatarUpload? {
    val mime = context.contentResolver.getType(uri)
        ?.substringBefore(";")
        ?.lowercase(Locale.US)
        ?: "image/jpeg"
    val raw = context.contentResolver.openInputStream(uri)?.use { it.readBytes() } ?: return null
    if (mime in supportedAvatarMimes) return AvatarUpload(raw, mime)

    val jpeg = decodeAvatar(context, uri)?.let { bitmap ->
        ByteArrayOutputStream().use { out ->
            bitmap.compress(Bitmap.CompressFormat.JPEG, 90, out)
            out.toByteArray()
        }
    }
    return jpeg?.let { AvatarUpload(it, "image/jpeg") } ?: AvatarUpload(raw, mime)
}

private fun decodeAvatar(context: Context, uri: Uri): Bitmap? = try {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
        ImageDecoder.decodeBitmap(ImageDecoder.createSource(context.contentResolver, uri)) { decoder, _, _ ->
            decoder.allocator = ImageDecoder.ALLOCATOR_SOFTWARE
        }
    } else {
        context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it) }
    }
} catch (_: Exception) {
    null
}

@Composable
private fun AccentIcon(icon: ImageVector) {
    Box(
        modifier = Modifier
            .size(38.dp)
            .clip(RoundedCornerShape(Dimens.radiusSm))
            .background(AigriAccent.copy(alpha = 0.12f)),
        contentAlignment = Alignment.Center,
    ) {
        Icon(icon, contentDescription = null, tint = AigriAccentBright, modifier = Modifier.size(20.dp))
    }
}

@Composable
private fun IconSettingRow(
    icon: ImageVector,
    label: String,
    value: String,
    valueMono: Boolean = false,
) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
        AccentIcon(icon)
        Spacer(Modifier.width(12.dp))
        Text(label, color = AigriMuted, fontSize = 13.sp, modifier = Modifier.weight(1f))
        Text(
            value,
            color = AigriText,
            fontSize = 13.sp,
            fontWeight = FontWeight.W600,
            fontFamily = if (valueMono) MonoFontFamily else FontFamily.Default,
            maxLines = 1,
        )
    }
}

@Composable
private fun DangerButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    loading: Boolean = false,
) {
    Button(
        onClick = onClick,
        modifier = modifier,
        enabled = !loading,
        shape = RoundedCornerShape(Dimens.radiusSm),
        colors = ButtonDefaults.buttonColors(
            containerColor = AigriDanger,
            contentColor = Color.White,
            disabledContainerColor = AigriDanger.copy(alpha = 0.4f),
            disabledContentColor = Color.White.copy(alpha = 0.7f),
        ),
        border = BorderStroke(1.dp, AigriDanger.copy(alpha = 0.5f)),
    ) {
        if (loading) {
            CircularProgressIndicator(modifier = Modifier.size(18.dp), color = Color.White, strokeWidth = 2.dp)
        } else {
            Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
            Text(text, fontWeight = FontWeight.W700)
        }
    }
}
