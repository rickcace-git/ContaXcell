package com.contaxcell.app.ui.screens

import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.ReceiptLong
import androidx.compose.material.icons.outlined.Search
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.Switch
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
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.contaxcell.app.ui.AppAction
import com.contaxcell.app.ui.AppDestination
import com.contaxcell.app.ui.CategoryOption
import com.contaxcell.app.ui.MovementDraft
import com.contaxcell.app.ui.MovementKind
import com.contaxcell.app.ui.MovementRowUi
import com.contaxcell.app.ui.MovementsUiState
import com.contaxcell.app.ui.QuickAddUiState
import com.contaxcell.app.ui.RecurringDraft
import com.contaxcell.app.ui.RecurringRowUi
import com.contaxcell.app.ui.RecurringUiState
import com.contaxcell.app.ui.SelectableOption
import com.contaxcell.app.ui.components.CompactDropdown
import com.contaxcell.app.ui.components.ControlRadius
import com.contaxcell.app.ui.components.EmptyState
import com.contaxcell.app.ui.components.LoadingState
import com.contaxcell.app.ui.components.MetricGrid
import com.contaxcell.app.ui.components.NumericTextField
import com.contaxcell.app.ui.components.OptionChips
import com.contaxcell.app.ui.components.ScreenIntro
import com.contaxcell.app.ui.components.SectionCard
import com.contaxcell.app.ui.components.metricToneColor
import com.contaxcell.app.ui.MetricTone

