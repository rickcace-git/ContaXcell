package com.contaxcell.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.FileUpload
import androidx.compose.material.icons.outlined.Refresh
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.PrimaryTabRow
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.contaxcell.app.ui.AppAction
import com.contaxcell.app.ui.AssetDraft
import com.contaxcell.app.ui.AssetUi
import com.contaxcell.app.ui.BudgetRowUi
import com.contaxcell.app.ui.BudgetsUiState
import com.contaxcell.app.ui.CashbackUi
import com.contaxcell.app.ui.CategoryShareUi
import com.contaxcell.app.ui.InvestmentsUiState
import com.contaxcell.app.ui.MonthSummaryUi
import com.contaxcell.app.ui.PortfolioHistoryUi
import com.contaxcell.app.ui.QuoteSearchUiState
import com.contaxcell.app.ui.SummaryUiState
import com.contaxcell.app.ui.SummaryMode
import com.contaxcell.app.ui.SelectableOption
import com.contaxcell.app.ui.components.CompactDropdown
import com.contaxcell.app.ui.components.DonutShare
import com.contaxcell.app.ui.components.EmptyState
import com.contaxcell.app.ui.components.InlineProgress
import com.contaxcell.app.ui.components.MetricGrid
import com.contaxcell.app.ui.components.MonthlyBarChart
import com.contaxcell.app.ui.components.NumericTextField
import com.contaxcell.app.ui.components.PortfolioLineChart
import com.contaxcell.app.ui.components.QuoteLineChart
import com.contaxcell.app.ui.components.ScreenIntro
import com.contaxcell.app.ui.components.SectionCard

