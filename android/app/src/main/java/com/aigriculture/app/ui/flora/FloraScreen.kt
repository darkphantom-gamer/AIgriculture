package com.aigriculture.app.ui.flora

import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.aigriculture.app.data.net.ScheduleTask
import com.aigriculture.app.ui.common.AigriTextField
import com.aigriculture.app.ui.theme.AigriAccent
import com.aigriculture.app.ui.theme.AigriBg
import com.aigriculture.app.ui.theme.AigriBorder
import com.aigriculture.app.ui.theme.AigriCard
import com.aigriculture.app.ui.theme.AigriMuted
import com.aigriculture.app.ui.theme.AigriOk
import com.aigriculture.app.ui.theme.AigriOnAccent
import com.aigriculture.app.ui.theme.AigriSidebar
import com.aigriculture.app.ui.theme.AigriTeal
import com.aigriculture.app.ui.theme.AigriText

@Composable
fun FloraScreen(vm: FloraViewModel = viewModel()) {
    val ui by vm.ui.collectAsState()
    val listState = rememberLazyListState()
    LaunchedEffect(ui.messages.size, ui.typing) {
        val count = ui.messages.size + if (ui.typing) 1 else 0
        if (count > 0) listState.animateScrollToItem(count - 1)
    }

    Column(modifier = Modifier.fillMaxSize().background(AigriBg)) {
        FloraHeader(mode = ui.mode, connected = ui.connected, onMode = vm::setMode)
        LazyColumn(
            state = listState,
            modifier = Modifier.weight(1f).fillMaxWidth(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            items(ui.messages, key = { it.id }) { Bubble(it) }
            if (ui.typing) item(key = "typing") { TypingBubble() }
        }
        ScheduleBar(tasks = ui.schedule, open = ui.scheduleOpen, onToggle = vm::toggleSchedule)
        InputBar(value = ui.input, onChange = vm::onInput, onSend = vm::send)
    }
}

@Composable
private fun ScheduleBar(tasks: List<ScheduleTask>, open: Boolean, onToggle: () -> Unit) {
    Surface(color = AigriSidebar, contentColor = AigriText) {
        Column(Modifier.fillMaxWidth()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onToggle)
                    .padding(horizontal = 16.dp, vertical = 10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("📅", fontSize = 13.sp)
                Spacer(Modifier.size(8.dp))
                Text("Scheduled Tasks", color = AigriText, fontWeight = FontWeight.W700, fontSize = 13.sp)
                Spacer(Modifier.size(6.dp))
                if (tasks.isNotEmpty()) {
                    Box(
                        Modifier
                            .clip(RoundedCornerShape(50))
                            .background(AigriAccent)
                            .padding(horizontal = 7.dp, vertical = 1.dp),
                    ) {
                        Text("${tasks.size}", color = AigriOnAccent, fontSize = 10.sp, fontWeight = FontWeight.W700)
                    }
                }
                Spacer(Modifier.weight(1f))
                Text(if (open) "▾" else "▸", color = AigriMuted, fontSize = 13.sp)
            }
            if (open) {
                if (tasks.isEmpty()) {
                    Text(
                        "No scheduled tasks — ask FLORA to schedule something.",
                        color = AigriMuted, fontSize = 12.sp,
                        modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp),
                    )
                } else {
                    Column(Modifier.padding(start = 16.dp, end = 16.dp, bottom = 10.dp)) {
                        tasks.take(8).forEach { ScheduleRow(it) }
                    }
                }
            }
        }
    }
}

@Composable
private fun ScheduleRow(t: ScheduleTask) {
    Row(
        modifier = Modifier.fillMaxWidth().padding(vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(6.dp).background(AigriAccent, CircleShape))
        Spacer(Modifier.size(8.dp))
        Column(Modifier.weight(1f)) {
            Text(
                (t.tool_name ?: "task").replace('_', ' ').replaceFirstChar { it.uppercase() },
                color = AigriText, fontSize = 12.sp, fontWeight = FontWeight.W600,
            )
            Text(
                ((t.run_at ?: t.run_at_iso).ifBlank { "—" }) + "  ·  " + t.repeat,
                color = AigriMuted, fontSize = 10.sp,
            )
        }
    }
}

