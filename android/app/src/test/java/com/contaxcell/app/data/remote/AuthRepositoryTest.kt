package com.contaxcell.app.data.remote

import com.contaxcell.app.data.sync.SessionStore
import com.contaxcell.app.data.sync.SyncSession
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AuthRepositoryTest {
    @Test
    fun loginPersistsServerCanonicalUsernameAndToken() = runTest {
        val api = AuthFakeApi().apply {
            loginResponse = HttpResult(200, tokenBody("fresh", "ana"))
        }
        val sessions = AuthMemorySessions()

        val session = AuthRepository(api, sessions).login("  Ana  ", "contrasena1", "https://sync.example/")

        assertEquals("ana", session.username)
        assertEquals("fresh", session.token)
        assertEquals("https://sync.example", session.serverUrl)
        assertFalse(session.expired)
        assertEquals(session, sessions.value)
    }

    @Test
    fun changingAccountInvokesDataSeparationBeforePersistingNewSession() = runTest {
        val api = AuthFakeApi().apply { loginResponse = HttpResult(200, tokenBody("b", "bea")) }
        val sessions = AuthMemorySessions(SyncSession("https://old.example", "ana", "a", 9, pending = true))
        var change: Pair<String, String>? = null
        val repository = AuthRepository(api, sessions, AccountChangeHandler { old, new -> change = old to new })

        val result = repository.login("bea", "contrasena2", "https://new.example")

        assertEquals("ana" to "bea", change)
        assertEquals(0, result.lastRevision)
        assertFalse(result.pending)
    }

    @Test
    fun invitationErrorIsTypedForSimplifiedUiRetry() = runTest {
        val api = AuthFakeApi().apply {
            registerResponse = HttpResult(403, buildJsonObject { put("detail", JsonPrimitive("Hace falta código")) })
        }
        val error = runCatching {
            AuthRepository(api, AuthMemorySessions()).register("ana", "contrasena1", "https://sync.example")
        }.exceptionOrNull() as AuthenticationException

        assertEquals(AuthenticationException.Kind.INVITATION_REQUIRED, error.kind)
        assertEquals("Hace falta código", error.message)
    }

    @Test
    fun unauthorizedPasswordChangeExpiresButKeepsOfflineSessionData() = runTest {
        val sessions = AuthMemorySessions(SyncSession("https://sync.example", "ana", "old", 3, pending = true))
        val api = AuthFakeApi().apply { passwordResponse = HttpResult(401) }

        runCatching { AuthRepository(api, sessions).changePassword("contrasena1", "contrasena2") }

        assertTrue(sessions.value.expired)
        assertTrue(sessions.value.pending)
        assertEquals("old", sessions.value.token)
    }

    private fun tokenBody(token: String, username: String) = buildJsonObject {
        put("token", JsonPrimitive(token))
        put("usuario", JsonPrimitive(username))
    }
}

private class AuthMemorySessions(initial: SyncSession = SyncSession()) : SessionStore {
    var value = initial
    override suspend fun read() = value
    override suspend fun write(session: SyncSession) { value = session }
    override suspend fun clear() { value = SyncSession() }
}

private class AuthFakeApi : ContaXcellApi {
    var loginResponse = HttpResult(500)
    var registerResponse = HttpResult(500)
    var passwordResponse = HttpResult(500)
    override suspend fun health(serverUrl: String) = HttpResult(200)
    override suspend fun register(serverUrl: String, username: String, password: String, invitationCode: String) = registerResponse
    override suspend fun login(serverUrl: String, username: String, password: String) = loginResponse
    override suspend fun changePassword(serverUrl: String, token: String, currentPassword: String, newPassword: String) = passwordResponse
    override suspend fun downloadBook(serverUrl: String, token: String) = HttpResult(500)
    override suspend fun uploadBook(serverUrl: String, token: String, baseRevision: Int, book: JsonObject) = HttpResult(500)
    override suspend fun searchQuotes(serverUrl: String, token: String, query: String) = HttpResult(500)
    override suspend fun downloadQuotes(serverUrl: String, token: String, symbol: String, from: String) = HttpResult(500)
}
