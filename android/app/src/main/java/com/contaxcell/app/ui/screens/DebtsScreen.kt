package com.contaxcell.app.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Notes
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.Payments
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
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
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.contaxcell.app.ui.AppAction
import com.contaxcell.app.ui.CategoryOption
import com.contaxcell.app.ui.DebtDirection
import com.contaxcell.app.ui.DebtDraft
import com.contaxcell.app.ui.DebtRowUi
import com.contaxcell.app.ui.DebtSettlementDraft
import com.contaxcell.app.ui.DebtsUiState
import com.contaxcell.app.ui.MetricTone
import com.contaxcell.app.ui.MovementKind
import com.contaxcell.app.ui.components.CompactDropdown
import com.contaxcell.app.ui.components.EmptyState
import com.contaxcell.app.ui.components.MetricGrid
import com.contaxcell.app.ui.components.NumericTextField
import com.contaxcell.app.ui.components.ScreenIntro
import com.contaxcell.app.ui.components.SectionCard
import com.contaxcell.app.ui.components.metricToneColor

@Composable
fun DebtsScreen(state: DebtsUiState, onAction: (AppAction) -> Unit) {
    var creating by remember { mutableStateOf(false) }
    var editing by remember { mutableStateOf<DebtRowUi?>(null) }
    var noting by remember { mutableStateOf<DebtRowUi?>(null) }
    var settling by remember { mutableStateOf<DebtRowUi?>(null) }
    var deleting by remember { mutableStateOf<DebtRowUi?>(null) }

    LazyColumn(
        modifier = Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item {
            ScreenIntro(
                title = "Deudas",
                supporting = "Lo que te deben y lo que debes, sin alterar el saldo del banco.",
                action = {
                    FilledTonalButton(onClick = { creating = true }) {
                        Icon(Icons.Outlined.Add, contentDescription = null)
                        Text("Nueva")
                    }
                },
            )
        }
        if (state.metrics.isNotEmpty()) item { MetricGrid(state.metrics) }
        if (state.people.isNotEmpty()) {
            item {
                SectionCard(
                    title = "Cuenta con cada persona",
                    supporting = "El neto de todo lo que sigue abierto.",
                ) {
                    state.people.forEachIndexed { index, person ->
                        Row(
                            Modifier.fillMaxWidth().padding(vertical = 9.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(person.person, style = MaterialTheme.typography.titleMedium)
                                Text(
                                    "${person.openItems} ${if (person.openItems == 1) "cuenta abierta" else "cuentas abiertas"}",
                                    style = MaterialTheme.typography.labelMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            Text(
                                person.balance,
                                style = MaterialTheme.typography.titleMedium,
                                color = metricToneColor(person.tone),
                            )
                        }
                        if (index != state.people.lastIndex) {
                            HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                        }
                    }
                }
            }
        }
        if (state.rows.isEmpty()) {
            item {
                EmptyState(
                    title = "No hay ninguna deuda",
                    detail = "Apunta una cena compartida, un pr\u00e9stamo o cualquier cuenta pendiente.",
                    actionLabel = "Crear la primera",
                    onAction = { creating = true },
                )
            }
        } else {
            items(state.rows, key = { it.id }) { debt ->
                DebtCard(
                    debt = debt,
                    onEdit = { editing = debt },
                    onNote = { noting = debt },
                    onSettle = { settling = debt },
                    onDelete = { deleting = debt },
                )
            }
        }
    }

    if (creating) {
        DebtEditor(debt = null, today = state.today, onDismiss = { creating = false }) {
            onAction(AppAction.SaveDebt(null, it))
            creating = false
        }
    }
    editing?.let { debt ->
        DebtEditor(debt, state.today, onDismiss = { editing = null }) {
            onAction(AppAction.SaveDebt(debt.id, it))
            editing = null
        }
    }
    noting?.let { debt ->
        DebtNoteDialog(debt, onDismiss = { noting = null }) {
            onAction(AppAction.UpdateDebtNote(debt.id, it))
            noting = null
        }
    }
    settling?.let { debt ->
        DebtSettlementDialog(debt, state, onDismiss = { settling = null }) {
            onAction(AppAction.SettleDebt(debt.id, it))
            settling = null
        }
    }
    deleting?.let { debt ->
        ConfirmDeleteDialog(
            title = "\u00bfBorrar esta deuda?",
            detail = "${debt.person}: ${debt.total}. Los movimientos ya creados se conservan.",
            onDismiss = { deleting = null },
        ) {
            onAction(AppAction.DeleteDebt(debt.id))
            deleting = null
        }
    }
}

@Composable
private fun DebtCard(
    debt: DebtRowUi,
    onEdit: () -> Unit,
    onNote: () -> Unit,
    onSettle: () -> Unit,
    onDelete: () -> Unit,
) {
    OutlinedCard(
        colors = CardDefaults.outlinedCardColors(
            containerColor = if (debt.settled) {
                MaterialTheme.colorScheme.surfaceVariant.copy(alpha = .38f)
            } else MaterialTheme.colorScheme.surface,
        ),
    ) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(debt.person, style = MaterialTheme.typography.titleLarge)
                    Text(
                        listOf(debt.date, debt.concept).filter { it.isNotBlank() }.joinToString("  "),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text(
                        if (debt.settled) "Saldada" else debt.pending,
                        style = MaterialTheme.typography.titleMedium,
                        color = if (debt.settled) MaterialTheme.colorScheme.onSurfaceVariant else
                            metricToneColor(
                                if (debt.direction == DebtDirection.OwedToMe) MetricTone.Positive
                                else MetricTone.Negative,
                            ),
                    )
                    Text("de ${debt.total}", style = MaterialTheme.typography.labelMedium)
                }
            }
            if (debt.note.isNotBlank()) {
                Spacer(Modifier.height(8.dp))
                Text(
                    debt.note.lineSequence().first(),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(2.dp), verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = onSettle, enabled = !debt.settled) {
                    Icon(Icons.Outlined.Payments, contentDescription = null)
                    Text(if (debt.direction == DebtDirection.OwedToMe) "Cobrar" else "Pagar")
                }
                IconButton(onClick = onEdit) { Icon(Icons.Outlined.Edit, "Editar") }
                IconButton(onClick = onNote) { Icon(Icons.AutoMirrored.Outlined.Notes, "Editar nota") }
                IconButton(onClick = onDelete) { Icon(Icons.Outlined.DeleteOutline, "Borrar") }
            }
        }
    }
}

