package com.contaxcell.app.data.sync

import com.contaxcell.app.data.remote.ContaXcellApi
import com.contaxcell.app.data.remote.NetworkUnavailableException
import com.contaxcell.app.domain.Libro
import java.util.concurrent.atomic.AtomicLong
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.SerializationException
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.decodeFromJsonElement
import kotlinx.serialization.json.encodeToJsonElement
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonPrimitive

/** Adapter implemented by the app's authoritative local Libro repository. */
interface SyncBookStore {
    suspend fun read(): Libro?

    /** Replaces the local book atomically and keeps the usual pre-replacement backup. */
    suspend fun replace(book: Libro, reason: String)

    /** Stores an extra recovery copy without changing the current book. Returns a user-facing location. */
    suspend fun backup(book: Libro, reason: String): String?
}

fun interface SyncEventSink {
    suspend fun emit(event: SyncEvent)
}

sealed interface SyncEvent {
    data object Synced : SyncEvent
    data object Offline : SyncEvent
    data object SessionExpired : SyncEvent
    data class ConflictBackedUp(val location: String?) : SyncEvent
    data class Downloaded(val revision: Int, val localWasUnlinked: Boolean) : SyncEvent
    data class UnexpectedServerResponse(val statusCode: Int) : SyncEvent
}

sealed interface SyncResult {
    data object Current : SyncResult
    data object NoSession : SyncResult
    data object Offline : SyncResult
    data object SessionExpired : SyncResult
    data class Uploaded(val revision: Int, val stillPending: Boolean) : SyncResult
    data class Downloaded(val revision: Int, val localWasUnlinked: Boolean) : SyncResult
    data class Failed(val statusCode: Int? = null) : SyncResult
}

/**
 * Offline-first synchronizer mirroring the desktop implementation.
 *
 * The local repository is authoritative while an upload is pending. On a 409 the remote
 * version is backed up, then the current local book is retried against the returned revision.
 */
