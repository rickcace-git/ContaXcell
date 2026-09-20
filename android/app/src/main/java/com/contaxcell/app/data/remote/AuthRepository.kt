package com.contaxcell.app.data.remote

import com.contaxcell.app.data.sync.SessionStore
import com.contaxcell.app.data.sync.SyncSession
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive

class AuthenticationException(
    message: String,
    val kind: Kind,
) : Exception(message) {
    enum class Kind {
        INVALID_INPUT,
        INVALID_CREDENTIALS,
        USERNAME_TAKEN,
        INVITATION_REQUIRED,
        CURRENT_PASSWORD_WRONG,
        RATE_LIMITED,
        SESSION_EXPIRED,
        SERVER_ERROR,
        OFFLINE,
    }
}

fun interface AccountChangeHandler {
    /** Back up and detach the previous user's local book before the new session is saved. */
    suspend fun onAccountChanged(previousUsername: String, newUsername: String)
}

class AuthRepository(
    private val api: ContaXcellApi,
    private val sessions: SessionStore,
    private val accountChangeHandler: AccountChangeHandler = AccountChangeHandler { _, _ -> },
) {
    suspend fun session(): SyncSession = sessions.read()

    suspend fun register(
        username: String,
        password: String,
        serverUrl: String = "",
        invitationCode: String = "",
    ): SyncSession = authenticate(username, password, serverUrl, true, invitationCode)

    suspend fun login(
        username: String,
        password: String,
        serverUrl: String = "",
    ): SyncSession = authenticate(username, password, serverUrl, false, "")

    suspend fun changePassword(currentPassword: String, newPassword: String): SyncSession {
        val session = sessions.read()
        if (!session.isSignedIn) fail("En este dispositivo todavía no hay ninguna cuenta.", AuthenticationException.Kind.INVALID_INPUT)
        if (currentPassword.isBlank() || newPassword.isBlank()) {
            fail("Hacen falta la contraseña de ahora y la nueva.", AuthenticationException.Kind.INVALID_INPUT)
        }
        val response = callOrOffline {
            api.changePassword(session.serverUrl, session.token, currentPassword, newPassword)
        }
        when (response.statusCode) {
            200 -> Unit
            401 -> {
                sessions.write(session.copy(expired = true))
                fail("La sesión ha caducado. Entra de nuevo y vuelve a intentarlo.", AuthenticationException.Kind.SESSION_EXPIRED)
            }
            403 -> fail("La contraseña actual no es correcta.", AuthenticationException.Kind.CURRENT_PASSWORD_WRONG)
            422 -> fail(response.detail() ?: "La contraseña nueva no es válida.", AuthenticationException.Kind.INVALID_INPUT)
            429 -> fail(RATE_LIMIT_MESSAGE, AuthenticationException.Kind.RATE_LIMITED)
            else -> fail("El servidor ha respondido algo inesperado (${response.statusCode}).", AuthenticationException.Kind.SERVER_ERROR)
        }
        val token = response.objectBody?.get("token")?.jsonPrimitive?.contentOrNull
            ?.takeIf(String::isNotBlank)
            ?: fail("El servidor no ha devuelto una sesión válida.", AuthenticationException.Kind.SERVER_ERROR)
        return session.copy(token = token, expired = false).also { sessions.write(it) }
    }

    suspend fun logout() = sessions.clear()

    private suspend fun authenticate(
        rawUsername: String,
        password: String,
        requestedServerUrl: String,
        registering: Boolean,
        invitationCode: String,
    ): SyncSession {
        val username = rawUsername.trim()
        if (username.isBlank() || password.isBlank()) {
            fail("Hace falta el usuario y la contraseña.", AuthenticationException.Kind.INVALID_INPUT)
        }
        val old = sessions.read()
        val server = OkHttpContaXcellApi.normalizeServerUrl(
            requestedServerUrl.ifBlank { old.serverUrl },
        )
        val response = callOrOffline {
            if (registering) api.register(server, username, password, invitationCode)
            else api.login(server, username, password)
        }
        when (response.statusCode) {
            200, 201 -> Unit
            401 -> fail("El usuario o la contraseña no son correctos.", AuthenticationException.Kind.INVALID_CREDENTIALS)
            403 -> fail(
                response.detail() ?: "Este servidor pide un código de invitación.",
                if (registering) AuthenticationException.Kind.INVITATION_REQUIRED else AuthenticationException.Kind.SERVER_ERROR,
            )
            409 -> fail("Ese nombre de usuario ya está cogido.", AuthenticationException.Kind.USERNAME_TAKEN)
            422 -> fail(response.detail() ?: "El usuario o la contraseña no son válidos.", AuthenticationException.Kind.INVALID_INPUT)
            429 -> fail(RATE_LIMIT_MESSAGE, AuthenticationException.Kind.RATE_LIMITED)
            else -> fail("El servidor ha respondido algo inesperado (${response.statusCode}).", AuthenticationException.Kind.SERVER_ERROR)
        }
        val body = response.objectBody
        val token = body?.get("token")?.jsonPrimitive?.contentOrNull?.takeIf(String::isNotBlank)
            ?: fail("El servidor no ha devuelto una sesión válida.", AuthenticationException.Kind.SERVER_ERROR)
        val normalizedUser = body["usuario"]?.jsonPrimitive?.contentOrNull?.ifBlank { username } ?: username
        if (old.username.isNotBlank() && old.username != normalizedUser) {
            accountChangeHandler.onAccountChanged(old.username, normalizedUser)
        }
        return SyncSession(
            serverUrl = server,
            username = normalizedUser,
            token = token,
            lastRevision = if (old.username == normalizedUser) old.lastRevision else 0,
            pending = if (old.username == normalizedUser) old.pending else false,
            expired = false,
        ).also { sessions.write(it) }
    }

    private suspend fun callOrOffline(block: suspend () -> HttpResult): HttpResult = try {
        block()
    } catch (_: NetworkUnavailableException) {
        fail("No se ha podido hablar con el servidor. Comprueba la conexión y su dirección.", AuthenticationException.Kind.OFFLINE)
    }

    private fun fail(message: String, kind: AuthenticationException.Kind): Nothing =
        throw AuthenticationException(message, kind)

    private companion object {
        const val RATE_LIMIT_MESSAGE = "Demasiados intentos seguidos. Espera un rato y vuelve a probar."
    }
}
