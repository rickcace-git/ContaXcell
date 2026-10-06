package com.contaxcell.app.data.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import java.io.File

/**
 * Lo que toca Android: dónde se deja el APK bajado, el permiso de «instalar
 * apps de esta fuente» y abrir el instalador del sistema.
 */
object ApkInstaller {
    /** Debajo de cache/, que es lo que comparte el FileProvider (res/xml/rutas_actualizacion.xml). */
    fun folder(context: Context): File = File(context.cacheDir, "actualizaciones")

    /** Si ContaXcell ya tiene permiso para instalar apps. Se da una vez, en Ajustes de Android. */
    fun canInstall(context: Context): Boolean = context.packageManager.canRequestPackageInstalls()

    /** Lleva directo al interruptor «Permitir de esta fuente» de ContaXcell. */
    fun openPermissionSettings(context: Context) {
        context.startActivity(
            Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${context.packageName}"))
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }

    /** Abre «¿Quieres actualizar esta aplicación?». Los datos de la app se mantienen. */
    fun install(context: Context, apk: File) {
        val uri = FileProvider.getUriForFile(context, "${context.packageName}.actualizaciones", apk)
        context.startActivity(
            Intent(Intent.ACTION_VIEW)
                .setDataAndType(uri, "application/vnd.android.package-archive")
                .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK),
        )
    }
}
