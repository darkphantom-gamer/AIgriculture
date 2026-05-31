package com.aigriculture.app.ui.theme

import androidx.compose.ui.graphics.Color

// Exact tokens lifted from design/dashboard.html (:root + [data-theme="dark"]).
// Accent/teal/warn/danger are shared across light & dark; the rest are the dark set.
val AigriBg = Color(0xFF0D1B24)
val AigriBg2 = Color(0xFF0A1A24)
val AigriCard = Color(0xFF112233)
val AigriSidebar = Color(0xFF0B1F2A)
val AigriSidebarTop = Color(0xFF0D2234)
val AigriSidebarBot = Color(0xFF091A23)
val AigriText = Color(0xFFD4EEF5)
val AigriMuted = Color(0xFF4A7E92)
val AigriBorder = Color(0xFF1A3347)

val AigriTeal = Color(0xFF0D8A78)
val AigriTealLt = Color(0xFF0D2D28)
val AigriTealMd = Color(0xFF13B3A0)
val AigriTealDk = Color(0xFF096B5C)
val AigriAccent = Color(0xFF00CDB5)
val AigriBlue = Color(0xFF0EA5E9)
val AigriWarn = Color(0xFFF59E0B)
val AigriDanger = Color(0xFFEF4444)
val AigriOk = Color(0xFF22C55E)

// Readable ink to sit on the bright accent (buttons, pills).
val AigriOnAccent = Color(0xFF04222A)

// ── Stitch design-system extensions (same family, richer ramp) ───────────────
// The Stitch mock confirmed a 3-level background ramp and a two-tone accent:
//   AigriBgDeep  = deepest page base / gradient floor (#07151E)
//   AigriBg      = page surface (#0D1B24, above)         AigriBg2 = alt (#0A1A24)
//   AigriCard    = card surface (#112233, above)
// Accent is now two-tone: AigriAccent (#00CDB5) fills buttons/pills, while the
// brighter AigriAccentBright (#45EAD0) is used for accent TEXT, icons and glows;
// AigriAccentGlow (#32DEC5) seeds soft radial halos behind logos/avatars.
val AigriBgDeep = Color(0xFF07151E)
val AigriAccentBright = Color(0xFF45EAD0)
val AigriAccentGlow = Color(0xFF32DEC5)
val AigriAccentSoft = Color(0xFF72D8C3)