@Composable
fun QuickAddScreen(state: QuickAddUiState, onAction: (AppAction) -> Unit) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            ScreenIntro(
                title = "Apuntar",
                supporting = "Importe, concepto y categor\u00eda. Nada m\u00e1s.",
            )
        }
        item {
            BoxWithConstraints {
                if (maxWidth >= 760.dp) {
                    Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        QuickAddForm(state, onAction, Modifier.weight(.82f))
                        Column(Modifier.weight(1.18f), verticalArrangement = Arrangement.spacedBy(14.dp)) {
                            SectionCard("Este mes") { MetricGrid(state.monthMetrics) }
                            RecentMovements(state.recent, onAction)
                        }
                    }
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                        QuickAddForm(state, onAction)
                        if (state.monthMetrics.isNotEmpty()) {
                            SectionCard("Este mes") { MetricGrid(state.monthMetrics) }
                        }
                        RecentMovements(state.recent, onAction)
                    }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun QuickAddForm(
    state: QuickAddUiState,
    onAction: (AppAction) -> Unit,
    modifier: Modifier = Modifier,
) {
    var kind by rememberSaveable { mutableStateOf(MovementKind.Expense) }
    var amount by rememberSaveable { mutableStateOf("") }
    var description by rememberSaveable { mutableStateOf("") }
    var categoryId by rememberSaveable {
        mutableStateOf(state.categories.firstOrNull { it.kind == MovementKind.Expense }?.id.orEmpty())
    }
    var assetId by rememberSaveable { mutableStateOf<String?>(null) }
    var date by rememberSaveable(state.today) { mutableStateOf(state.today) }
    var repeats by rememberSaveable { mutableStateOf(false) }
    var cadence by rememberSaveable { mutableStateOf("Mensual") }
    val categories = state.categories.filter { it.kind == kind }
    val selectedCategory = categories.firstOrNull { it.id == categoryId }
    val isInvestment = kind == MovementKind.Investment

    fun save() {
        if (amount.isBlank() || categoryId.isBlank()) return
        onAction(
            AppAction.AddMovement(
                MovementDraft(
                    amount = amount,
                    description = description.trim(),
                    categoryId = categoryId,
                    date = date,
                    assetId = assetId,
                    recurringCadence = cadence.takeIf { repeats },
                ),
            ),
        )
        amount = ""
        description = ""
        repeats = false
    }

    SectionCard("Nuevo movimiento", modifier) {
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            listOf(
                MovementKind.Expense to "Gasto",
                MovementKind.Income to "Ingreso",
                MovementKind.Investment to "Inversi\u00f3n",
            ).forEachIndexed { index, (value, label) ->
                SegmentedButton(
                    selected = kind == value,
                    onClick = {
                        kind = value
                        categoryId = state.categories.firstOrNull { it.kind == value }?.id.orEmpty()
                        if (value != MovementKind.Investment) assetId = null
                    },
                    shape = SegmentedButtonDefaults.itemShape(index, 3),
                ) { Text(label, maxLines = 1) }
            }
        }
        Spacer(Modifier.height(14.dp))
        NumericTextField(
            value = amount,
            onValueChange = { amount = it },
            modifier = Modifier.fillMaxWidth(),
            label = "Importe",
            textStyle = MaterialTheme.typography.headlineMedium,
            imeAction = ImeAction.Next,
        )
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = description,
            onValueChange = { description = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Concepto") },
            placeholder = { Text("Compra, n\u00f3mina, aportaci\u00f3n...") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
            keyboardActions = KeyboardActions(onDone = { save() }),
        )
        Spacer(Modifier.height(10.dp))
        CompactDropdown(
            label = "Categor\u00eda",
            selected = selectedCategory,
            options = categories,
            optionLabel = { it.label },
            onSelected = { categoryId = it.id },
        )
        if (isInvestment) {
            Spacer(Modifier.height(10.dp))
            CompactDropdown(
                label = "Activo",
                selected = state.assets.firstOrNull { it.id == assetId },
                options = state.assets,
                optionLabel = { it.label },
                onSelected = { assetId = it.id },
                emptyLabel = "Sin asignar",
            )
        }
        Spacer(Modifier.height(10.dp))
        OutlinedTextField(
            value = date,
            onValueChange = { date = it },
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Fecha") },
            supportingText = { Text("AAAA-MM-DD") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
        )
        Spacer(Modifier.height(10.dp))
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Column(Modifier.weight(1f)) {
                Text("Se repite", style = MaterialTheme.typography.titleMedium)
                Text(
                    "Este apunte ser\u00e1 el primer pago.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Switch(checked = repeats, onCheckedChange = { repeats = it })
        }
        if (repeats) {
            Spacer(Modifier.height(8.dp))
            CompactDropdown(
                label = "Cada cu\u00e1nto",
                selected = state.cadences.firstOrNull { it == cadence },
                options = state.cadences,
                optionLabel = { it },
                onSelected = { cadence = it },
            )
            Spacer(Modifier.height(4.dp))
            Text(
                "Se apuntar\u00e1 solo a partir de la siguiente fecha. Puedes cambiarlo en Peri\u00f3dicos.",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.height(14.dp))
        Button(
            onClick = { save() },
            enabled = amount.isNotBlank() && categoryId.isNotBlank() && !state.saving,
            modifier = Modifier.fillMaxWidth().height(48.dp),
            shape = RoundedCornerShape(ControlRadius),
        ) {
            Icon(Icons.Outlined.Add, contentDescription = null)
            Spacer(Modifier.width(8.dp))
            Text(if (state.saving) "Guardando" else "Guardar")
        }
    }
}

@Composable
private fun RecentMovements(rows: List<MovementRowUi>, onAction: (AppAction) -> Unit) {
    SectionCard(
        title = "\u00daltimos movimientos",
        action = {
            TextButton(onClick = { onAction(AppAction.Navigate(AppDestination.Movements)) }) {
                Text("Ver todos")
            }
        },
    ) {
        if (rows.isEmpty()) {
            EmptyState("Todav\u00eda no hay movimientos", "El primero aparecer\u00e1 aqu\u00ed al guardarlo.")
        } else {
            Column {
                rows.take(8).forEachIndexed { index, row ->
                    MovementRow(row, onEdit = null, onDelete = null)
                    if (index != rows.take(8).lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                }
            }
        }
    }
}

@Composable
fun MovementsScreen(state: MovementsUiState, onAction: (AppAction) -> Unit) {
    var editing by remember { mutableStateOf<MovementRowUi?>(null) }
    var deleting by remember { mutableStateOf<MovementRowUi?>(null) }
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item { ScreenIntro("Movimientos", "Todo el libro, ordenado de lo m\u00e1s reciente a lo m\u00e1s antiguo.") }
        item {
            SectionCard("Buscar y filtrar") {
                OutlinedTextField(
                    value = state.query,
                    onValueChange = { onAction(AppAction.SearchMovements(it)) },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Buscar") },
                    placeholder = { Text("Concepto, categor\u00eda o activo") },
                    leadingIcon = { Icon(Icons.Outlined.Search, contentDescription = null) },
                    singleLine = true,
                )
                Spacer(Modifier.height(10.dp))
                Text("Categor\u00eda", style = MaterialTheme.typography.labelMedium)
                OptionChips(state.categories, state.categoryId, {
                    onAction(AppAction.FilterMovements(it, state.monthId))
                })
                Spacer(Modifier.height(6.dp))
                Text("Mes", style = MaterialTheme.typography.labelMedium)
                OptionChips(state.months, state.monthId, {
                    onAction(AppAction.FilterMovements(state.categoryId, it))
                }, allLabel = "Todos")
            }
        }
        item {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(state.countLabel, style = MaterialTheme.typography.titleMedium, modifier = Modifier.weight(1f))
                if (state.totalsLabel.isNotBlank()) {
                    Text(state.totalsLabel, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        if (state.loading && state.rows.isEmpty()) {
            item { LoadingState() }
        } else if (state.rows.isEmpty()) {
            item { EmptyState("No hay coincidencias", "Cambia los filtros o apunta un movimiento nuevo.") }
        } else {
            items(state.rows, key = { it.id }) { row ->
                OutlinedCard(
                    modifier = Modifier.fillMaxWidth().clickable { editing = row },
                    colors = CardDefaults.outlinedCardColors(containerColor = MaterialTheme.colorScheme.surface),
                ) {
                    MovementRow(row, onEdit = { editing = row }, onDelete = { deleting = row })
                }
            }
        }
        if (state.canLoadMore) {
            item {
                OutlinedButton(onClick = { onAction(AppAction.LoadMoreMovements) }, Modifier.fillMaxWidth()) {
                    Text("Cargar m\u00e1s")
                }
            }
        }
    }
    editing?.let { row ->
        MovementEditor(row, state.editCategories, state.assets, onDismiss = { editing = null }) { draft ->
            onAction(AppAction.UpdateMovement(row.id, draft))
            editing = null
        }
    }
    deleting?.let { row ->
        ConfirmDeleteDialog(
            title = "\u00bfBorrar este movimiento?",
            detail = "${row.description.ifBlank { row.category }}  ${row.amount}",
            onDismiss = { deleting = null },
            onConfirm = {
                onAction(AppAction.DeleteMovement(row.id))
                deleting = null
            },
        )
    }
}

@Composable
private fun MovementRow(
    row: MovementRowUi,
    onEdit: (() -> Unit)?,
    onDelete: (() -> Unit)?,
) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 14.dp, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Column(Modifier.weight(1f)) {
            Text(
                row.description.ifBlank { row.category },
                style = MaterialTheme.typography.titleMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                listOf(row.date, row.category, row.asset).filter { it.isNotBlank() }.joinToString("  "),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(
                row.amount,
                style = MaterialTheme.typography.titleMedium,
                color = metricToneColor(
                    when (row.kind) {
                        MovementKind.Expense -> MetricTone.Negative
                        MovementKind.Income -> MetricTone.Positive
                        MovementKind.Investment -> MetricTone.Investment
                    },
                ),
            )
            if (row.balance.isNotBlank()) {
                Text(row.balance, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        if (onEdit != null) {
            IconButton(onClick = onEdit) { Icon(Icons.Outlined.Edit, contentDescription = "Editar") }
        }
        if (onDelete != null) {
            IconButton(onClick = onDelete) { Icon(Icons.Outlined.DeleteOutline, contentDescription = "Borrar") }
        }
    }
}

@Composable
private fun MovementEditor(
    row: MovementRowUi,
    categories: List<CategoryOption>,
    assets: List<SelectableOption>,
    onDismiss: () -> Unit,
    onSave: (MovementDraft) -> Unit,
) {
    var amount by rememberSaveable(row.id) { mutableStateOf(row.rawAmount) }
    var description by rememberSaveable(row.id) { mutableStateOf(row.description) }
    var date by rememberSaveable(row.id) { mutableStateOf(row.date) }
    var categoryId by rememberSaveable(row.id) { mutableStateOf(row.categoryId) }
    var assetId by rememberSaveable(row.id) { mutableStateOf(row.assetId) }
    val availableCategories = categories.ifEmpty {
        listOf(CategoryOption(row.categoryId, row.category, row.kind))
    }
    val selectedCategory = availableCategories.firstOrNull { it.id == categoryId }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Editar movimiento") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                NumericTextField(amount, { amount = it }, "Importe", Modifier.fillMaxWidth())
                OutlinedTextField(description, { description = it }, label = { Text("Concepto") }, singleLine = true)
                CompactDropdown(
                    label = "Categor\u00eda",
                    selected = selectedCategory,
                    options = availableCategories,
                    optionLabel = { it.label },
                    onSelected = {
                        categoryId = it.id
                        if (it.kind != MovementKind.Investment) assetId = null
                    },
                )
                if (selectedCategory?.kind == MovementKind.Investment && assets.isNotEmpty()) {
                    CompactDropdown(
                        label = "Activo",
                        selected = assets.firstOrNull { it.id == assetId },
                        options = assets,
                        optionLabel = { it.label },
                        onSelected = { assetId = it.id },
                        emptyLabel = "Sin asignar",
                    )
                }
                OutlinedTextField(date, { date = it }, label = { Text("Fecha") }, singleLine = true)
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(MovementDraft(amount, description, categoryId, date, assetId)) },
                enabled = amount.isNotBlank() && categoryId.isNotBlank(),
            ) { Text("Guardar") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
fun RecurringScreen(state: RecurringUiState, onAction: (AppAction) -> Unit) {
    var editing by remember { mutableStateOf<RecurringRowUi?>(null) }
    var creating by remember { mutableStateOf(false) }
    var deleting by remember { mutableStateOf<RecurringRowUi?>(null) }
    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            ScreenIntro(
                "Pagos peri\u00f3dicos",
                "ContaXcell apunta autom\u00e1ticamente lo que se repite.",
                action = { FilledTonalButton(onClick = { creating = true }) { Icon(Icons.Outlined.Add, null); Text("Nuevo") } },
            )
        }
        if (state.metrics.isNotEmpty()) item { MetricGrid(state.metrics) }
        if (state.rows.isEmpty()) {
            item {
                EmptyState(
                    title = "No hay pagos peri\u00f3dicos",
                    detail = "A\u00f1ade el alquiler, suscripciones, n\u00f3mina o aportaciones.",
                    actionLabel = "Crear el primero",
                    onAction = { creating = true },
                )
            }
        } else {
            items(state.rows, key = { it.id }) { row ->
                OutlinedCard(colors = CardDefaults.outlinedCardColors(containerColor = MaterialTheme.colorScheme.surface)) {
                    Row(Modifier.fillMaxWidth().padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(row.name, style = MaterialTheme.typography.titleMedium)
                            Text(
                                "${row.category}  ${row.cadence}  Pr\u00f3ximo: ${row.nextPayment}",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Text(row.amount, fontWeight = FontWeight.SemiBold)
                        Switch(checked = row.enabled && !row.finished, onCheckedChange = { onAction(AppAction.ToggleRecurring(row.id)) }, enabled = !row.finished)
                        IconButton(onClick = { editing = row }) { Icon(Icons.Outlined.Edit, "Editar") }
                        IconButton(onClick = { deleting = row }) { Icon(Icons.Outlined.DeleteOutline, "Borrar") }
                    }
                }
            }
        }
    }
    if (creating) RecurringEditor(null, state, { creating = false }) {
        onAction(AppAction.SaveRecurring(null, it)); creating = false
    }
    editing?.let { row ->
        RecurringEditor(row, state, { editing = null }) {
            onAction(AppAction.SaveRecurring(row.id, it)); editing = null
        }
    }
    deleting?.let { row ->
        ConfirmDeleteDialog("\u00bfBorrar este pago peri\u00f3dico?", "Lo ya apuntado se conserva.", { deleting = null }) {
            onAction(AppAction.DeleteRecurring(row.id)); deleting = null
        }
    }
}

@Composable
private fun RecurringEditor(
    row: RecurringRowUi?,
    state: RecurringUiState,
    onDismiss: () -> Unit,
    onSave: (RecurringDraft) -> Unit,
) {
    var name by rememberSaveable(row?.id) { mutableStateOf(row?.name.orEmpty()) }
    var category by rememberSaveable(row?.id) {
        mutableStateOf(row?.categoryId ?: state.categories.firstOrNull()?.id.orEmpty())
    }
    var amount by rememberSaveable(row?.id) { mutableStateOf(row?.rawAmount.orEmpty()) }
    var cadence by rememberSaveable(row?.id) { mutableStateOf(row?.cadence ?: "Mensual") }
    var start by rememberSaveable(row?.id) { mutableStateOf(row?.startDate.orEmpty()) }
    var end by rememberSaveable(row?.id) { mutableStateOf(row?.endDate.orEmpty()) }
    var assetId by rememberSaveable(row?.id) { mutableStateOf(row?.assetId) }
    val availableCategories = state.categories.ifEmpty {
        row?.let { listOf(CategoryOption(it.categoryId, it.category, it.kind)) }.orEmpty()
    }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (row == null) "Nuevo pago peri\u00f3dico" else "Editar pago peri\u00f3dico") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(name, { name = it }, label = { Text("Nombre") }, singleLine = true)
                CompactDropdown(
                    label = "Categor\u00eda",
                    selected = availableCategories.firstOrNull { it.id == category },
                    options = availableCategories,
                    optionLabel = { it.label },
                    onSelected = { category = it.id },
                )
                NumericTextField(amount, { amount = it }, "Importe", Modifier.fillMaxWidth())
                CompactDropdown(
                    label = "Cada cu\u00e1nto",
                    selected = state.cadences.firstOrNull { it == cadence },
                    options = state.cadences,
                    optionLabel = { it },
                    onSelected = { cadence = it },
                )
                if (availableCategories.firstOrNull { it.id == category }?.kind == MovementKind.Investment && state.assets.isNotEmpty()) {
                    CompactDropdown(
                        label = "Activo",
                        selected = state.assets.firstOrNull { it.id == assetId },
                        options = state.assets,
                        optionLabel = { it.label },
                        onSelected = { assetId = it.id },
                        emptyLabel = "Sin asignar",
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(start, { start = it }, label = { Text("Primer pago") }, modifier = Modifier.weight(1f), singleLine = true)
                    OutlinedTextField(end, { end = it }, label = { Text("\u00daltimo (opcional)") }, modifier = Modifier.weight(1f), singleLine = true)
                }
            }
        },
        confirmButton = {
            Button(onClick = { onSave(RecurringDraft(name, category, amount, cadence, start, end, assetId)) }, enabled = name.isNotBlank() && category.isNotBlank() && amount.isNotBlank()) { Text("Guardar") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
internal fun ConfirmDeleteDialog(
    title: String,
    detail: String,
    onDismiss: () -> Unit,
    onConfirm: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { Text(detail) },
        confirmButton = { Button(onClick = onConfirm) { Text("Borrar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
        icon = { Icon(Icons.Outlined.DeleteOutline, contentDescription = null) },
    )
}
