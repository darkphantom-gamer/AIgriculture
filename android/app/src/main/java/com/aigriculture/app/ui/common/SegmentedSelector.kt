package com.aigriculture.app.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriCard
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOnAccent
import com.aigriculture.app.ui.theme.Dimens

/**
 * A pill segmented control — the mobile twist on the web sidebar's expandable
 * sub-items (Live Camera → Security/Farm, Analytics → Moisture/Security/Health).
 */
@Composable
fun SegmentedSelector(
    options: List<String>,
    selected: Int,
    onSelect: (Int) -> Unit,
    modifier: Modifier = Modifier,
) {
    Row(
        modifier = modifier
            .clip(RoundedCornerShape(Dimens.radiusSm))
            .background(AigriCard)
            .border(1.dp, AigriBorder, RoundedCornerShape(Dimens.radiusSm))
            .padding(3.dp),
        horizontalArrangement = Arrangement.spacedBy(3.dp),
    ) {
        options.forEachIndexed { i, label ->
            val active = i == selected
            Box(
                modifier = Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(8.dp))
                    .background(if (active) AigriAccent else Color.Transparent)
                    .clickable { onSelect(i) }
                    .padding(vertical = 8.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    label,
                    color = if (active) AigriOnAccent else AigriMuted,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.W700,
                    maxLines = 1,
                )
            }
        }
    }
}