class SyncEngine(
    private val api: ContaXcellApi,
    private val sessions: SessionStore,
    private val books: SyncBookStore,
    private val events: SyncEventSink = SyncEventSink {},
    private val json: Json = Json {
        ignoreUnknownKeys = true
        encodeDefaults = true
    },
) {
    private val operationMutex = Mutex()
    private val editGeneration = AtomicLong(0)

    suspend fun markPending() {
        val session = sessions.read()
        if (!session.isSignedIn) return
        editGeneration.incrementAndGet()
        sessions.update { it.copy(pending = true) }
    }

    suspend fun confirmDownloadedRevision(revision: Int) {
        sessions.update { it.copy(lastRevision = revision.coerceAtLeast(0)) }
    }

    suspend fun syncNow(): SyncResult = operationMutex.withLock {
        val session = sessions.read()
        when {
            !session.isSignedIn -> SyncResult.NoSession
            session.expired -> SyncResult.SessionExpired
            session.pending -> pushLocked(session)
            else -> pullLocked(session)
        }
    }

    suspend fun push(): SyncResult = operationMutex.withLock { pushLocked(sessions.read()) }

    suspend fun pull(): SyncResult = operationMutex.withLock { pullLocked(sessions.read()) }

    fun statusText(session: SyncSession): String = when {
        !session.isSignedIn -> "Sin cuenta."
        session.expired -> "Sesión caducada: entra de nuevo para seguir sincronizando."
        session.pending -> "Hay cambios pendientes de subir. Se subirán al volver la conexión."
        else -> "Al día con el servidor."
    }

    private suspend fun pushLocked(initial: SyncSession): SyncResult {
        if (!initial.isSignedIn) return SyncResult.NoSession
        if (initial.expired) return SyncResult.SessionExpired
        if (!initial.pending) return SyncResult.Current
        val local = books.read() ?: return SyncResult.Failed()
        val serialized = json.encodeToJsonElement(Libro.serializer(), local).let { it as JsonObject }
        val generationAtStart = editGeneration.get()
        var baseRevision = initial.lastRevision
        var conflictReported = false

        repeat(MAX_CONFLICT_RETRIES + 1) {
            val response = try {
                api.uploadBook(initial.serverUrl, initial.token, baseRevision, serialized)
            } catch (_: NetworkUnavailableException) {
                events.emit(SyncEvent.Offline)
                return SyncResult.Offline
            }
            when (response.statusCode) {
                200 -> {
                    val revision = response.objectBody?.get("revision")?.jsonPrimitive?.intOrNull
                        ?: return unexpected(response.statusCode)
                    val changedWhileUploading = editGeneration.get() != generationAtStart
                    sessions.update {
                        it.copy(lastRevision = revision, pending = changedWhileUploading)
                    }
                    events.emit(SyncEvent.Synced)
                    return SyncResult.Uploaded(revision, changedWhileUploading)
                }
                409 -> {
                    val body = response.objectBody ?: return unexpected(response.statusCode)
                    val revision = body["revision"]?.jsonPrimitive?.intOrNull
                        ?: return unexpected(response.statusCode)
                    val remote = decodeBook(body["libro"])
                    val location = remote?.let { books.backup(it, "conflicto-sincronia") }
                    if (!conflictReported) {
                        conflictReported = true
                        events.emit(SyncEvent.ConflictBackedUp(location))
                    }
                    baseRevision = revision
                }
                401 -> return expireSession()
                else -> return unexpected(response.statusCode)
            }
        }
        return SyncResult.Failed(409)
    }

    private suspend fun pullLocked(session: SyncSession): SyncResult {
        if (!session.isSignedIn) return SyncResult.NoSession
        if (session.expired) return SyncResult.SessionExpired
        // Never replace a local edit that has not been uploaded yet.
        if (session.pending) return pushLocked(session)
        val response = try {
            api.downloadBook(session.serverUrl, session.token)
        } catch (_: NetworkUnavailableException) {
            events.emit(SyncEvent.Offline)
            return SyncResult.Offline
        }
        if (response.statusCode == 401) return expireSession()
        if (response.statusCode != 200) return unexpected(response.statusCode)
        val body = response.objectBody ?: return unexpected(response.statusCode)
        val revision = body["revision"]?.jsonPrimitive?.intOrNull
            ?: return unexpected(response.statusCode)
        val remoteElement = body["libro"]
        val remote = decodeBook(remoteElement)
        if (remoteElement != null && remoteElement !is kotlinx.serialization.json.JsonNull && remote == null) {
            return unexpected(response.statusCode)
        }
        val local = books.read()

        if (remote == null) {
            val changed = sessions.update {
                it.copy(lastRevision = revision, pending = local != null)
            }
            // A brand-new remote account must receive the local book immediately;
            // marking it pending first makes this durable if the upload loses connectivity.
            return if (local == null) SyncResult.Current else pushLocked(changed)
        }
        if (revision == session.lastRevision) return SyncResult.Current
        if (local == remote) {
            sessions.update { it.copy(lastRevision = revision) }
            return SyncResult.Current
        }

        val localWasUnlinked = session.lastRevision == 0 && local != null
        if (localWasUnlinked) books.backup(local!!, "antes-de-descarga-sin-vinculo")
        books.replace(remote, "antes-de-descarga")
        sessions.update { it.copy(lastRevision = revision, pending = false) }
        events.emit(SyncEvent.Downloaded(revision, localWasUnlinked))
        return SyncResult.Downloaded(revision, localWasUnlinked)
    }

    private fun decodeBook(element: kotlinx.serialization.json.JsonElement?): Libro? {
        if (element == null || element is kotlinx.serialization.json.JsonNull) return null
        return try {
            json.decodeFromJsonElement(Libro.serializer(), element).normalized()
        } catch (_: SerializationException) {
            null
        } catch (_: IllegalArgumentException) {
            null
        }
    }

    private suspend fun expireSession(): SyncResult.SessionExpired {
        sessions.update { it.copy(expired = true) }
        events.emit(SyncEvent.SessionExpired)
        return SyncResult.SessionExpired
    }

    private suspend fun unexpected(status: Int): SyncResult.Failed {
        events.emit(SyncEvent.UnexpectedServerResponse(status))
        return SyncResult.Failed(status)
    }

    private companion object {
        const val MAX_CONFLICT_RETRIES = 3
    }
}