@Composable
private fun DebtEditor(
    debt: DebtRowUi?,
    today: String,
    onDismiss: () -> Unit,
    onSave: (DebtDraft) -> Unit,
) {
    var direction by rememberSaveable(debt?.id) { mutableStateOf(debt?.direction ?: DebtDirection.OwedToMe) }
    var person by rememberSaveable(debt?.id) { mutableStateOf(debt?.person.orEmpty()) }
    var concept by rememberSaveable(debt?.id) { mutableStateOf(debt?.concept.orEmpty()) }
    var amount by rememberSaveable(debt?.id) { mutableStateOf(debt?.rawTotal.orEmpty()) }
    var date by rememberSaveable(debt?.id) { mutableStateOf(debt?.date ?: today) }
    var note by rememberSaveable(debt?.id) { mutableStateOf(debt?.note.orEmpty()) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (debt == null) "Nueva deuda" else "Editar deuda") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
                Text("\u00bfDe qui\u00e9n es el dinero?", style = MaterialTheme.typography.labelMedium)
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    listOf(DebtDirection.OwedToMe to "Me deben", DebtDirection.IOwe to "Debo")
                        .forEachIndexed { index, option ->
                            SegmentedButton(
                                selected = direction == option.first,
                                onClick = { direction = option.first },
                                shape = SegmentedButtonDefaults.itemShape(index, 2),
                            ) { Text(option.second) }
                        }
                }
                OutlinedTextField(person, { person = it }, label = { Text("Qui\u00e9n") }, singleLine = true)
                OutlinedTextField(concept, { concept = it }, label = { Text("De qu\u00e9") }, singleLine = true)
                NumericTextField(amount, { amount = it }, "Importe", Modifier.fillMaxWidth())
                OutlinedTextField(date, { date = it }, label = { Text("Desde") }, supportingText = { Text("AAAA-MM-DD") }, singleLine = true)
                OutlinedTextField(note, { note = it }, label = { Text("Nota") }, minLines = 3, maxLines = 6)
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(DebtDraft(direction, person.trim(), concept.trim(), amount, date, note.trim())) },
                enabled = person.isNotBlank() && amount.isNotBlank() && date.isNotBlank(),
            ) { Text("Guardar") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
private fun DebtNoteDialog(debt: DebtRowUi, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var note by rememberSaveable(debt.id) { mutableStateOf(debt.note) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Nota de ${debt.person}") },
        text = { OutlinedTextField(note, { note = it }, label = { Text("Nota") }, minLines = 6, maxLines = 10) },
        confirmButton = { Button(onClick = { onSave(note.trim()) }) { Text("Guardar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
private fun DebtSettlementDialog(
    debt: DebtRowUi,
    state: DebtsUiState,
    onDismiss: () -> Unit,
    onSave: (DebtSettlementDraft) -> Unit,
) {
    val movementKind = if (debt.direction == DebtDirection.OwedToMe) MovementKind.Income else MovementKind.Expense
    val categories = state.categories.filter { it.kind == movementKind }
    var amount by rememberSaveable(debt.id) { mutableStateOf(debt.rawPending) }
    var date by rememberSaveable(debt.id) { mutableStateOf(state.today) }
    var createMovement by rememberSaveable(debt.id) { mutableStateOf(false) }
    var categoryId by rememberSaveable(debt.id) { mutableStateOf(categories.firstOrNull()?.id) }
    val verb = if (debt.direction == DebtDirection.OwedToMe) "Cobrar" else "Pagar"
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("$verb a ${debt.person}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(
                    "Quedan ${debt.pending}. Puedes saldar solo una parte y conservar el resto.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                NumericTextField(amount, { amount = it }, "Cu\u00e1nto", Modifier.fillMaxWidth())
                OutlinedTextField(date, { date = it }, label = { Text("Cu\u00e1ndo") }, supportingText = { Text("AAAA-MM-DD") }, singleLine = true)
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Apuntar tambi\u00e9n el movimiento", style = MaterialTheme.typography.titleMedium)
                        Text(
                            "M\u00e1rcalo solo si el dinero entra o sale ahora.",
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(checked = createMovement, onCheckedChange = { createMovement = it })
                }
                if (createMovement) {
                    CompactDropdown(
                        label = "Categor\u00eda del movimiento",
                        selected = categories.firstOrNull { it.id == categoryId },
                        options = categories,
                        optionLabel = { it.label },
                        onSelected = { categoryId = it.id },
                    )
                }
            }
        },
        confirmButton = {
            Button(
                onClick = { onSave(DebtSettlementDraft(amount, date, createMovement, categoryId)) },
                enabled = amount.isNotBlank() && date.isNotBlank() && (!createMovement || categoryId != null),
            ) { Text(verb) }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}
