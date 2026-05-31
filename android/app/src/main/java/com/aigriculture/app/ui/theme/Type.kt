package com.aigriculture.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontVariation
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import com.aigriculture.app.R

// Bundled to match the dashboard / Stitch design system 1:1:
//   UI text  -> Plus Jakarta Sans (variable wght 200-800)
//   data/mono-> JetBrains Mono     (variable wght 100-800)
// Both are variable fonts; each weight requests its wght axis explicitly so the
// render is deterministic on API 26+ (the app's minSdk).
private fun pjs(w: Int) = Font(
    R.font.plus_jakarta_sans,
    weight = FontWeight(w),
    variationSettings = FontVariation.Settings(FontVariation.weight(w)),
)

private fun jbm(w: Int) = Font(
    R.font.jetbrains_mono,
    weight = FontWeight(w),
    variationSettings = FontVariation.Settings(FontVariation.weight(w)),
)

val AppFontFamily = FontFamily(pjs(400), pjs(500), pjs(600), pjs(700), pjs(800))
val MonoFontFamily = FontFamily(jbm(400), jbm(500), jbm(700))

val AppTypography = Typography(
    headlineSmall = TextStyle(fontFamily = AppFontFamily, fontWeight = FontWeight.W800, fontSize = 22.sp),
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