@Composable
fun SummaryScreen(state: SummaryUiState, onAction: (AppAction) -> Unit) {
    val fallbackOptions = state.availableYears.map { SelectableOption(it.toString(), it.toString()) }
    val selectorOptions = state.selectorOptions.ifEmpty { fallbackOptions }
    val selectedId = state.selectionId.ifBlank { state.year.takeIf { it > 0 }?.toString().orEmpty() }
    val selectedPeriod = selectorOptions.firstOrNull { it.id == selectedId }
    val periodLabel = state.periodLabel.ifBlank {
        selectedPeriod?.label ?: state.year.takeIf { it > 0 }?.toString().orEmpty()
    }
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            ScreenIntro(
                title = if (periodLabel.isNotBlank()) "Resumen de $periodLabel" else "Resumen",
                supporting = "Ahorro, gasto, inversi\u00f3n y patrimonio en el periodo que elijas.",
            )
        }
        item {
            SectionCard("Periodo") {
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    listOf(
                        SummaryMode.SingleYear to "Un a\u00f1o",
                        SummaryMode.MultipleYears to "Varios a\u00f1os",
                        SummaryMode.SingleMonth to "Un mes",
                    ).forEachIndexed { index, option ->
                        SegmentedButton(
                            selected = state.mode == option.first,
                            onClick = { onAction(AppAction.SelectSummaryMode(option.first)) },
                            shape = SegmentedButtonDefaults.itemShape(index, 3),
                        ) { Text(option.second, maxLines = 1) }
                    }
                }
                if (selectorOptions.isNotEmpty()) {
                    Spacer(Modifier.height(10.dp))
                    CompactDropdown(
                        label = when (state.mode) {
                            SummaryMode.SingleYear -> "A\u00f1o"
                            SummaryMode.MultipleYears -> "Cu\u00e1ntos"
                            SummaryMode.SingleMonth -> "Mes"
                        },
                        selected = selectedPeriod,
                        options = selectorOptions,
                        optionLabel = { it.label },
                        onSelected = { selected ->
                            if (state.selectorOptions.isEmpty() && state.mode == SummaryMode.SingleYear) {
                                selected.id.toIntOrNull()?.let { onAction(AppAction.SelectSummaryYear(it)) }
                            } else {
                                onAction(AppAction.SelectSummaryPeriod(selected.id))
                            }
                        },
                    )
                }
            }
        }
        if (state.empty) {
            item { EmptyState("No hay datos en este periodo", "Elige otro periodo o empieza a apuntar.") }
        } else {
            item { MetricGrid(state.metrics) }
            if (state.showTrend && state.months.size > 1) item {
                SectionCard(state.trendTitle, supporting = "Ingresos, gastos e inversi\u00f3n") {
                    MonthlyBarChart(state.months)
                    ChartLegend()
                    Spacer(Modifier.height(10.dp))
                    MonthTable(state.months)
                }
            }
            item {
                BoxWithConstraints {
                    if (maxWidth >= 720.dp) {
                        Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                            ShareCard("En qu\u00e9 se va el dinero", state.expenses, Modifier.weight(1f))
                            ShareCard("De d\u00f3nde viene", state.income, Modifier.weight(1f))
                        }
                    } else {
                        Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                            ShareCard("En qu\u00e9 se va el dinero", state.expenses)
                            ShareCard("De d\u00f3nde viene", state.income)
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ChartLegend() {
    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        Text("Ingresos", color = com.contaxcell.app.ui.components.metricToneColor(com.contaxcell.app.ui.MetricTone.Positive), style = MaterialTheme.typography.labelMedium)
        Text("Gastos", color = com.contaxcell.app.ui.components.metricToneColor(com.contaxcell.app.ui.MetricTone.Negative), style = MaterialTheme.typography.labelMedium)
        Text("Inversi\u00f3n", color = com.contaxcell.app.ui.components.metricToneColor(com.contaxcell.app.ui.MetricTone.Investment), style = MaterialTheme.typography.labelMedium)
    }
}

@Composable
private fun MonthTable(months: List<MonthSummaryUi>) {
    Column {
        months.forEachIndexed { index, month ->
            Row(Modifier.fillMaxWidth().padding(vertical = 9.dp), verticalAlignment = Alignment.CenterVertically) {
                Text(month.label, Modifier.weight(1f), style = MaterialTheme.typography.titleMedium)
                Column(horizontalAlignment = Alignment.End) {
                    Text(month.expensesLabel.ifBlank { "Sin gasto" }, style = MaterialTheme.typography.bodyMedium)
                    Text(
                        "Ahorro ${month.savingsLabel.ifBlank { "sin datos" }}  Saldo ${month.endBalanceLabel.ifBlank { "sin datos" }}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            if (index != months.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
        }
    }
}

@Composable
private fun ShareCard(title: String, rows: List<CategoryShareUi>, modifier: Modifier = Modifier) {
    SectionCard(title, modifier) {
        if (rows.isEmpty()) {
            EmptyState("Sin datos", "Todav\u00eda no hay movimientos en este grupo.")
        } else {
            rows.take(8).forEachIndexed { index, row ->
                Row(
                    Modifier.fillMaxWidth().padding(vertical = 7.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    DonutShare(row)
                    Column(Modifier.weight(1f)) {
                        Text(row.name, style = MaterialTheme.typography.titleMedium)
                        Text(row.percent, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    Text(row.amount, fontWeight = FontWeight.SemiBold)
                }
                if (index != rows.take(8).lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
            }
        }
    }
}

@Composable
fun BudgetsScreen(state: BudgetsUiState, onAction: (AppAction) -> Unit) {
    val selectedMonth = state.months.firstOrNull { it.id == state.monthId }
    var editing by remember { mutableStateOf<BudgetRowUi?>(null) }
    var editingGoal by remember { mutableStateOf(false) }
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            ScreenIntro(
                "Presupuesto",
                "Un tope mensual por categor\u00eda, con el gasto real al lado.",
                action = {
                    CompactDropdown(
                        "Mes",
                        selectedMonth,
                        state.months,
                        { it.label },
                        { onAction(AppAction.SelectBudgetMonth(it.id)) },
                        Modifier.width(160.dp),
                    )
                },
            )
        }
        item { MetricGrid(state.metrics) }
        item {
            SectionCard("Presupuesto de ${state.monthLabel}", supporting = "Pulsa una categor\u00eda para cambiar su tope.") {
                if (state.rows.isEmpty()) {
                    EmptyState("No hay categor\u00edas de gasto", "Cr\u00e9alas en Ajustes para ponerles un tope.")
                } else {
                    state.rows.forEachIndexed { index, row ->
                        BudgetRow(row) { editing = row }
                        if (index != state.rows.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                    }
                }
            }
        }
        item {
            SectionCard(
                "Objetivo de inversi\u00f3n",
                supporting = "La inversi\u00f3n sale del banco, pero no cuenta como gasto.",
                action = { TextButton(onClick = { editingGoal = true }) { Text("Cambiar") } },
            ) {
                MetricGrid(state.investmentMetrics)
            }
        }
    }
    editing?.let { row ->
        AmountDialog(
            title = "Presupuesto de ${row.category}",
            initial = row.rawLimit,
            supporting = "D\u00e9jalo vac\u00edo si no quieres poner un tope.",
            onDismiss = { editing = null },
        ) {
            onAction(AppAction.UpdateBudget(row.categoryId, it)); editing = null
        }
    }
    if (editingGoal) {
        AmountDialog("Objetivo mensual de inversi\u00f3n", state.investmentGoal, "Puedes cambiarlo en cualquier momento.", { editingGoal = false }) {
            onAction(AppAction.UpdateInvestmentGoal(it)); editingGoal = false
        }
    }
}

@Composable
private fun BudgetRow(row: BudgetRowUi, onClick: () -> Unit) {
    Column(Modifier.fillMaxWidth().padding(vertical = 11.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(row.category, style = MaterialTheme.typography.titleMedium)
                Text(
                    "Gastado ${row.spent}  Disponible ${row.available}",
                    style = MaterialTheme.typography.labelMedium,
                    color = if (row.overBudget) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(row.limit.ifBlank { "Sin tope" }, fontWeight = FontWeight.SemiBold)
            IconButton(onClick = onClick) { Icon(Icons.Outlined.Edit, "Cambiar presupuesto") }
        }
        InlineProgress(row.fraction, over = row.overBudget, label = row.consumedLabel)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InvestmentsScreen(state: InvestmentsUiState, onAction: (AppAction) -> Unit) {
    var tab by rememberSaveable { mutableStateOf(0) }
    var assetEditor by remember { mutableStateOf<AssetUi?>(null) }
    var creatingAsset by remember { mutableStateOf(false) }
    var deletingAsset by remember { mutableStateOf<AssetUi?>(null) }
    var addValue by remember { mutableStateOf(false) }
    var addCashback by remember { mutableStateOf(false) }
    var quoteAsset by remember { mutableStateOf<AssetUi?>(null) }
    val tabs = listOf("Cartera", "Activos", "Hist\u00f3rico", "Gratis")
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            ScreenIntro(
                "Inversiones",
                "Lo aportado, lo que vale hoy y lo que ha generado el mercado.",
                action = {
                    OutlinedButton(onClick = { onAction(AppAction.RefreshQuotes) }) {
                        Icon(Icons.Outlined.Refresh, null)
                        Text("Precios")
                    }
                },
            )
        }
        item { MetricGrid(state.metrics) }
        item {
            PrimaryTabRow(selectedTabIndex = tab) {
                tabs.forEachIndexed { index, title ->
                    Tab(selected = tab == index, onClick = { tab = index }, text = { Text(title, maxLines = 1) })
                }
            }
        }
        when (tab) {
            0 -> {
                item {
                    SectionCard("Evoluci\u00f3n de la cartera") {
                        if (state.history.size >= 2) PortfolioLineChart(state.history)
                        else EmptyState("A\u00fan no hay evoluci\u00f3n", "Apunta valoraciones para ver la l\u00ednea de la cartera.")
                    }
                }
                if (state.categoryGroups.isNotEmpty()) {
                    item {
                        SectionCard("Por categor\u00eda") {
                            state.categoryGroups.forEach { group ->
                                Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                                    Column(Modifier.weight(1f)) {
                                        Text(group.name, style = MaterialTheme.typography.titleMedium)
                                        Text("${group.assets} activos  ${group.weight}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    Column(horizontalAlignment = Alignment.End) {
                                        Text(group.marketValue, fontWeight = FontWeight.SemiBold)
                                        Text(group.generated, style = MaterialTheme.typography.labelMedium)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            1 -> {
                item {
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.End)) {
                        OutlinedButton(onClick = { onAction(AppAction.ImportTradeRepublic) }) {
                            Icon(Icons.Outlined.FileUpload, null)
                            Text("Importar")
                        }
                        FilledTonalButton(onClick = { creatingAsset = true }) { Icon(Icons.Outlined.Add, null); Text("A\u00f1adir activo") }
                    }
                }
                if (state.assets.isEmpty()) item { EmptyState("No hay activos", "Un activo es cada fondo, cuenta, acci\u00f3n o cripto donde inviertes.") }
                else items(state.assets, key = { it.id }) { asset ->
                    AssetCard(
                        asset = asset,
                        onEdit = { onAction(AppAction.SelectAsset(asset.id)); assetEditor = asset },
                        onQuote = { onAction(AppAction.SelectAsset(asset.id)); quoteAsset = asset },
                        onDelete = { deletingAsset = asset },
                    )
                }
                if (state.quoteHistory.size >= 2) item {
                    SectionCard(
                        title = "Cotizaci\u00f3n",
                        supporting = state.quoteStatus.ifBlank { "Cierre diario y precio medio pagado." },
                    ) {
                        QuoteLineChart(state.quoteHistory, averagePaid = state.quoteAveragePaid)
                        if (state.quoteAveragePaidLabel.isNotBlank()) {
                            Spacer(Modifier.height(6.dp))
                            Text(
                                "Precio medio pagado: ${state.quoteAveragePaidLabel}",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                if (state.purchases.isNotEmpty()) item {
                    SectionCard("Compras del activo") {
                        state.purchases.forEach { purchase ->
                            Row(Modifier.fillMaxWidth().padding(vertical = 7.dp)) {
                                Column(Modifier.weight(1f)) {
                                    Text(purchase.date, style = MaterialTheme.typography.titleMedium)
                                    Text("${purchase.units} t\u00edtulos a ${purchase.paidPrice}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    if (purchase.quoteAtPurchase.isNotBlank()) {
                                        Text(
                                            "Cotizaci\u00f3n entonces ${purchase.quoteAtPurchase}, hoy ${purchase.quoteToday}",
                                            style = MaterialTheme.typography.labelMedium,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                                Column(horizontalAlignment = Alignment.End) {
                                    Text(purchase.currentValue, fontWeight = FontWeight.SemiBold)
                                    Text(purchase.returnLabel, style = MaterialTheme.typography.labelMedium)
                                    if (purchase.quoteChangeLabel.isNotBlank()) {
                                        Text(purchase.quoteChangeLabel, style = MaterialTheme.typography.labelMedium)
                                    }
                                }
                            }
                        }
                    }
                }
            }
            2 -> {
                item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) { FilledTonalButton(onClick = { addValue = true }) { Icon(Icons.Outlined.Add, null); Text("Apuntar valoraci\u00f3n") } } }
                if (state.history.isEmpty()) item { EmptyState("No hay valoraciones", "Apunta cu\u00e1nto vale la cartera cada fin de mes.") }
                else items(state.history, key = { it.id }) { value -> HistoryCard(value) { onAction(AppAction.DeletePortfolioValue(value.id)) } }
            }
            else -> {
                item { Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) { FilledTonalButton(onClick = { addCashback = true }) { Icon(Icons.Outlined.Add, null); Text("A\u00f1adir aportaci\u00f3n") } } }
                if (state.cashback.isEmpty()) item { EmptyState("Nada apuntado", "Cashback, promociones y redondeos aparecen aqu\u00ed.") }
                else items(state.cashback, key = { it.id }) { item -> CashbackCard(item) { onAction(AppAction.DeleteCashback(item.id)) } }
            }
        }
    }

    if (creatingAsset) AssetEditor(null, { creatingAsset = false }) { onAction(AppAction.SaveAsset(null, it)); creatingAsset = false }
    assetEditor?.let { asset -> AssetEditor(asset, { assetEditor = null }) { onAction(AppAction.SaveAsset(asset.id, it)); assetEditor = null } }
    deletingAsset?.let { asset -> ConfirmDeleteDialog("\u00bfQuitar ${asset.name}?", "Los movimientos no se borran.", { deletingAsset = null }) { onAction(AppAction.DeleteAsset(asset.id)); deletingAsset = null } }
    if (addValue) TwoFieldAmountDialog("Apuntar valoraci\u00f3n", "Fecha", "Valor de mercado", { addValue = false }) { date, amount -> onAction(AppAction.AddPortfolioValue(date, amount)); addValue = false }
    if (addCashback) CashbackDialog({ addCashback = false }) { date, asset, concept, amount -> onAction(AppAction.AddCashback(date, asset.ifBlank { null }, concept, amount)); addCashback = false }
    quoteAsset?.let { asset ->
        QuotePickerDialog(
            asset = asset,
            state = state.quoteSearch,
            onDismiss = { quoteAsset = null },
            onSearch = { query -> onAction(AppAction.SearchQuotes(asset.id, query)) },
            onSelect = { symbol ->
                onAction(AppAction.SelectQuote(asset.id, symbol))
                quoteAsset = null
            },
        )
    }
}

@Composable
private fun AssetCard(asset: AssetUi, onEdit: () -> Unit, onQuote: () -> Unit, onDelete: () -> Unit) {
    OutlinedCard(colors = CardDefaults.outlinedCardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(asset.name, style = MaterialTheme.typography.titleLarge)
                    Text("${asset.category}  Valorado ${asset.valuedAt}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                IconButton(onClick = onEdit) { Icon(Icons.Outlined.Edit, "Editar") }
                IconButton(onClick = onDelete) { Icon(Icons.Outlined.DeleteOutline, "Quitar") }
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                AssetFigure("Aportado", asset.contributed, Modifier.weight(1f))
                AssetFigure("Valor", asset.marketValue, Modifier.weight(1f))
                AssetFigure("Generado", asset.generated, Modifier.weight(1f))
            }
            Spacer(Modifier.height(7.dp))
            Text("Inicial ${asset.initial}  Banco ${asset.fromBank}  Gratis ${asset.free}  Rentab. ${asset.returnLabel}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(6.dp))
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(
                        asset.quoteStatus,
                        style = MaterialTheme.typography.labelMedium,
                        color = if (asset.automaticallyQuoted) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    if (asset.latestQuoteDate.isNotBlank()) {
                        Text(
                            "\u00daltimo cierre: ${asset.latestQuoteDate}",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
                TextButton(onClick = onQuote) {
                    Icon(Icons.Outlined.Search, contentDescription = null)
                    Text(if (asset.quoteSymbol.isBlank()) "Cotizaci\u00f3n" else asset.quoteSymbol)
                }
            }
        }
    }
}

@Composable
private fun AssetFigure(label: String, value: String, modifier: Modifier) {
    Column(modifier) {
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(value, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun HistoryCard(value: PortfolioHistoryUi, onDelete: () -> Unit) {
    OutlinedCard(colors = CardDefaults.outlinedCardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(value.date, style = MaterialTheme.typography.titleMedium)
                Text("Aportado ${value.contributed}  Generado ${value.generated}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(value.market, fontWeight = FontWeight.SemiBold)
                Text(value.returnLabel, style = MaterialTheme.typography.labelMedium)
            }
            IconButton(onClick = onDelete) { Icon(Icons.Outlined.DeleteOutline, "Borrar valoraci\u00f3n") }
        }
    }
}

@Composable
private fun CashbackCard(value: CashbackUi, onDelete: () -> Unit) {
    OutlinedCard(colors = CardDefaults.outlinedCardColors(containerColor = MaterialTheme.colorScheme.surface)) {
        Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text(value.concept, style = MaterialTheme.typography.titleMedium)
                Text("${value.date}  ${value.asset}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Text(value.amount, fontWeight = FontWeight.SemiBold)
            IconButton(onClick = onDelete) { Icon(Icons.Outlined.DeleteOutline, "Borrar") }
        }
    }
}

@Composable
private fun QuotePickerDialog(
    asset: AssetUi,
    state: QuoteSearchUiState,
    onDismiss: () -> Unit,
    onSearch: (String) -> Unit,
    onSelect: (String?) -> Unit,
) {
    var query by rememberSaveable(asset.id) { mutableStateOf(asset.name) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Cotizaci\u00f3n de ${asset.name}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    "Busca por nombre y elige la bolsa y moneda en la que compraste.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    label = { Text("Buscar fondo o acci\u00f3n") },
                    leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                    trailingIcon = {
                        TextButton(onClick = { onSearch(query.trim()) }, enabled = query.isNotBlank() && !state.searching) {
                            Text(if (state.searching) "Buscando" else "Buscar")
                        }
                    },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                state.error?.let { error ->
                    Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
                }
                if (state.results.isEmpty() && !state.searching && state.error == null) {
                    Text(
                        "Busca para ver las cotizaciones disponibles.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                state.results.take(8).forEach { result ->
                    OutlinedCard(
                        onClick = { onSelect(result.symbol) },
                        modifier = Modifier.fillMaxWidth(),
                        colors = CardDefaults.outlinedCardColors(containerColor = MaterialTheme.colorScheme.surface),
                    ) {
                        Row(
                            Modifier.fillMaxWidth().padding(10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(result.name, style = MaterialTheme.typography.titleMedium, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                Text(
                                    "${result.symbol}  ${result.exchange}  ${result.currency}",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            if (result.latestPrice.isNotBlank()) Text(result.latestPrice, fontWeight = FontWeight.SemiBold)
                        }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onSelect(null) }) { Text("Usar valor manual") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
private fun AmountDialog(title: String, initial: String, supporting: String, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var value by rememberSaveable(title) { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Column { NumericTextField(value, { value = it }, "Importe", Modifier.fillMaxWidth()); Text(supporting, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) } },
        confirmButton = { Button(onClick = { onSave(value) }) { Text("Guardar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
private fun AssetEditor(asset: AssetUi?, onDismiss: () -> Unit, onSave: (AssetDraft) -> Unit) {
    var name by rememberSaveable(asset?.id) { mutableStateOf(asset?.name.orEmpty()) }
    var category by rememberSaveable(asset?.id) { mutableStateOf(asset?.category.orEmpty()) }
    var initial by rememberSaveable(asset?.id) { mutableStateOf(asset?.rawInitial.orEmpty()) }
    var market by rememberSaveable(asset?.id) { mutableStateOf(asset?.rawMarketValue.orEmpty()) }
    val quoteSymbol = asset?.quoteSymbol.orEmpty()
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (asset == null) "Nuevo activo" else "Editar activo") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { OutlinedTextField(name, { name = it }, label = { Text("Nombre") }); OutlinedTextField(category, { category = it }, label = { Text("Categor\u00eda") }); NumericTextField(initial, { initial = it }, "Aportaci\u00f3n inicial", Modifier.fillMaxWidth()); NumericTextField(market, { market = it }, "Valor de mercado", Modifier.fillMaxWidth()); if (quoteSymbol.isNotBlank()) Text("Cotizaci\u00f3n autom\u00e1tica: $quoteSymbol", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.primary) } },
        confirmButton = { Button(onClick = { onSave(AssetDraft(name, category, initial, market, quoteSymbol)) }, enabled = name.isNotBlank()) { Text("Guardar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
private fun TwoFieldAmountDialog(title: String, firstLabel: String, secondLabel: String, onDismiss: () -> Unit, onSave: (String, String) -> Unit) {
    var first by rememberSaveable(title) { mutableStateOf("") }
    var second by rememberSaveable(title) { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { OutlinedTextField(first, { first = it }, label = { Text(firstLabel) }); NumericTextField(second, { second = it }, secondLabel, Modifier.fillMaxWidth()) } },
        confirmButton = { Button(onClick = { onSave(first, second) }, enabled = first.isNotBlank() && second.isNotBlank()) { Text("Guardar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
private fun CashbackDialog(onDismiss: () -> Unit, onSave: (String, String, String, String) -> Unit) {
    var date by rememberSaveable { mutableStateOf("") }
    var asset by rememberSaveable { mutableStateOf("") }
    var concept by rememberSaveable { mutableStateOf("") }
    var amount by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Aportaci\u00f3n gratis") },
        text = { Column(verticalArrangement = Arrangement.spacedBy(8.dp)) { OutlinedTextField(date, { date = it }, label = { Text("Fecha") }); OutlinedTextField(asset, { asset = it }, label = { Text("Activo") }); OutlinedTextField(concept, { concept = it }, label = { Text("Concepto") }); NumericTextField(amount, { amount = it }, "Importe", Modifier.fillMaxWidth()) } },
        confirmButton = { Button(onClick = { onSave(date, asset, concept, amount) }, enabled = date.isNotBlank() && concept.isNotBlank() && amount.isNotBlank()) { Text("Guardar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}
