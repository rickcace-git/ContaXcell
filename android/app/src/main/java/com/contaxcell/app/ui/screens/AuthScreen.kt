package com.contaxcell.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
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
import androidx.compose.material.icons.outlined.Visibility
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.AlertDialog
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
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import com.contaxcell.app.ui.AccountForm
import com.contaxcell.app.ui.AppAction
import com.contaxcell.app.ui.AuthUiState

/**
 * Tres pantallas, como en el escritorio: la de inicio pregunta qué quieres
 * hacer; «Iniciar sesión» pide usuario y contraseña; «Crear cuenta» pide además
 * el correo y la contraseña dos veces, y el código de invitación sale después,
 * en una ventanita aparte. Quien ya tenía sesión empieza en «Iniciar sesión».
 */
private const val START = "inicio"
private const val SIGN_IN = "entrar"
private const val CREATE = "crear"

@Composable
fun AuthScreen(state: AuthUiState.Gate, onAction: (AppAction) -> Unit) {
    val alreadyKnown = state.previousSessionAvailable || state.defaultUser.isNotBlank()
    var screen by rememberSaveable { mutableStateOf(if (alreadyKnown) SIGN_IN else START) }
    var showServer by rememberSaveable { mutableStateOf(false) }
    var server by rememberSaveable(state.defaultServer) { mutableStateOf(state.defaultServer) }

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
                when (screen) {
                    SIGN_IN -> SignInForm(state, server, onAction) { screen = START }
                    CREATE -> CreateForm(state, server, onAction) { screen = START }
                    else -> StartChoice(state, onAction, onSignIn = { screen = SIGN_IN }, onCreate = { screen = CREATE })
                }
                if (screen != START) {
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
                            label = { Text("Dirección del servidor") },
                            singleLine = true,
                            enabled = !state.busy,
                            supportingText = if (server.startsWith("http://") &&
                                !server.contains("localhost") && !server.contains("127.0.0.1")
                            ) {
                                { Text("Sin HTTPS, la contraseña viaja sin cifrar.") }
                            } else null,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ColumnScope.StartChoice(
    state: AuthUiState.Gate,
    onAction: (AppAction) -> Unit,
    onSignIn: () -> Unit,
    onCreate: () -> Unit,
) {
    Text("Tu cuenta de ContaXcell", style = MaterialTheme.typography.headlineMedium)
    Spacer(Modifier.height(6.dp))
    Text(
        "Tus cuentas se guardan primero en el móvil y se sincronizan con tu servidor cuando hay conexión.",
        style = MaterialTheme.typography.bodyMedium,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
    )
    Spacer(Modifier.height(22.dp))
    Button(onClick = onSignIn, modifier = Modifier.fillMaxWidth().height(48.dp)) { Text("Iniciar sesión") }
    Hint("Ya tengo cuenta")
    Spacer(Modifier.height(12.dp))
    OutlinedButton(onClick = onCreate, modifier = Modifier.fillMaxWidth().height(48.dp)) { Text("Crear cuenta") }
    Hint("Es la primera vez")
    if (state.previousSessionAvailable) {
        Spacer(Modifier.height(10.dp))
        TextButton(onClick = { onAction(AppAction.ContinueOffline) }, modifier = Modifier.fillMaxWidth()) {
            Icon(Icons.Outlined.CloudOff, contentDescription = null)
            Text("Seguir sin conexión")
        }
    }
}

@Composable
private fun SignInForm(
    state: AuthUiState.Gate,
    server: String,
    onAction: (AppAction) -> Unit,
    onBack: () -> Unit,
) {
    var user by rememberSaveable(state.defaultUser) { mutableStateOf(state.defaultUser) }
    var password by rememberSaveable { mutableStateOf("") }
    val ready = user.isNotBlank() && password.isNotEmpty() && server.isNotBlank() && !state.busy
    fun submit() { if (ready) onAction(AppAction.SignIn(user, password, server)) }

    Text("Iniciar sesión", style = MaterialTheme.typography.headlineMedium)
    Spacer(Modifier.height(16.dp))
    UserField(user, { user = it }, state.busy)
    Spacer(Modifier.height(10.dp))
    PasswordField("Contraseña", password, { password = it }, state.busy, ImeAction.Done) { submit() }
    ErrorText(state.error)
    Spacer(Modifier.height(18.dp))
    MainButton("Entrar", ready, state.busy) { submit() }
    BackButton(state.busy, onBack)
}

@Composable
private fun CreateForm(
    state: AuthUiState.Gate,
    server: String,
    onAction: (AppAction) -> Unit,
    onBack: () -> Unit,
) {
    var user by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var repeated by rememberSaveable { mutableStateOf("") }
    var localError by rememberSaveable { mutableStateOf<String?>(null) }
    var askingCode by rememberSaveable { mutableStateOf(false) }

    fun next() {
        localError = AccountForm.newAccountProblem(user, email, password, repeated)
        if (localError == null) askingCode = true
    }

    Text("Crear cuenta", style = MaterialTheme.typography.headlineMedium)
    Spacer(Modifier.height(16.dp))
    UserField(user, { user = it }, state.busy)
    Spacer(Modifier.height(10.dp))
    OutlinedTextField(
        value = email,
        onValueChange = { email = it },
        modifier = Modifier.fillMaxWidth(),
        label = { Text("Correo electrónico") },
        singleLine = true,
        enabled = !state.busy,
        supportingText = { Text("Por si algún día hay que restablecer la contraseña.") },
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Next),
    )
    Spacer(Modifier.height(4.dp))
    PasswordField("Contraseña", password, { password = it }, state.busy, ImeAction.Next) {}
    Spacer(Modifier.height(10.dp))
    PasswordField(
        "Repite la contraseña", repeated, { repeated = it }, state.busy, ImeAction.Done,
        isError = repeated.isNotEmpty() && repeated != password,
    ) { next() }
    ErrorText(localError ?: state.error)
    Spacer(Modifier.height(18.dp))
    MainButton("Crear cuenta", server.isNotBlank() && !state.busy, state.busy) { next() }
    BackButton(state.busy, onBack)

    if (askingCode) {
        InviteCodeDialog(
            onCancel = { askingCode = false },
            onConfirm = { code ->
                askingCode = false
                onAction(AppAction.Register(user, password, server, code, email.trim()))
            },
        )
    }
}

/** La ventanita del código, después de rellenar la cuenta: es lo último que falta. */
@Composable
private fun InviteCodeDialog(onCancel: () -> Unit, onConfirm: (String) -> Unit) {
    var code by rememberSaveable { mutableStateOf("") }
    AlertDialog(
        onDismissRequest = onCancel,
        title = { Text("Código de invitación") },
        text = {
            Column {
                Text("Te lo da quien administra ContaXcell. Sin él, el servidor no deja crear cuentas.")
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = code,
                    onValueChange = { code = it },
                    modifier = Modifier.fillMaxWidth(),
                    label = { Text("Código") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { onConfirm(code.trim()) }),
                )
            }
        },
        confirmButton = { Button(onClick = { onConfirm(code.trim()) }) { Text("Crear la cuenta") } },
        dismissButton = { TextButton(onClick = onCancel) { Text("Cancelar") } },
    )
}

