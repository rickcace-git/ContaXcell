package com.contaxcell.app.data.update

import java.io.File
import java.io.IOException
import java.math.BigInteger
import java.security.KeyFactory
import java.security.MessageDigest
import java.security.PublicKey
import java.security.Signature
import java.security.spec.RSAPublicKeySpec
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import okhttp3.OkHttpClient
import okhttp3.Request

/*
 * La app se actualiza desde el servidor, como el programa del ordenador:
 *
 * 1. `python publicar.py --android <apk>` deja en el servidor el APK, una nota
 *    (android.json: qué versión es, su tamaño, su SHA-256 y lo que trae) y la
 *    firma de esa nota, hecha con la llave que solo vive en el ordenador de
 *    quien publica.
 * 2. Al abrir la app se piden la nota y la firma con la sesión: solo las
 *    cuentas aceptadas y sin vetar reciben versiones nuevas.
 * 3. Si la firma no es de esa llave, no se hace nada. Si lo es y la versión
 *    es más nueva, se pregunta.
 * 4. Se baja el APK, se comprueba que es justo el de la nota y se abre el
 *    instalador de Android, donde la persona pulsa «Instalar». Ese último paso
 *    no se puede saltar: Android no deja que una app se cambie sola.
 *
 * Android, además, solo instala encima un APK firmado con la misma llave que
 * el que hay. Son dos cerrojos: el de Android y el nuestro.
 */

data class AppChange(val title: String, val detail: String = "")

/** Lo que trajo una versión de la app. `date` es AAAA-MM-DD, o "" si no se sabe. */
data class AppRelease(
    val versionCode: Int,
    val versionName: String,
    val changes: List<AppChange>,
    val date: String = "",
)

data class AppUpdate(
    val versionCode: Int,
    val versionName: String,
    val path: String,
    val size: Long,
    val sha256: String,
    val notes: String = "",
    val releases: List<AppRelease> = emptyList(),
) {
    /** Lo que le falta a quien tiene `currentCode`, la versión más nueva primero. */
    fun changesSince(currentCode: Int): List<AppRelease> =
        releases.filter { it.versionCode > currentCode && it.changes.isNotEmpty() }
}

/** Lo del servidor no viene firmado por quien administra ContaXcell, o el APK no es el de la nota. */
class UntrustedUpdateException(message: String) : Exception(message)

/** La cuenta no recibe versiones nuevas: en espera, vetada o con la sesión caducada. */
class UpdateNotAllowedException : Exception("Tu cuenta todavía no recibe actualizaciones.")

class FetchResult(val status: Int, val body: ByteArray = ByteArray(0))

/** Lo que hace falta del servidor. Separado para poder probarlo sin red. */
interface UpdateFetcher {
    suspend fun get(url: String, token: String): FetchResult

    /** Baja `url` a `target` y devuelve el código HTTP. */
    suspend fun download(url: String, token: String, target: File, onProgress: (Float) -> Unit): Int
}

object UpdateNote {
    const val PREFIX = "/api/actualizacion/"
    const val NOTE = PREFIX + "android.json"
    const val SIGNATURE = PREFIX + "android.json.firma"

    fun officialKey(): PublicKey = KeyFactory.getInstance("RSA").generatePublic(
        RSAPublicKeySpec(BigInteger(UpdateKey.MODULUS), BigInteger.valueOf(UpdateKey.EXPONENT)),
    )

    /** RSA con SHA-256 (PKCS#1 v1.5): lo mismo que firma `escritorio/contaxcell/firma.py`. */
    fun verify(note: ByteArray, signature: ByteArray, key: PublicKey): Boolean = runCatching {
        Signature.getInstance("SHA256withRSA").run {
            initVerify(key)
            update(note)
            verify(signature)
        }
    }.getOrDefault(false)

    fun parse(note: ByteArray): AppUpdate = try {
        val root = Json.parseToJsonElement(note.decodeToString()).jsonObject
        AppUpdate(
            versionCode = root.int("versionCode"),
            versionName = root.text("versionName"),
            path = root.text("archivo"),
            size = root["tamano"]?.jsonPrimitive?.longOrNull ?: error("sin tamaño"),
            sha256 = root.text("sha256").lowercase(),
            notes = root["notas"]?.jsonPrimitive?.contentOrNull.orEmpty(),
            releases = releases(root["historial"] as? JsonArray),
        )
    } catch (_: Exception) {
        throw UntrustedUpdateException("La nota de la actualización está mal escrita.")
    }

    /**
     * El historial que lleva la app dentro (assets/historial.json, lo escribe
     * GitHub al compilarla): todas las versiones publicadas, la más nueva
     * primero. Vacío si no está o no se entiende, que no es para romper nada.
     */
    fun parseHistory(bytes: ByteArray): List<AppRelease> = runCatching {
        releases(Json.parseToJsonElement(bytes.decodeToString()) as? JsonArray)
    }.getOrDefault(emptyList())

