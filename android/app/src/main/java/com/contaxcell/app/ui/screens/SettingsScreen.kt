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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.Logout
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.ArrowDownward
import androidx.compose.material.icons.outlined.ArrowUpward
import androidx.compose.material.icons.outlined.Backup
import androidx.compose.material.icons.outlined.DeleteOutline
import androidx.compose.material.icons.outlined.Edit
import androidx.compose.material.icons.outlined.FileDownload
import androidx.compose.material.icons.outlined.FileUpload
import androidx.compose.material.icons.outlined.Password
import androidx.compose.material.icons.outlined.Restore
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.contaxcell.app.ui.AppAction
import com.contaxcell.app.ui.CategoryDraft
import com.contaxcell.app.ui.CategorySettingsUi
import com.contaxcell.app.ui.MovementKind
import com.contaxcell.app.ui.SettingsUiState
import com.contaxcell.app.ui.ThemePreference
import com.contaxcell.app.ui.components.ControlRadius
import com.contaxcell.app.ui.components.MetricGrid
import com.contaxcell.app.ui.components.NumericTextField
import com.contaxcell.app.ui.components.ScreenIntro
import com.contaxcell.app.ui.components.SectionCard

@Composable
fun SettingsScreen(
    state: SettingsUiState,
    theme: ThemePreference,
    amountsHidden: Boolean,
    onAction: (AppAction) -> Unit,
) {
    var editBalance by remember { mutableStateOf(false) }
    var editCategory by remember { mutableStateOf<CategorySettingsUi?>(null) }
    var createCategory by remember { mutableStateOf(false) }
    var deleteCategory by remember { mutableStateOf<CategorySettingsUi?>(null) }
    var importConfirm by remember { mutableStateOf(false) }
    var restoreConfirm by remember { mutableStateOf(false) }
    var signOutConfirm by remember { mutableStateOf(false) }
    var passwordDialog by remember { mutableStateOf(false) }

    LazyColumn(
        Modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        item { ScreenIntro("Ajustes", "Tu banco, categor\u00edas, privacidad, archivos y cuenta.") }
        item {
            SectionCard(
                "El banco",
                supporting = "Saldo inicial: lo que hab\u00eda antes del primer movimiento.",
                action = { TextButton(onClick = { editBalance = true }) { Text("Cambiar") } },
            ) { MetricGrid(state.bankMetrics) }
        }
        item {
            SectionCard(
                "Categor\u00edas",
                supporting = "El tipo determina c\u00f3mo cuenta todo su hist\u00f3rico.",
                action = { FilledTonalButton(onClick = { createCategory = true }) { Icon(Icons.Outlined.Add, null); Text("A\u00f1adir") } },
            ) {
                state.categories.forEachIndexed { index, category ->
                    CategoryRow(
                        category,
                        onEdit = { editCategory = category },
                        onDelete = { deleteCategory = category },
                        onUp = { onAction(AppAction.MoveCategory(category.id, -1)) },
                        onDown = { onAction(AppAction.MoveCategory(category.id, 1)) },
                    )
                    if (index != state.categories.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                }
            }
        }
        item {
            BoxWithConstraints {
                if (maxWidth >= 720.dp) {
                    Row(horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        AppearanceCard(theme, amountsHidden, onAction, Modifier.weight(1f))
                        DataCard(state, onImport = { importConfirm = true }, onRestore = { restoreConfirm = true }, onAction, Modifier.weight(1f))
                    }
                } else {
                    Column(verticalArrangement = Arrangement.spacedBy(14.dp)) {
                        AppearanceCard(theme, amountsHidden, onAction)
                        DataCard(state, onImport = { importConfirm = true }, onRestore = { restoreConfirm = true }, onAction)
                    }
                }
            }
        }
        item {
            SectionCard("Tu cuenta") {
                if (state.account.signedIn) {
                    Text("Conectado como ${state.account.user}", style = MaterialTheme.typography.titleMedium)
                    Text(state.account.server, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                } else {
                    Text("Sin cuenta en este m\u00f3vil", style = MaterialTheme.typography.titleMedium)
                }
                if (state.account.syncDetail.isNotBlank()) {
                    Spacer(Modifier.height(4.dp))
                    Text(state.account.syncDetail, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { passwordDialog = true }, enabled = state.account.signedIn) {
                        Icon(Icons.Outlined.Password, null)
                        Text("Contrase\u00f1a")
                    }
                    TextButton(onClick = { signOutConfirm = true }, enabled = state.account.signedIn) {
                        Icon(Icons.AutoMirrored.Outlined.Logout, null)
                        Text("Cerrar sesi\u00f3n")
                    }
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    "Los cambios se guardan primero en el m\u00f3vil. Sin conexi\u00f3n, puedes seguir usando todo.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        if (state.appVersion.isNotBlank()) {
            item { Text("ContaXcell ${state.appVersion}", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant) }
        }
    }

    if (editBalance) SimpleAmountDialog("Saldo inicial", state.initialBalance, { editBalance = false }) {
        onAction(AppAction.UpdateInitialBalance(it)); editBalance = false
    }
    if (createCategory) CategoryEditor(null, { createCategory = false }) { onAction(AppAction.SaveCategory(null, it)); createCategory = false }
    editCategory?.let { category -> CategoryEditor(category, { editCategory = null }) { onAction(AppAction.SaveCategory(category.id, it)); editCategory = null } }
    deleteCategory?.let { category -> ConfirmDeleteDialog("\u00bfBorrar ${category.name}?", if (category.uses > 0) "Tiene ${category.uses} movimientos. Se conservar\u00e1n, pero quedar\u00e1n sin categor\u00eda." else "No tiene movimientos.", { deleteCategory = null }) { onAction(AppAction.DeleteCategory(category.id)); deleteCategory = null } }
    if (importConfirm) ConfirmationDialog("\u00bfImportar desde Excel?", "La contabilidad actual se sustituir\u00e1. Antes se guardar\u00e1 una copia autom\u00e1tica.", "Elegir Excel", { importConfirm = false }) { onAction(AppAction.ImportExcel); importConfirm = false }
    if (restoreConfirm) ConfirmationDialog("\u00bfRestaurar una copia?", "Antes de sustituir los datos se guardar\u00e1 una copia del estado actual.", "Elegir copia", { restoreConfirm = false }) { onAction(AppAction.RestoreBackup); restoreConfirm = false }
    if (signOutConfirm) ConfirmationDialog("\u00bfCerrar la sesi\u00f3n?", "Tus datos se quedan en este m\u00f3vil y en el servidor.", "Cerrar sesi\u00f3n", { signOutConfirm = false }) { onAction(AppAction.SignOut); signOutConfirm = false }
    if (passwordDialog) PasswordDialog({ passwordDialog = false }) { current, new -> onAction(AppAction.ChangePassword(current, new)); passwordDialog = false }
}

@Composable
private fun CategoryRow(category: CategorySettingsUi, onEdit: () -> Unit, onDelete: () -> Unit, onUp: () -> Unit, onDown: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(category.name, style = MaterialTheme.typography.titleMedium)
            Text(
                "${kindLabel(category.kind)}  ${category.uses} movimientos" + if (category.budget.isNotBlank()) "  ${category.budget}/mes" else "",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        IconButton(onClick = onUp) { Icon(Icons.Outlined.ArrowUpward, "Subir") }
        IconButton(onClick = onDown) { Icon(Icons.Outlined.ArrowDownward, "Bajar") }
        IconButton(onClick = onEdit) { Icon(Icons.Outlined.Edit, "Editar") }
        IconButton(onClick = onDelete) { Icon(Icons.Outlined.DeleteOutline, "Borrar") }
    }
}

@Composable
private fun AppearanceCard(theme: ThemePreference, amountsHidden: Boolean, onAction: (AppAction) -> Unit, modifier: Modifier = Modifier) {
    SectionCard("Aspecto y privacidad", modifier) {
        Text("Tema", style = MaterialTheme.typography.labelMedium)
        Spacer(Modifier.height(6.dp))
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            listOf(ThemePreference.System to "Sistema", ThemePreference.Light to "Claro", ThemePreference.Dark to "Oscuro").forEachIndexed { index, pair ->
                SegmentedButton(selected = theme == pair.first, onClick = { onAction(AppAction.SetTheme(pair.first)) }, shape = SegmentedButtonDefaults.itemShape(index, 3)) { Text(pair.second, maxLines = 1) }
            }
        }
        Spacer(Modifier.height(14.dp))
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Text("Ocultar importes", style = MaterialTheme.typography.titleMedium)
                Text("Tapa todas las cifras de un toque.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Switch(checked = amountsHidden, onCheckedChange = { onAction(AppAction.ToggleAmounts) })
        }
    }
}

@Composable
private fun DataCard(state: SettingsUiState, onImport: () -> Unit, onRestore: () -> Unit, onAction: (AppAction) -> Unit, modifier: Modifier = Modifier) {
    SectionCard("Tus datos", modifier, supporting = "Puedes salir a Excel siempre que quieras.") {
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = onImport, modifier = Modifier.weight(1f)) { Icon(Icons.Outlined.FileDownload, null); Text("Importar") }
            Button(onClick = { onAction(AppAction.ExportExcel) }, modifier = Modifier.weight(1f)) { Icon(Icons.Outlined.FileUpload, null); Text("Exportar") }
        }
        Spacer(Modifier.height(8.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            OutlinedButton(onClick = { onAction(AppAction.SaveBackup) }, modifier = Modifier.weight(1f)) { Icon(Icons.Outlined.Backup, null); Text("Copia") }
            OutlinedButton(onClick = onRestore, modifier = Modifier.weight(1f)) { Icon(Icons.Outlined.Restore, null); Text("Restaurar") }
        }
        Spacer(Modifier.height(10.dp))
        Text(state.dataLocation, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun SimpleAmountDialog(title: String, initial: String, onDismiss: () -> Unit, onSave: (String) -> Unit) {
    var value by rememberSaveable(title) { mutableStateOf(initial) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = { NumericTextField(value, { value = it }, "Importe", Modifier.fillMaxWidth(), allowNegative = true) },
        confirmButton = { Button(onClick = { onSave(value) }) { Text("Guardar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
private fun CategoryEditor(category: CategorySettingsUi?, onDismiss: () -> Unit, onSave: (CategoryDraft) -> Unit) {
    var name by rememberSaveable(category?.id) { mutableStateOf(category?.name.orEmpty()) }
    var kind by rememberSaveable(category?.id) { mutableStateOf(category?.kind ?: MovementKind.Expense) }
    var budget by rememberSaveable(category?.id) { mutableStateOf(category?.rawBudget.orEmpty()) }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (category == null) "Nueva categor\u00eda" else "Editar categor\u00eda") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(name, { name = it }, label = { Text("Nombre") }, singleLine = true)
                SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
                    MovementKind.entries.forEachIndexed { index, value ->
                        SegmentedButton(selected = kind == value, onClick = { kind = value }, shape = SegmentedButtonDefaults.itemShape(index, MovementKind.entries.size)) { Text(kindLabel(value), maxLines = 1) }
                    }
                }
                if (kind == MovementKind.Expense) NumericTextField(budget, { budget = it }, "Presupuesto al mes", Modifier.fillMaxWidth())
                Text("Cambiar el tipo recalcula todo el hist\u00f3rico de esta categor\u00eda.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        },
        confirmButton = { Button(onClick = { onSave(CategoryDraft(name, kind, if (kind == MovementKind.Expense) budget else "")) }, enabled = name.isNotBlank()) { Text("Guardar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
private fun PasswordDialog(onDismiss: () -> Unit, onSave: (String, String) -> Unit) {
    var current by rememberSaveable { mutableStateOf("") }
    var new by rememberSaveable { mutableStateOf("") }
    var confirm by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Cambiar la contrase\u00f1a") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(current, { current = it }, label = { Text("Contrase\u00f1a actual") }, visualTransformation = PasswordVisualTransformation(), singleLine = true)
                OutlinedTextField(new, { new = it }, label = { Text("Contrase\u00f1a nueva") }, visualTransformation = PasswordVisualTransformation(), singleLine = true, supportingText = { Text("M\u00ednimo 8 caracteres") })
                OutlinedTextField(confirm, { confirm = it }, label = { Text("Repite la contrase\u00f1a") }, visualTransformation = PasswordVisualTransformation(), singleLine = true, isError = confirm.isNotBlank() && confirm != new)
            }
        },
        confirmButton = { Button(onClick = { onSave(current, new) }, enabled = current.isNotBlank() && new.length >= 8 && new == confirm) { Text("Cambiar") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } },
    )
}

@Composable
private fun ConfirmationDialog(title: String, detail: String, confirm: String, onDismiss: () -> Unit, onConfirm: () -> Unit) {
    AlertDialog(onDismissRequest = onDismiss, title = { Text(title) }, text = { Text(detail) }, confirmButton = { Button(onClick = onConfirm) { Text(confirm) } }, dismissButton = { TextButton(onClick = onDismiss) { Text("Cancelar") } })
}

private fun kindLabel(kind: MovementKind) = when (kind) {
    MovementKind.Expense -> "Gasto"
    MovementKind.Income -> "Ingreso"
    MovementKind.Investment -> "Inversi\u00f3n"
}
