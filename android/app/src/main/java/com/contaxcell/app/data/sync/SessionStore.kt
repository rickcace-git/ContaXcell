package com.contaxcell.app.data.sync

import android.content.Context
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock

data class SyncSession(
    val serverUrl: String = DEFAULT_SERVER_URL,
    val username: String = "",
    val token: String = "",
    val lastRevision: Int = 0,
    val pending: Boolean = false,
    val expired: Boolean = false,
) {
    val isSignedIn: Boolean get() = token.isNotBlank()

    companion object {
        const val DEFAULT_SERVER_URL = "http://localhost:8000"
    }
}

interface SessionStore {
    suspend fun read(): SyncSession
    suspend fun write(session: SyncSession)
    suspend fun clear()

    suspend fun update(transform: (SyncSession) -> SyncSession): SyncSession {
        val changed = transform(read())
        write(changed)
        return changed
    }
}

/**
 * App-private SharedPreferences persistence. Android encrypts the app sandbox at rest;
 * callers should still avoid logging [SyncSession.token].
 */
class SharedPreferencesSessionStore(context: Context) : SessionStore {
    private val preferences = context.applicationContext.getSharedPreferences(PREFERENCES, Context.MODE_PRIVATE)
    private val mutex = Mutex()

    override suspend fun read(): SyncSession = mutex.withLock { readUnlocked() }

    override suspend fun write(session: SyncSession) {
        mutex.withLock { writeUnlocked(session) }
    }

    override suspend fun clear() {
        mutex.withLock { preferences.edit().clear().commit() }
    }

    override suspend fun update(transform: (SyncSession) -> SyncSession): SyncSession = mutex.withLock {
        val changed = transform(readUnlocked())
        writeUnlocked(changed)
        changed
    }

    private fun readUnlocked() = SyncSession(
        serverUrl = preferences.getString(KEY_SERVER, null)
            ?.trimEnd('/')
            ?.takeIf(String::isNotBlank)
            ?: SyncSession.DEFAULT_SERVER_URL,
        username = preferences.getString(KEY_USER, "").orEmpty(),
        token = preferences.getString(KEY_TOKEN, "").orEmpty(),
        lastRevision = preferences.getInt(KEY_REVISION, 0).coerceAtLeast(0),
        pending = preferences.getBoolean(KEY_PENDING, false),
        expired = preferences.getBoolean(KEY_EXPIRED, false),
    )

    private fun writeUnlocked(session: SyncSession) {
        preferences.edit()
            .putString(KEY_SERVER, session.serverUrl.trimEnd('/'))
            .putString(KEY_USER, session.username)
            .putString(KEY_TOKEN, session.token)
            .putInt(KEY_REVISION, session.lastRevision.coerceAtLeast(0))
            .putBoolean(KEY_PENDING, session.pending)
            .putBoolean(KEY_EXPIRED, session.expired)
            .commit()
    }

    private companion object {
        const val PREFERENCES = "contaxcell_sync_session"
        const val KEY_SERVER = "server"
        const val KEY_USER = "user"
        const val KEY_TOKEN = "token"
        const val KEY_REVISION = "last_revision"
        const val KEY_PENDING = "pending"
        const val KEY_EXPIRED = "expired"
    }
}