@Composable
private fun UserField(value: String, onChange: (String) -> Unit, busy: Boolean) {
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        modifier = Modifier.fillMaxWidth(),
        label = { Text("Usuario") },
        singleLine = true,
        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Next),
        enabled = !busy,
    )
}

/** Con su ojo: para comprobar lo escrito, que en el móvil es fácil colar una letra. */
@Composable
private fun PasswordField(
    label: String,
    value: String,
    onChange: (String) -> Unit,
    busy: Boolean,
    imeAction: ImeAction,
    isError: Boolean = false,
    onDone: () -> Unit,
) {
    var visible by rememberSaveable { mutableStateOf(false) }
    OutlinedTextField(
        value = value,
        onValueChange = onChange,
        modifier = Modifier.fillMaxWidth(),
        label = { Text(label) },
        singleLine = true,
        isError = isError,
        visualTransformation = if (visible) VisualTransformation.None else PasswordVisualTransformation(),
        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password, imeAction = imeAction),
        keyboardActions = KeyboardActions(onDone = { onDone() }),
        enabled = !busy,
        leadingIcon = { Icon(Icons.Outlined.Lock, contentDescription = null) },
        trailingIcon = {
            IconButton(onClick = { visible = !visible }) {
                Icon(
                    if (visible) Icons.Outlined.VisibilityOff else Icons.Outlined.Visibility,
                    contentDescription = if (visible) "Ocultar la contraseña" else "Mostrar la contraseña",
                )
            }
        },
    )
}

@Composable
private fun MainButton(text: String, enabled: Boolean, busy: Boolean, onClick: () -> Unit) {
    Button(onClick = onClick, enabled = enabled, modifier = Modifier.fillMaxWidth().height(48.dp)) {
        if (busy) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp) else Text(text)
    }
}

@Composable
private fun BackButton(busy: Boolean, onBack: () -> Unit) {
    TextButton(onClick = onBack, enabled = !busy, modifier = Modifier.fillMaxWidth()) { Text("Volver") }
}

@Composable
private fun ErrorText(error: String?) {
    if (!error.isNullOrBlank()) {
        Spacer(Modifier.height(10.dp))
        Text(error, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodyMedium)
    }
}

@Composable
private fun Hint(text: String) {
    Text(
        text,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.onSurfaceVariant,
        modifier = Modifier.padding(top = 4.dp, start = 4.dp),
    )
}
