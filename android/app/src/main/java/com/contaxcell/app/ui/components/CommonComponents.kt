package com.contaxcell.app.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AddCircleOutline
import androidx.compose.material.icons.outlined.ErrorOutline
import androidx.compose.material.icons.outlined.Info
import androidx.compose.material.icons.outlined.MoreHoriz
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.contaxcell.app.ui.CategoryShareUi
import com.contaxcell.app.ui.MessageKind
import com.contaxcell.app.ui.MetricTone
import com.contaxcell.app.ui.MetricUi
import com.contaxcell.app.ui.MonthSummaryUi
import com.contaxcell.app.ui.SelectableOption
import com.contaxcell.app.ui.QuotePointUi
import com.contaxcell.app.ui.UiMessage
import com.contaxcell.app.ui.theme.Expense
import com.contaxcell.app.ui.theme.ExpenseDark
import com.contaxcell.app.ui.theme.Income
import com.contaxcell.app.ui.theme.IncomeDark
import com.contaxcell.app.ui.theme.Investment
import com.contaxcell.app.ui.theme.InvestmentDark
import kotlin.math.max

val AppRadius = 14.dp
val ControlRadius = 10.dp

private const val MaxNumericLength = 20

/**
 * Money/decimal field that rejects invalid keystrokes instead of surfacing a
 * parse error after submission. It intentionally accepts pasted Spanish
 * formatting (spaces, euro sign, thousands dots and one decimal comma).
 */
@Composable
fun NumericTextField(
    value: String,
    onValueChange: (String) -> Unit,
    label: String,
    modifier: Modifier = Modifier,
    allowNegative: Boolean = false,
    suffix: String? = "\u20ac",
    supporting: String? = null,
    textStyle: TextStyle = MaterialTheme.typography.bodyLarge,
    imeAction: ImeAction = ImeAction.Done,
    enabled: Boolean = true,
) {
    OutlinedTextField(
        value = value,
        onValueChange = { proposed ->
            if (isAllowedNumber(proposed, allowNegative)) onValueChange(proposed)
        },
        modifier = modifier,
        label = { Text(label) },
        suffix = suffix?.let { text -> { Text(text) } },
        supportingText = supporting?.let { text -> { Text(text) } },
        textStyle = textStyle,
        singleLine = true,
        enabled = enabled,
        keyboardOptions = KeyboardOptions(
            keyboardType = if (allowNegative) KeyboardType.Number else KeyboardType.Decimal,
            imeAction = imeAction,
        ),
    )
}

fun isAllowedNumber(value: String, allowNegative: Boolean = false): Boolean {
    if (value.length > MaxNumericLength) return false
    val allowed = if (allowNegative) "0123456789.,\u20ac -" else "0123456789.,\u20ac "
    if (value.any { it !in allowed }) return false
    if (value.count { it == ',' } > 1) return false
    if (value.count { it == '-' } > 1) return false
    if ('-' in value && (!allowNegative || value.indexOf('-') != 0)) return false
    return true
}

@Composable
fun ScreenIntro(
    title: String,
    supporting: String,
    action: (@Composable () -> Unit)? = null,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(16.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.headlineLarge)
            Spacer(Modifier.height(4.dp))
            Text(
                supporting,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        action?.invoke()
    }
}

@Composable
fun SectionCard(
    title: String,
    modifier: Modifier = Modifier,
    supporting: String? = null,
    action: (@Composable () -> Unit)? = null,
    content: @Composable () -> Unit,
) {
    OutlinedCard(
        modifier = modifier,
        shape = RoundedCornerShape(AppRadius),
        colors = CardDefaults.outlinedCardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = androidx.compose.ui.graphics.SolidColor(MaterialTheme.colorScheme.outlineVariant),
        ),
    ) {
        Column(Modifier.padding(16.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(title, style = MaterialTheme.typography.titleLarge)
                    if (!supporting.isNullOrBlank()) {
                        Spacer(Modifier.height(2.dp))
                        Text(
                            supporting,
                            style = MaterialTheme.typography.bodyMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                action?.invoke()
            }
            Spacer(Modifier.height(14.dp))
            content()
        }
    }
}

@Composable
fun MetricGrid(metrics: List<MetricUi>, modifier: Modifier = Modifier) {
    BoxWithConstraints(modifier.fillMaxWidth()) {
        val columns = when {
            maxWidth >= 720.dp -> 4
            maxWidth >= 420.dp -> 2
            else -> 1
        }
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            metrics.chunked(columns).forEach { group ->
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    group.forEach { metric ->
                        MetricTile(metric, Modifier.weight(1f))
                    }
                    repeat(columns - group.size) { Spacer(Modifier.weight(1f)) }
                }
            }
        }
    }
}

