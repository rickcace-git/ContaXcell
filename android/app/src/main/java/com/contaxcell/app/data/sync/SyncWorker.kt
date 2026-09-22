package com.contaxcell.app.data.sync

import android.content.Context
import androidx.work.BackoffPolicy
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.ExistingWorkPolicy
import androidx.work.NetworkType
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.contaxcell.app.data.local.JsonLibroStore
import com.contaxcell.app.data.remote.OkHttpContaXcellApi
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** Installed by the application composition root; keeps WorkManager independent from a DI framework. */
object SyncRuntime {
    @Volatile
    var engineFactory: ((Context) -> SyncEngine)? = null

    fun engine(context: Context): SyncEngine = engineFactory?.invoke(context) ?: defaultEngine(context)

    private fun defaultEngine(context: Context): SyncEngine {
        val app = context.applicationContext
        val store = JsonLibroStore(app.filesDir)
        return SyncEngine(
            OkHttpContaXcellApi(),
            SharedPreferencesSessionStore(app),
            object : SyncBookStore {
                override suspend fun read() = withContext(Dispatchers.IO) { store.load().libro }
                override suspend fun replace(book: com.contaxcell.app.domain.Libro, reason: String) {
                    withContext(Dispatchers.IO) { store.replace(book, reason) }
                }
                override suspend fun backup(book: com.contaxcell.app.domain.Libro, reason: String): String? =
                    withContext(Dispatchers.IO) { store.backup(book, reason)?.absolutePath }
            },
        )
    }
}

class SyncWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {
    override suspend fun doWork(): Result {
        val engine = SyncRuntime.engine(applicationContext)
        return when (engine.syncNow()) {
            SyncResult.Current,
            SyncResult.NoSession,
            SyncResult.SessionExpired,
            is SyncResult.Uploaded,
            is SyncResult.Downloaded -> Result.success()
            SyncResult.Offline -> Result.retry()
            is SyncResult.Failed -> if (runAttemptCount < 3) Result.retry() else Result.failure()
        }
    }
}

object SyncScheduler {
    private const val PERIODIC_WORK = "contaxcell-periodic-sync"
    private const val IMMEDIATE_WORK = "contaxcell-immediate-sync"

    private val connected = Constraints.Builder()
        .setRequiredNetworkType(NetworkType.CONNECTED)
        .build()

    fun schedulePeriodic(context: Context) {
        val request = PeriodicWorkRequestBuilder<SyncWorker>(15, TimeUnit.MINUTES)
            .setConstraints(connected)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniquePeriodicWork(
            PERIODIC_WORK,
            ExistingPeriodicWorkPolicy.KEEP,
            request,
        )
    }

    fun requestImmediate(context: Context) {
        val request = OneTimeWorkRequestBuilder<SyncWorker>()
            .setConstraints(connected)
            .setBackoffCriteria(BackoffPolicy.EXPONENTIAL, 30, TimeUnit.SECONDS)
            .build()
        WorkManager.getInstance(context).enqueueUniqueWork(
            IMMEDIATE_WORK,
            ExistingWorkPolicy.REPLACE,
            request,
        )
    }

    fun cancel(context: Context) {
        WorkManager.getInstance(context).cancelUniqueWork(PERIODIC_WORK)
        WorkManager.getInstance(context).cancelUniqueWork(IMMEDIATE_WORK)
    }
}
