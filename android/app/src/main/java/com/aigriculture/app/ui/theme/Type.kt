package com.aigriculture.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// TODO(polish): swap AppFontFamily to bundled Plus Jakarta Sans for byte-exact
// type. The dashboard uses Plus Jakarta Sans (weights 300-800) + JetBrains Mono.
// Visual language (color/shape/weight) already matches; typeface is a polish item.
val AppFontFamily = FontFamily.Default
val MonoFontFamily = FontFamily.Monospace

val AppTypography = Typography(
    headlineSmall = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W700, fontSize = 20.sp),
    titleLarge = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W700, fontSize = 18.sp),
    titleMedium = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W600, fontSize = 15.sp),
    titleSmall = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W600, fontSize = 13.sp),
    bodyLarge = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W400, fontSize = 14.sp),
    bodyMedium = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W400, fontSize = 13.sp),
    bodySmall = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W400, fontSize = 12.sp),
    labelLarge = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W600, fontSize = 13.sp),
    labelMedium = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W600, fontSize = 12.sp),
    labelSmall = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W600, fontSize = 11.sp),
)
