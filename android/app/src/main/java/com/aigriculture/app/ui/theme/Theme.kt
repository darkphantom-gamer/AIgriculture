package com.aigriculture.app.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable

// The dashboard's signature is its dark theme — the app forces it regardless of
// the system setting, so it looks identical on every phone.
private val AigriColorScheme = darkColorScheme(
    primary = AigriAccent,
    onPrimary = AigriOnAccent,
    secondary = AigriTealMd,
    onSecondary = AigriOnAccent,
    tertiary = AigriBlue,
    onTertiary = AigriOnAccent,
    background = AigriBg,
    onBackground = AigriText,
    surface = AigriCard,
    onSurface = AigriText,
    surfaceVariant = AigriSidebar,
    onSurfaceVariant = AigriMuted,
    outline = AigriBorder,
    outlineVariant = AigriBorder,
    error = AigriDanger,
    onError = AigriText,
)

@Composable
fun AigricultureTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = AigriColorScheme,
        typography = AppTypography,
        content = content,
    )
}
