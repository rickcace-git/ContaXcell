package com.contaxcell.app

import android.app.Application
import androidx.work.Configuration

/** Application process entry. WorkManager is used only for resilient background sync. */
class ContaXcellApplication : Application(), Configuration.Provider {
    override val workManagerConfiguration: Configuration
        get() = Configuration.Builder()
            .setMinimumLoggingLevel(if (BuildConfig.DEBUG) android.util.Log.DEBUG else android.util.Log.INFO)
            .build()
}
