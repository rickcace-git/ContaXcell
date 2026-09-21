package com.contaxcell.app.data.sync

import com.contaxcell.app.data.remote.ContaXcellApi
import com.contaxcell.app.data.remote.HttpResult
import com.contaxcell.app.domain.Libro
import com.contaxcell.app.domain.Movimiento
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.encodeToJsonElement
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SyncEngineTest {
    private val json = Json { encodeDefaults = true; ignoreUnknownKeys = true }

    @Test
    fun conflictBacksUpServerAndRetriesLocalAgainstItsRevision() = runTest {
        val local = Libro.empty().copy(movimientos = listOf(Movimiento("2026-01-02", importe = 20.0)))
        val remote = Libro.empty().copy(movimientos = listOf(Movimiento("2026-01-01", importe = 10.0)))
        val api = FakeApi(
            uploadResponses = ArrayDeque(
                listOf(
                    HttpResult(409, bookEnvelope(7, remote)),
                    HttpResult(200, buildJsonObject { put("revision", JsonPrimitive(8)) }),
                ),
            ),
        )
        val sessions = MemorySessions(SyncSession("https://example.test", "ana", "token", 6, pending = true))
        val books = MemoryBooks(local)
        val events = mutableListOf<SyncEvent>()
        val engine = SyncEngine(api, sessions, books, SyncEventSink(events::add), json)

        val result = engine.push()

        assertEquals(SyncResult.Uploaded(8, false), result)
        assertEquals(listOf(6, 7), api.uploadedRevisions)
        assertEquals(remote, books.backups.single())
        assertFalse(sessions.read().pending)
        assertEquals(8, sessions.read().lastRevision)
        assertTrue(events.any { it is SyncEvent.ConflictBackedUp })
    }

    @Test
    fun pullNeverOverwritesPendingLocalChanges() = runTest {
        val local = Libro.empty().copy(movimientos = listOf(Movimiento("2026-01-02", importe = 20.0)))
        val api = FakeApi(uploadResponses = ArrayDeque(listOf(HttpResult(500))))
        val sessions = MemorySessions(SyncSession("https://example.test", "ana", "token", 2, pending = true))
        val books = MemoryBooks(local)

        SyncEngine(api, sessions, books, json = json).pull()

        assertEquals(local, books.current)
        assertEquals(1, api.uploadCalls)
        assertEquals(0, api.downloadCalls)
    }

    @Test
    fun remoteDownloadBacksUpUnlinkedLocalBookBeforeReplacing() = runTest {
        val local = Libro.empty().copy(movimientos = listOf(Movimiento("2026-01-02", importe = 20.0)))
        val remote = Libro.empty().copy(movimientos = listOf(Movimiento("2026-01-03", importe = 30.0)))
        val api = FakeApi(downloadResponse = HttpResult(200, bookEnvelope(4, remote)))
        val sessions = MemorySessions(SyncSession("https://example.test", "ana", "token", 0))
        val books = MemoryBooks(local)

        val result = SyncEngine(api, sessions, books, json = json).pull()

        assertEquals(SyncResult.Downloaded(4, true), result)
        assertEquals(remote, books.current)
        assertEquals(local, books.backups.single())
        assertEquals(4, sessions.read().lastRevision)
    }

    @Test
    fun unauthorizedResponseExpiresSessionWithoutClearingPending() = runTest {
        val api = FakeApi(uploadResponses = ArrayDeque(listOf(HttpResult(401))))
        val sessions = MemorySessions(SyncSession("https://example.test", "ana", "token", 2, pending = true))

        val result = SyncEngine(api, sessions, MemoryBooks(Libro.empty()), json = json).push()

        assertEquals(SyncResult.SessionExpired, result)
        assertTrue(sessions.read().expired)
        assertTrue(sessions.read().pending)
    }

    private fun bookEnvelope(revision: Int, book: Libro) = buildJsonObject {
        put("revision", JsonPrimitive(revision))
        put("libro", json.encodeToJsonElement(Libro.serializer(), book))
    }
}

private class MemorySessions(initial: SyncSession) : SessionStore {
    var value = initial
    override suspend fun read() = value
    override suspend fun write(session: SyncSession) { value = session }
    override suspend fun clear() { value = SyncSession() }
}

private class MemoryBooks(overrideBook: Libro?) : SyncBookStore {
    var current = overrideBook
    val backups = mutableListOf<Libro>()
    override suspend fun read() = current
    override suspend fun replace(book: Libro, reason: String) { current = book }
    override suspend fun backup(book: Libro, reason: String): String {
        backups += book
        return "copias/test.json"
    }
}

private class FakeApi(
    val uploadResponses: ArrayDeque<HttpResult> = ArrayDeque(),
    val downloadResponse: HttpResult = HttpResult(500),
) : ContaXcellApi {
    val uploadedRevisions = mutableListOf<Int>()
    var uploadCalls = 0
    var downloadCalls = 0
    override suspend fun health(serverUrl: String) = HttpResult(200)
    override suspend fun register(serverUrl: String, username: String, password: String, invitationCode: String) = HttpResult(500)
    override suspend fun login(serverUrl: String, username: String, password: String) = HttpResult(500)
    override suspend fun changePassword(serverUrl: String, token: String, currentPassword: String, newPassword: String) = HttpResult(500)
    override suspend fun downloadBook(serverUrl: String, token: String): HttpResult {
        downloadCalls++
        return downloadResponse
    }
    override suspend fun uploadBook(serverUrl: String, token: String, baseRevision: Int, book: JsonObject): HttpResult {
        uploadCalls++
        uploadedRevisions += baseRevision
        return uploadResponses.removeFirst()
    }
    override suspend fun searchQuotes(serverUrl: String, token: String, query: String) = HttpResult(500)
    override suspend fun downloadQuotes(serverUrl: String, token: String, symbol: String, from: String) = HttpResult(500)
}
