package com.contaxcell.app.data.sync

/**
 * Por qué se dio la sesión por caducada la última vez, en palabras que se
 * pueden enseñar. Nunca guarda la ficha: solo su forma (largo y trozos), que
 * basta para saber si el móvil mandó una ficha vacía o rota.
 */
object SyncDiagnostics {
    @Volatile
    var lastExpiry: String = ""
        private set

    fun expired(request: String, serverDetail: String?, token: String) {
        val shape = if (token.isBlank()) "sin ficha" else "ficha de ${token.length} caracteres en ${token.split('.').size} trozos"
        val detail = serverDetail?.takeIf(String::isNotBlank) ?: "sin motivo"
        lastExpiry = "$request → 401: «$detail» ($shape)"
    }
}
