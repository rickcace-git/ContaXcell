package com.contaxcell.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.AccountBalanceWallet
import androidx.compose.material.icons.outlined.CloudOff
import androidx.compose.material.icons.outlined.Lock
import androidx.compose.material.icons.outlined.MoreHoriz
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.unit.dp
import com.contaxcell.app.ui.AppAction
import com.contaxcell.app.ui.AuthUiState

@Composable
fun AuthScreen(state: AuthUiState.Gate, onAction: (AppAction) -> Unit) {
    var registering by rememberSaveable { mutableStateOf(false) }
    var showServer by rememberSaveable { mutableStateOf(false) }
    var user by rememberSaveable(state.defaultUser) { mutableStateOf(state.defaultUser) }
    var password by rememberSaveable { mutableStateOf("") }
    var server by rememberSaveable(state.defaultServer) { mutableStateOf(state.defaultServer) }
    var inviteCode by rememberSaveable { mutableStateOf("") }

    fun submit() {
        if (registering) onAction(AppAction.Register(user, password, server, inviteCode))
        else onAction(AppAction.SignIn(user, password, server))
    }

    Box(
        Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)
            .imePadding().padding(20.dp),
        contentAlignment = Alignment.Center,
    ) {
        Surface(
            modifier = Modifier.fillMaxWidth().widthIn(max = 460.dp),
            shape = RoundedCornerShape(18.dp),
            color = MaterialTheme.colorScheme.surface,
            tonalElevation = 1.dp,
            shadowElevation = 8.dp,
        ) {
            Column(
                Modifier.verticalScroll(rememberScrollState()).padding(24.dp),
                horizontalAlignment = Alignment.Start,
            ) {
                Box(
                    Modifier.size(46.dp)
                        .background(MaterialTheme.colorScheme.primaryContainer, RoundedCornerShape(13.dp)),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(
                        Icons.Outlined.AccountBalanceWallet,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.onPrimaryContainer,
                    )
                }
                Spacer(Modifier.height(18.dp))
                Text("Tu cuenta de ContaXcell", style = MaterialTheme.typography.headlineMedium)
                Spacer(Modifier.height(6.dp))
                Text(
                    "Tus cuentas se guardan primero en el m\u00f3vil y se sincronizan cuando hay conexi\u00f3n.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.height(20.dp))

                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (!registering) {
                        Button(onClick = { registering = false }, modifier = Modifier.weight(1f)) {
                            Text("Entrar")
                        }
                    } else {
                        OutlinedButton(onClick = { registering = false }, modifier = Modifier.weight(1f)) {
                            Text("Entrar")
                        }
                    }
                    if (registering) {
                        Button(onClick = { registering = true }, modifier = Modifier.weight(1f)) {
                            Text("Crear cuenta")
                        }
                    } else {
                        OutlinedButton(onClick = { registering = true }, modifier = Modifier.weight(1f)) {
                            Text("Crear cuenta")
                        }
                    }
                }
                Spacer(Modifier.height(16.dp))
                OutlinedTextField(
                    value = user,
                    onValueChange = { user = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Usuario") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
                    enabled = !state.busy,
                )
                Spacer(Modifier.height(10.dp))
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Contrase\u00f1a") },
                    singleLine = true,
                    visualTransformation = PasswordVisualTransformation(),
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Password,
                        imeAction = ImeAction.Done,
                    ),
                    keyboardActions = KeyboardActions(onDone = { submit() }),
                    enabled = !state.busy,
                    leadingIcon = { Icon(Icons.Outlined.Lock, contentDescription = null) },
                )
                if (registering && state.inviteRequired) {
                    Spacer(Modifier.height(10.dp))
                    OutlinedTextField(
                        value = inviteCode,
                        onValueChange = { inviteCode = it },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("C\u00f3digo de invitaci\u00f3n") },
                        singleLine = true,
                        enabled = !state.busy,
                    )
                }
                Spacer(Modifier.height(6.dp))
                TextButton(onClick = { showServer = !showServer }, enabled = !state.busy) {
                    Icon(Icons.Outlined.MoreHoriz, contentDescription = null)
                    Text(if (showServer) "Ocultar servidor" else "Cambiar el servidor")
                }
                if (showServer) {
                    OutlinedTextField(
                        value = server,
                        onValueChange = { server = it },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("Direcci\u00f3n del servidor") },
                        singleLine = true,
                        enabled = !state.busy,
                        supportingText = if (server.startsWith("http://") &&
                            !server.contains("localhost") && !server.contains("127.0.0.1")) {
                            { Text("Sin HTTPS, la contrase\u00f1a viaja sin cifrar.") }
                        } else null,
                    )
                }
                if (!state.error.isNullOrBlank()) {
                    Spacer(Modifier.height(10.dp))
                    Text(
                        state.error,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodyMedium,
                    )
                }
                Spacer(Modifier.height(18.dp))
                Button(
                    onClick = { submit() },
                    enabled = user.isNotBlank() && password.length >= 8 && server.isNotBlank() && !state.busy,
                    modifier = Modifier.fillMaxWidth().height(48.dp),
                ) {
                    if (state.busy) {
                        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                    } else {
                        Text(if (registering) "Crear cuenta" else "Entrar")
                    }
                }
                if (state.previousSessionAvailable) {
                    Spacer(Modifier.height(8.dp))
                    TextButton(
                        onClick = { onAction(AppAction.ContinueOffline) },
                        modifier = Modifier.fillMaxWidth(),
                        enabled = !state.busy,
                    ) {
                        Icon(Icons.Outlined.CloudOff, contentDescription = null)
                        Text("Seguir sin conexi\u00f3n")
                    }
                }
            }
        }
    }
}