@Composable
fun MetricTile(metric: MetricUi, modifier: Modifier = Modifier) {
    val tint = metricToneColor(metric.tone)
    Surface(
        modifier = modifier,
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.48f),
        shape = RoundedCornerShape(ControlRadius),
    ) {
        Column(Modifier.padding(12.dp)) {
            Text(
                metric.label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 2,
            )
            Spacer(Modifier.height(5.dp))
            Text(
                metric.value,
                style = MaterialTheme.typography.titleLarge,
                color = tint,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            if (metric.supporting.isNotBlank()) {
                Spacer(Modifier.height(2.dp))
                Text(
                    metric.supporting,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                )
            }
        }
    }
}

@Composable
fun metricToneColor(tone: MetricTone): Color {
    val dark = MaterialTheme.colorScheme.background.red < 0.15f
    return when (tone) {
        MetricTone.Positive -> if (dark) IncomeDark else Income
        MetricTone.Negative -> if (dark) ExpenseDark else Expense
        MetricTone.Investment -> if (dark) InvestmentDark else Investment
        MetricTone.Muted -> MaterialTheme.colorScheme.onSurfaceVariant
        MetricTone.Neutral -> MaterialTheme.colorScheme.onSurface
    }
}

@Composable
fun <T> CompactDropdown(
    label: String,
    selected: T?,
    options: List<T>,
    optionLabel: (T) -> String,
    onSelected: (T) -> Unit,
    modifier: Modifier = Modifier,
    emptyLabel: String = "Elegir",
) {
    var expanded by remember { mutableStateOf(false) }
    Box(modifier) {
        OutlinedButton(
            onClick = { expanded = true },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(ControlRadius),
        ) {
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.Start) {
                Text(
                    label,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(
                    selected?.let(optionLabel) ?: emptyLabel,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Icon(Icons.Outlined.MoreHoriz, contentDescription = "Abrir $label")
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            options.forEach { option ->
                DropdownMenuItem(
                    text = { Text(optionLabel(option)) },
                    onClick = {
                        expanded = false
                        onSelected(option)
                    },
                )
            }
        }
    }
}

@Composable
fun OptionChips(
    options: List<SelectableOption>,
    selectedId: String?,
    onSelected: (String?) -> Unit,
    includeAll: Boolean = true,
    allLabel: String = "Todas",
) {
    Row(
        Modifier.fillMaxWidth().horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        if (includeAll) {
            AssistChip(onClick = { onSelected(null) }, label = { Text(allLabel) })
        }
        options.forEach { option ->
            val selected = option.id == selectedId
            AssistChip(
                onClick = { onSelected(option.id) },
                label = { Text(option.label) },
                leadingIcon = if (selected) {
                    { Box(Modifier.size(7.dp).background(MaterialTheme.colorScheme.primary, CircleShape)) }
                } else null,
            )
        }
    }
}

@Composable
fun InlineProgress(
    fraction: Float,
    modifier: Modifier = Modifier,
    over: Boolean = false,
    label: String? = null,
) {
    val color = if (over) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.primary
    Column(modifier) {
        if (label != null) {
            Text(label, style = MaterialTheme.typography.labelMedium, color = color)
            Spacer(Modifier.height(4.dp))
        }
        Box(
            Modifier.fillMaxWidth().height(6.dp)
                .background(MaterialTheme.colorScheme.surfaceVariant, CircleShape),
        ) {
            Box(
                Modifier.fillMaxWidth(fraction.coerceIn(0f, 1f)).height(6.dp)
                    .background(color, CircleShape),
            )
        }
    }
}

@Composable
fun EmptyState(
    title: String,
    detail: String,
    modifier: Modifier = Modifier,
    actionLabel: String? = null,
    onAction: (() -> Unit)? = null,
) {
    Column(
        modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 36.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            Icons.Outlined.AddCircleOutline,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(32.dp),
        )
        Spacer(Modifier.height(12.dp))
        Text(title, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(4.dp))
        Text(
            detail,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        if (actionLabel != null && onAction != null) {
            Spacer(Modifier.height(14.dp))
            OutlinedButton(onClick = onAction) { Text(actionLabel) }
        }
    }
}

@Composable
fun LoadingState(label: String = "Cargando") {
    Row(
        Modifier.fillMaxWidth().padding(32.dp),
        horizontalArrangement = Arrangement.Center,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
        Spacer(Modifier.width(10.dp))
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun MessageBanner(message: UiMessage, onDismiss: () -> Unit, modifier: Modifier = Modifier) {
    val tone = when (message.kind) {
        MessageKind.Success -> metricToneColor(MetricTone.Positive)
        MessageKind.Error -> MaterialTheme.colorScheme.error
        MessageKind.Warning -> Color(0xFFB54708)
        MessageKind.Info -> MaterialTheme.colorScheme.primary
    }
    Row(
        modifier.fillMaxWidth()
            .background(tone.copy(alpha = 0.10f), RoundedCornerShape(ControlRadius))
            .border(1.dp, tone.copy(alpha = 0.3f), RoundedCornerShape(ControlRadius))
            .padding(start = 12.dp, top = 8.dp, bottom = 8.dp, end = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(
            if (message.kind == MessageKind.Error) Icons.Outlined.ErrorOutline else Icons.Outlined.Info,
            contentDescription = null,
            tint = tone,
            modifier = Modifier.size(20.dp),
        )
        Spacer(Modifier.width(8.dp))
        Text(message.text, Modifier.weight(1f), style = MaterialTheme.typography.bodyMedium)
        IconButton(onClick = onDismiss) {
            Icon(Icons.Outlined.MoreHoriz, contentDescription = "Cerrar aviso")
        }
    }
}

@Composable
fun MonthlyBarChart(months: List<MonthSummaryUi>, modifier: Modifier = Modifier) {
    if (months.isEmpty()) return
    val incomeColor = metricToneColor(MetricTone.Positive)
    val expenseColor = metricToneColor(MetricTone.Negative)
    val investmentColor = metricToneColor(MetricTone.Investment)
    val gridColor = MaterialTheme.colorScheme.outlineVariant
    val maxValue = months.maxOfOrNull { max(it.income, max(it.expenses, it.investment)) }
        ?.coerceAtLeast(1.0) ?: 1.0
    Canvas(
        modifier.fillMaxWidth().height(190.dp)
            .semantics { contentDescription = "Gr\u00e1fico mensual de ingresos, gastos e inversi\u00f3n" },
    ) {
        repeat(4) { index ->
            val y = size.height * index / 3f
            drawLine(gridColor, Offset(0f, y), Offset(size.width, y), 1.dp.toPx())
        }
        val groupWidth = size.width / months.size
        val barWidth = (groupWidth * 0.18f).coerceAtMost(10.dp.toPx())
        months.forEachIndexed { index, month ->
            val center = groupWidth * (index + .5f)
            listOf(month.income to incomeColor, month.expenses to expenseColor, month.investment to investmentColor)
                .forEachIndexed { bar, (value, color) ->
                    val h = (value / maxValue * (size.height - 10.dp.toPx())).toFloat()
                    drawRoundRect(
                        color = color,
                        topLeft = Offset(center + (bar - 1) * (barWidth + 1.dp.toPx()) - barWidth / 2, size.height - h),
                        size = Size(barWidth, h),
                        cornerRadius = androidx.compose.ui.geometry.CornerRadius(3.dp.toPx()),
                    )
                }
        }
    }
}

@Composable
fun PortfolioLineChart(history: List<com.contaxcell.app.ui.PortfolioHistoryUi>, modifier: Modifier = Modifier) {
    if (history.size < 2) return
    val marketColor = MaterialTheme.colorScheme.primary
    val contributedColor = MaterialTheme.colorScheme.onSurfaceVariant
    val gridColor = MaterialTheme.colorScheme.outlineVariant
    val values = history.flatMap { listOf(it.marketValue, it.contributedValue) }
    val min = values.minOrNull() ?: 0.0
    val max = (values.maxOrNull() ?: 1.0).let { if (it == min) it + 1 else it }
    Canvas(
        modifier.fillMaxWidth().height(180.dp)
            .semantics { contentDescription = "Evoluci\u00f3n del valor de la cartera y de lo aportado" },
    ) {
        repeat(4) { index ->
            val y = size.height * index / 3f
            drawLine(gridColor, Offset(0f, y), Offset(size.width, y), 1.dp.toPx())
        }
        fun point(index: Int, value: Double): Offset {
            val x = size.width * index / (history.size - 1)
            val y = size.height - ((value - min) / (max - min) * size.height).toFloat()
            return Offset(x, y)
        }
        for (index in 0 until history.lastIndex) {
            drawLine(
                marketColor,
                point(index, history[index].marketValue),
                point(index + 1, history[index + 1].marketValue),
                3.dp.toPx(),
                StrokeCap.Round,
            )
            drawLine(
                contributedColor,
                point(index, history[index].contributedValue),
                point(index + 1, history[index + 1].contributedValue),
                2.dp.toPx(),
                StrokeCap.Round,
            )
        }
    }
}

@Composable
fun QuoteLineChart(
    history: List<QuotePointUi>,
    modifier: Modifier = Modifier,
    averagePaid: Double? = null,
) {
    if (history.size < 2) return
    val quoteColor = MaterialTheme.colorScheme.primary
    val averageColor = metricToneColor(MetricTone.Investment)
    val gridColor = MaterialTheme.colorScheme.outlineVariant
    val values = history.map { it.value } + listOfNotNull(averagePaid)
    val minValue = values.minOrNull() ?: 0.0
    val maxValue = (values.maxOrNull() ?: 1.0).let { if (it == minValue) it + 1.0 else it }
    Canvas(
        modifier.fillMaxWidth().height(172.dp)
            .semantics { contentDescription = "Evoluci\u00f3n de la cotizaci\u00f3n y precio medio pagado" },
    ) {
        repeat(4) { index ->
            val y = size.height * index / 3f
            drawLine(gridColor, Offset(0f, y), Offset(size.width, y), 1.dp.toPx())
        }
        fun point(index: Int, value: Double): Offset {
            val x = size.width * index / history.lastIndex
            val y = size.height - ((value - minValue) / (maxValue - minValue) * size.height).toFloat()
            return Offset(x, y)
        }
        for (index in 0 until history.lastIndex) {
            drawLine(
                quoteColor,
                point(index, history[index].value),
                point(index + 1, history[index + 1].value),
                3.dp.toPx(),
                StrokeCap.Round,
            )
        }
        averagePaid?.let { paid ->
            val y = point(0, paid).y
            drawLine(averageColor, Offset(0f, y), Offset(size.width, y), 2.dp.toPx(), StrokeCap.Round)
        }
    }
}

@Composable
fun DonutShare(share: CategoryShareUi, modifier: Modifier = Modifier, diameter: Dp = 42.dp) {
    val primary = MaterialTheme.colorScheme.primary
    val track = MaterialTheme.colorScheme.surfaceVariant
    Canvas(
        modifier.size(diameter).then(modifier)
            .semantics { contentDescription = "${share.name}: ${share.percent}" },
    ) {
        drawArc(track, -90f, 360f, false, style = Stroke(6.dp.toPx(), cap = StrokeCap.Round))
        drawArc(
            primary,
            -90f,
            360f * share.fraction.coerceIn(0f, 1f),
            false,
            style = Stroke(6.dp.toPx(), cap = StrokeCap.Round),
        )
    }
}
