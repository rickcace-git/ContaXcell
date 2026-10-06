package com.contaxcell.app.ui.screens

import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.contaxcell.app.ui.AppAction
import com.contaxcell.app.ui.AppUpdateStage
import com.contaxcell.app.ui.AppUpdateUi

/**
 * «Hay una versión nueva de la app». Cuatro momentos: la pregunta, el permiso
 * de instalar (solo la primera vez), la descarga y, al final, el instalador
 * de Android, donde hay que pulsar «Instalar».
 */
@Composable
fun AppUpdateDialog(update: AppUpdateUi, onAction: (AppAction) -> Unit) {
    var showChanges by rememberSaveable { mutableStateOf(false) }
    val downloading = update.stage == AppUpdateStage.Downloading
    AlertDialog(
        // Mientras baja no se cierra tocando fuera: no hay nada que cancelar a medias.
        onDismissRequest = { if (!downloading) onAction(AppAction.DismissAppUpdate) },
        title = { Text("Hay una versión nueva de la app") },
        text = {
            Column(Modifier.heightIn(max = 460.dp).verticalScroll(rememberScrollState())) {
                when (update.stage) {
                    AppUpdateStage.Offer -> {
                        Text(
                            "La ${update.versionName}. Tienes la ${update.currentVersion}. " +
                                "Tus datos se mantienen.",
                        )
                        if (update.notes.isNotBlank()) {
                            Spacer(Modifier.height(10.dp))
                            Text(
                                "Novedades: ${update.notes}",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        if (update.changes.isNotEmpty()) {
                            TextButton(onClick = { showChanges = !showChanges }) {
                                Text(if (showChanges) "Ocultar los cambios" else "Ver qué ha cambiado")
                            }
                            if (showChanges) Changes(update)
                        }
                    }
                    AppUpdateStage.NeedsPermission -> Text(
                        "La primera vez, Android pide permiso para que ContaXcell instale su " +
                            "versión nueva. Pulsa «Abrir ajustes», activa «Permitir de esta fuente», " +
                            "vuelve aquí y pulsa «Actualizar».",
                    )
                    AppUpdateStage.Downloading -> {
                        Text("Descargando la ${update.versionName}…")
                        Spacer(Modifier.height(14.dp))
                        LinearProgressIndicator(
                            progress = { update.progress },
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    AppUpdateStage.Ready -> Text(
                        "Descargada y comprobada. En la pantalla de Android, pulsa «Instalar». " +
                            "Si la has cerrado sin querer, vuelve a abrirla desde aquí.",
                    )
                }
                update.error?.let {
                    Spacer(Modifier.height(10.dp))
                    Text(it, color = MaterialTheme.colorScheme.error)
                }
            }
        },
        confirmButton = {
            when (update.stage) {
                AppUpdateStage.Offer -> Button(onClick = { onAction(AppAction.StartAppUpdate) }) {
                    Text("Actualizar")
                }
                AppUpdateStage.NeedsPermission -> Button(onClick = { onAction(AppAction.OpenInstallPermission) }) {
                    Text("Abrir ajustes")
                }
                AppUpdateStage.Downloading -> Unit
                AppUpdateStage.Ready -> Button(onClick = { onAction(AppAction.StartAppUpdate) }) {
                    Text("Abrir el instalador")
                }
            }
        },
        dismissButton = {
            when (update.stage) {
                AppUpdateStage.Downloading -> Unit
                AppUpdateStage.NeedsPermission -> TextButton(onClick = { onAction(AppAction.StartAppUpdate) }) {
                    Text("Actualizar")
                }
                else -> TextButton(onClick = { onAction(AppAction.DismissAppUpdate) }) { Text("Ahora no") }
            }
        },
    )
}

/** Lo que trae cada versión que falta, la más nueva primero. */
@Composable
private fun Changes(update: AppUpdateUi) {
    update.changes.forEach { release ->
        if (update.changes.size > 1) {
            Text(
                "Versión ${release.versionName}",
                style = MaterialTheme.typography.titleSmall,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.padding(top = 10.dp, bottom = 2.dp),
            )
        }
        release.changes.forEach { change ->
            Text(
                "•  ${change.title}",
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.padding(top = 6.dp),
            )
            if (change.detail.isNotBlank()) {
                Text(
                    change.detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(start = 14.dp),
                )
            }
        }
    }
}
