package com.aigriculture.app.ui.common

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriCard
import com.aigriculture.app.ui.theme.AigriDanger
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOnAccent
import com.aigriculture.app.ui.theme.AigriTeal
import com.aigriculture.app.ui.theme.AigriText
import com.aigriculture.app.ui.theme.Dimens

/** The dashboard logo: gradient rounded tile + "AI"-accented wordmark. */
@Composable
fun BrandHeader(subtitle: String? = null) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Box(
            modifier = Modifier
                .size(38.dp)
                .background(
                    brush = Brush.linearGradient(listOf(AigriTeal, AigriAccent)),
                    shape = RoundedCornerShape(11.dp)
                ),
            contentAlignment = Alignment.Center
        ) { Text("🌱", fontSize = 18.sp) }
        Column(modifier = Modifier.padding(start = 11.dp)) {
            Row {
                Text("AI", color = AigriAccent, fontWeight = FontWeight.W800, fontSize = 17.sp)
                Text("griculture", color = AigriText, fontWeight = FontWeight.W800, fontSize = 17.sp)
            }
            if (subtitle != null) {
                Text(
                    subtitle.uppercase(),
                    color = AigriMuted,
                    fontSize = 10.sp,
                    letterSpacing = 2.sp,
                    fontWeight = FontWeight.W600,
                )
            }
        }
    }
}

@Composable
fun AigriCard(
    modifier: Modifier = Modifier,
    padding: PaddingValues = PaddingValues(Dimens.cardPad),
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier,
        color = AigriCard,
        contentColor = AigriText,
        shape = RoundedCornerShape(Dimens.radius),
        border = BorderStroke(1.dp, AigriBorder),
    ) {
        Column(modifier = Modifier.padding(padding)) { content() }
    }
}

@Composable
fun PrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    loading: Boolean = false,
) {
    Button(
        onClick = onClick,
        modifier = modifier,
        enabled = enabled && !loading,
        shape = RoundedCornerShape(Dimens.radiusSm),
        colors = ButtonDefaults.buttonColors(
            containerColor = AigriAccent,
            contentColor = AigriOnAccent,
            disabledContainerColor = AigriBorder,
            disabledContentColor = AigriMuted,
        ),
    ) {
        if (loading) {
            CircularProgressIndicator(
                modifier = Modifier.size(18.dp),
                color = AigriOnAccent,
                strokeWidth = 2.dp,
            )
        } else {
            Text(text, fontWeight = FontWeight.W700)
        }
    }
}

@Composable
fun AigriTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    isPassword: Boolean = false,
    keyboardType: KeyboardType = KeyboardType.Text,
    singleLine: Boolean = true,
) {
    OutlinedTextField(
        value = value,
        onValueChange = onValueChange,
        modifier = modifier,
        label = { Text(label) },
        singleLine = singleLine,
        visualTransformation = if (isPassword) PasswordVisualTransformation() else VisualTransformation.None,
        shape = RoundedCornerShape(Dimens.radiusSm),
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
}

@Composable
fun ErrorBanner(text: String, modifier: Modifier = Modifier) {
    Surface(
        modifier = modifier,
        color = AigriDanger.copy(alpha = 0.14f),
        contentColor = AigriDanger,
        shape = RoundedCornerShape(Dimens.radiusSm),
        border = BorderStroke(1.dp, AigriDanger.copy(alpha = 0.4f)),
    ) {
        Text(
            text,
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
            fontSize = 13.sp,
        )
    }
}

@Composable
fun StatusDot(color: androidx.compose.ui.graphics.Color, size: Int = 8) {
    Box(
        modifier = Modifier
            .size(size.dp)
            .background(color, CircleShape)
    )
}

@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(
        text.uppercase(),
        modifier = modifier,
        color = AigriMuted,
        fontSize = 11.sp,
        letterSpacing = 2.sp,
        fontWeight = FontWeight.W700,
    )
}
