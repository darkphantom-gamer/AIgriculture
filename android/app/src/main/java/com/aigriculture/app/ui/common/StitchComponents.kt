package com.aigriculture.app.ui.common

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriAccentBright
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriCard
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.Dimens

/**
 * Reusable primitives lifted from the Stitch design system (circular gauges,
 * stat tiles, status pills, top-accent cards). These match the existing dark
 * palette/shape language in [AigriCard] etc. — they're the polished layer the
 * Stitch mocks add on top of the same tokens, not a new theme.
 */

/** Circular progress ring (Status global moisture + per-sector % badges). */
@Composable
fun GaugeRing(
    progress: Float,
    modifier: Modifier = Modifier,
    diameter: Dp = 160.dp,
    stroke: Dp = 14.dp,
    arcStart: Color = AigriAccent,
    arcEnd: Color = AigriAccentBright,
    trackColor: Color = AigriBorder,
    center: @Composable () -> Unit = {},
) {
    Box(modifier = modifier.size(diameter), contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.size(diameter)) {
            val sw = stroke.toPx()
            val inset = sw / 2f
            val arcSize = Size(size.width - sw, size.height - sw)
            val topLeft = Offset(inset, inset)
            drawArc(
                color = trackColor,
                startAngle = -90f,
                sweepAngle = 360f,
                useCenter = false,
                topLeft = topLeft,
                size = arcSize,
                style = Stroke(width = sw, cap = StrokeCap.Round),
            )
            val sweep = progress.coerceIn(0f, 1f) * 360f
            if (sweep > 0f) {
                drawArc(
                    brush = Brush.sweepGradient(listOf(arcStart, arcEnd, arcStart)),
                    startAngle = -90f,
                    sweepAngle = sweep,
                    useCenter = false,
                    topLeft = topLeft,
                    size = arcSize,
                    style = Stroke(width = sw, cap = StrokeCap.Round),
                )
            }
        }
        center()
    }
}

/** Gauge with a centered value + optional caption (e.g. "68%" / "GLOBAL"). */
@Composable
fun GaugeValue(
    progress: Float,
    valueText: String,
    modifier: Modifier = Modifier,
    caption: String? = null,
    diameter: Dp = 160.dp,
    stroke: Dp = 14.dp,
    valueSize: Int = 30,
) {
    GaugeRing(progress, modifier, diameter, stroke) {
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(valueText, color = AigriText, fontWeight = FontWeight.W800, fontSize = valueSize.sp)
            if (caption != null) {
                Text(
                    caption.uppercase(),
                    color = AigriMuted,
                    fontSize = 9.sp,
                    letterSpacing = 1.5.sp,
                    fontWeight = FontWeight.W600,
                )
            }
        }
    }
}

/** Small stat tile: big value + uppercase caption (Status overview strip). */
@Composable
fun StatTile(
    value: String,
    label: String,
    modifier: Modifier = Modifier,
    accent: Color = AigriText,
) {
    AigriCard(modifier, padding = PaddingValues(14.dp)) {
        Text(value, color = accent, fontWeight = FontWeight.W800, fontSize = 20.sp, maxLines = 1)
        Spacer(Modifier.height(2.dp))
        Text(
            label.uppercase(),
            color = AigriMuted,
            fontSize = 9.sp,
            letterSpacing = 1.sp,
            fontWeight = FontWeight.W600,
            maxLines = 1,
        )
    }
}

/** Rounded status pill with an optional leading dot ("Online", "Just now", "REC"). */
@Composable
fun Pill(
    text: String,
    modifier: Modifier = Modifier,
    dotColor: Color? = null,
    bg: Color = AigriCard,
    fg: Color = AigriMuted,
    border: Color = AigriBorder,
) {
    Row(
        modifier = modifier
            .clip(RoundedCornerShape(50))
            .background(bg)
            .border(1.dp, border, RoundedCornerShape(50))
            .padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (dotColor != null) Box(Modifier.size(7.dp).background(dotColor, CircleShape))
        Text(text, color = fg, fontSize = 11.sp, fontWeight = FontWeight.W600, maxLines = 1)
    }
}

/** Card with the Stitch teal top-accent hairline (Connect / hero cards). */
@Composable
fun AccentCard(
    modifier: Modifier = Modifier,
    padding: PaddingValues = PaddingValues(Dimens.cardPad),
    content: @Composable ColumnScope.() -> Unit,
) {
    Surface(
        modifier = modifier,
        color = AigriCard,
        contentColor = AigriText,
        shape = RoundedCornerShape(Dimens.radius),
        border = BorderStroke(1.dp, AigriBorder),
    ) {
        Column {
            Box(
                Modifier
                    .fillMaxWidth()
                    .height(3.dp)
                    .background(Brush.horizontalGradient(listOf(AigriAccent, AigriAccentBright)))
            )
            Column(modifier = Modifier.padding(padding), content = content)
        }
    }
}