@Composable
private fun FloraHeader(mode: String, connected: Boolean, onMode: (String) -> Unit) {
    Surface(color = AigriSidebar, contentColor = AigriText) {
        Column {
            Row(
                modifier = Modifier.fillMaxWidth().padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(
                    modifier = Modifier.size(34.dp).background(AigriTeal, CircleShape),
                    contentAlignment = Alignment.Center,
                ) { Text("🌿", fontSize = 16.sp) }
                Column(modifier = Modifier.padding(start = 10.dp).weight(1f)) {
                    Text("FLORA Intelligence", color = AigriText, fontWeight = FontWeight.W700, fontSize = 14.sp)
                    Text("Farm Live Operation and Reasoning Assistant", color = AigriMuted, fontSize = 10.sp)
                }
                Box(
                    modifier = Modifier.size(8.dp)
                        .background(if (connected) AigriOk else AigriMuted, CircleShape)
                )
            }
            Row(modifier = Modifier.padding(start = 16.dp, end = 16.dp, bottom = 12.dp)) {
                ModeChip("Cloud", mode == "cloud") { onMode("cloud") }
                Box(modifier = Modifier.size(8.dp))
                ModeChip("Offline", mode == "offline") { onMode("offline") }
            }
        }
    }
}

@Composable
private fun ModeChip(label: String, active: Boolean, onClick: () -> Unit) {
    val shape = RoundedCornerShape(50)
    Box(
        modifier = Modifier
            .clip(shape)
            .then(
                if (active) Modifier.background(AigriAccent)
                else Modifier.border(1.dp, AigriBorder, shape)
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 6.dp),
    ) {
        Text(
            label,
            color = if (active) AigriOnAccent else AigriMuted,
            fontSize = 12.sp,
            fontWeight = FontWeight.W600,
        )
    }
}

@Composable
private fun Bubble(m: ChatMsg) {
    when (m.role) {
        Role.SYS -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Center) {
            Text(m.text, color = AigriMuted, fontSize = 12.sp)
        }
        Role.USER -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            BubbleBox(m.text, AigriTeal, Color.White, end = true)
        }
        Role.FLORA -> Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
            BubbleBox(m.text, AigriCard, AigriText, end = false)
        }
    }
}

@Composable
private fun BubbleBox(text: String, bg: Color, fg: Color, end: Boolean) {
    Surface(
        modifier = Modifier.widthIn(max = 320.dp),
        color = bg,
        contentColor = fg,
        shape = RoundedCornerShape(
            topStart = 14.dp, topEnd = 14.dp,
            bottomStart = if (end) 14.dp else 3.dp,
            bottomEnd = if (end) 3.dp else 14.dp,
        ),
        border = if (end) null else BorderStroke(1.dp, AigriBorder),
    ) {
        Text(text, modifier = Modifier.padding(horizontal = 13.dp, vertical = 9.dp), fontSize = 14.sp)
    }
}

@Composable
private fun TypingBubble() {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.Start) {
        Surface(
            color = AigriCard,
            contentColor = AigriMuted,
            shape = RoundedCornerShape(14.dp),
            border = BorderStroke(1.dp, AigriBorder),
        ) {
            Text("FLORA is typing…", modifier = Modifier.padding(horizontal = 13.dp, vertical = 9.dp), fontSize = 13.sp)
        }
    }
}

@Composable
private fun InputBar(value: String, onChange: (String) -> Unit, onSend: () -> Unit) {
    Surface(color = AigriSidebar) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.Bottom,
        ) {
            AigriTextField(
                value = value,
                onValueChange = onChange,
                label = "Message FLORA…",
                modifier = Modifier.weight(1f),
                singleLine = false,
            )
            Box(modifier = Modifier.padding(start = 8.dp)) {
                IconButton(
                    onClick = onSend,
                    modifier = Modifier.size(48.dp).background(AigriAccent, CircleShape),
                ) {
                    Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send", tint = AigriOnAccent)
                }
            }
        }
    }
}