    private fun releases(array: JsonArray?): List<AppRelease> = array.orEmpty().map { entry ->
        val release = entry.jsonObject
        AppRelease(
            versionCode = release.int("versionCode"),
            versionName = release.text("versionName"),
            changes = (release["cambios"] as? JsonArray).orEmpty().mapNotNull { change ->
                val item = change.jsonObject
                val title = item["titulo"]?.jsonPrimitive?.contentOrNull?.trim().orEmpty()
                if (title.isEmpty()) null
                else AppChange(title, item["detalle"]?.jsonPrimitive?.contentOrNull?.trim().orEmpty())
            },
            date = release["fecha"]?.jsonPrimitive?.contentOrNull.orEmpty(),
        )
    }

    private fun JsonObject.int(key: String): Int = this[key]?.jsonPrimitive?.intOrNull ?: error("sin $key")
    private fun JsonObject.text(key: String): String =
        this[key]?.jsonPrimitive?.contentOrNull?.takeIf(String::isNotBlank) ?: error("sin $key")
}

class AppUpdater(
    private val fetcher: UpdateFetcher = OkHttpUpdateFetcher(),
    private val key: PublicKey = UpdateNote.officialKey(),
) {
    /** La versión nueva si la hay; null si no hay o si ya se tiene esa. */
    suspend fun check(serverUrl: String, token: String, currentCode: Int): AppUpdate? {
        val base = serverUrl.trimEnd('/')
        val note = fetcher.get(base + UpdateNote.NOTE, token)
        when (note.status) {
            200 -> Unit
            404 -> return null
            401, 403 -> throw UpdateNotAllowedException()
            else -> throw IOException("El servidor ha contestado ${note.status}.")
        }
        val signature = fetcher.get(base + UpdateNote.SIGNATURE, token)
        if (signature.status != 200 || !UpdateNote.verify(note.body, signature.body, key)) {
            throw UntrustedUpdateException(
                "La actualización del servidor no viene firmada por quien administra ContaXcell. " +
                    "No se ha instalado nada.",
            )
        }
        val update = UpdateNote.parse(note.body)
        if (!update.path.startsWith(UpdateNote.PREFIX)) {
            throw UntrustedUpdateException("La actualización apunta fuera de su sitio.")
        }
        return update.takeIf { it.versionCode > currentCode }
    }

    /** Baja el APK a `folder` y comprueba que es justo el de la nota. Si no, lo borra. */
    suspend fun download(
        serverUrl: String,
        token: String,
        update: AppUpdate,
        folder: File,
        onProgress: (Float) -> Unit,
    ): File = withContext(Dispatchers.IO) {
        folder.mkdirs()
        // Los que quedaran de otras veces sobran.
        folder.listFiles()?.forEach { it.delete() }
        val target = File(folder, "ContaXcell-${update.versionCode}.apk")
        val status = fetcher.download(serverUrl.trimEnd('/') + update.path, token, target, onProgress)
        when (status) {
            200 -> Unit
            401, 403 -> throw UpdateNotAllowedException()
            else -> throw IOException("El servidor ha contestado $status.")
        }
        if (target.length() != update.size || sha256(target) != update.sha256) {
            target.delete()
            throw UntrustedUpdateException(
                "El archivo descargado no es el que anuncia la actualización. No se ha instalado nada.",
            )
        }
        target
    }

    private fun sha256(file: File): String {
        val digest = MessageDigest.getInstance("SHA-256")
        file.inputStream().use { input ->
            val buffer = ByteArray(64 * 1024)
            while (true) {
                val read = input.read(buffer)
                if (read < 0) break
                digest.update(buffer, 0, read)
            }
        }
        return digest.digest().joinToString("") { "%02x".format(it) }
    }
}

class OkHttpUpdateFetcher(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build(),
) : UpdateFetcher {
    override suspend fun get(url: String, token: String): FetchResult = withContext(Dispatchers.IO) {
        client.newCall(request(url, token)).execute().use { response ->
            FetchResult(response.code, if (response.isSuccessful) response.body?.bytes() ?: ByteArray(0) else ByteArray(0))
        }
    }

    override suspend fun download(url: String, token: String, target: File, onProgress: (Float) -> Unit): Int =
        withContext(Dispatchers.IO) {
            client.newCall(request(url, token)).execute().use { response ->
                if (!response.isSuccessful) return@use response.code
                val body = response.body ?: return@use 500
                val total = body.contentLength().takeIf { it > 0 }
                var copied = 0L
                body.byteStream().use { input ->
                    target.outputStream().use { output ->
                        val buffer = ByteArray(64 * 1024)
                        while (true) {
                            val read = input.read(buffer)
                            if (read < 0) break
                            output.write(buffer, 0, read)
                            copied += read
                            if (total != null) onProgress(copied.toFloat() / total)
                        }
                    }
                }
                response.code
            }
        }

    private fun request(url: String, token: String): Request =
        Request.Builder().url(url).header("Authorization", "Bearer $token").get().build()
}
