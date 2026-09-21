package com.contaxcell.app.data.local

import com.contaxcell.app.domain.Libro
import kotlinx.serialization.encodeToString
import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.json.Json
import java.io.File
import java.io.FileOutputStream
import java.nio.file.Files
import java.nio.file.StandardCopyOption
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class LibroLoadResult(val libro: Libro, val startupNotice: String = "", val quarantinedFile: File? = null)

interface LibroStore {
    fun load(): LibroLoadResult
    fun save(libro: Libro)
    fun backup(reason: String = "copia"): File?
    fun backup(libro: Libro, reason: String): File?
    fun listBackups(): List<File>
    fun replace(libro: Libro, reason: String = "antes-de-reemplazar")
    fun restore(source: File)
}

/**
 * Desktop-compatible single-file persistence. The caller supplies Android's
 * `filesDir`; keeping Context out of this class makes it JVM-testable.
 */
class JsonLibroStore(
    private val directory: File,
    private val now: () -> Date = ::Date,
    private val json: Json = defaultJson,
) : LibroStore {
    val dataFile = File(directory, DATA_FILE_NAME)
    val backupsDirectory = File(directory, BACKUPS_DIRECTORY_NAME)

    override fun load(): LibroLoadResult {
        if (!dataFile.exists()) {
            val empty = Libro.empty()
            save(empty)
            return LibroLoadResult(empty)
        }
        val text = try {
            dataFile.readText(Charsets.UTF_8)
        } catch (error: Exception) {
            return LibroLoadResult(
                Libro.empty(),
                "No se ha podido leer el archivo de datos: ${error.message.orEmpty()}",
            )
        }
        return try {
            LibroLoadResult(json.decodeFromString<Libro>(text).normalized())
        } catch (_: Exception) {
            val quarantined = quarantineUnreadable()
            val empty = Libro.empty()
            save(empty)
            LibroLoadResult(
                libro = empty,
                startupNotice = if (quarantined != null) {
                    "El archivo de datos estaba dañado y no se ha podido leer. " +
                        "Se ha guardado una copia intacta en ${quarantined.name} y se ha empezado un libro nuevo."
                } else {
                    "El archivo de datos estaba dañado y no se ha podido leer."
                },
                quarantinedFile = quarantined,
            )
        }
    }

    override fun save(libro: Libro) {
        directory.mkdirsOrThrow()
        val temporary = File(directory, "$DATA_FILE_NAME.tmp")
        val payload = json.encodeToString(libro.normalized())
        FileOutputStream(temporary).use { stream ->
            stream.write(payload.toByteArray(Charsets.UTF_8))
            stream.fd.sync()
        }
        moveReplacing(temporary, dataFile)
    }

    override fun backup(reason: String): File? {
        if (!dataFile.exists()) return null
        return runCatching {
            backupsDirectory.mkdirsOrThrow()
            val destination = uniqueTimestampedFile(backupsDirectory, sanitizeReason(reason))
            dataFile.copyTo(destination, overwrite = false)
            trimBackups()
            destination
        }.getOrNull()
    }

    /** Writes an arbitrary snapshot without ever replacing the live data file. */
    override fun backup(libro: Libro, reason: String): File? = runCatching {
        backupsDirectory.mkdirsOrThrow()
        val destination = uniqueTimestampedFile(backupsDirectory, sanitizeReason(reason))
        destination.writeText(json.encodeToString(libro.normalized()), Charsets.UTF_8)
        trimBackups()
        destination
    }.getOrNull()

    override fun listBackups(): List<File> = backupsDirectory.listFiles { file ->
        file.isFile && file.extension.equals("json", ignoreCase = true)
    }?.sortedByDescending(File::getName).orEmpty()

    override fun replace(libro: Libro, reason: String) {
        backup(reason)
        save(libro)
    }

    override fun restore(source: File) {
        val restored = json.decodeFromString<Libro>(source.readText(Charsets.UTF_8)).normalized()
        replace(restored, "antes-de-restaurar")
    }

    private fun trimBackups() {
        listBackups().drop(MAX_BACKUPS).forEach { runCatching { it.delete() } }
    }

    private fun quarantineUnreadable(): File? = runCatching {
        val stamp = SimpleDateFormat("yyyy-MM-dd_HH-mm-ss", Locale.ROOT).format(now())
        var destination = File(directory, "datos-ilegible-$stamp.json")
        var suffix = 2
        while (destination.exists()) {
            destination = File(directory, "datos-ilegible-$stamp-$suffix.json")
            suffix++
        }
        moveReplacing(dataFile, destination)
        destination
    }.getOrNull()

    private fun uniqueTimestampedFile(parent: File, reason: String): File {
        val stamp = SimpleDateFormat("yyyy-MM-dd_HH-mm-ss", Locale.ROOT).format(now())
        var candidate = File(parent, "$stamp-$reason.json")
        var suffix = 2
        while (candidate.exists()) {
            candidate = File(parent, "$stamp-$reason-$suffix.json")
            suffix++
        }
        return candidate
    }

    private fun sanitizeReason(reason: String): String = reason.trim()
        .lowercase(Locale.ROOT)
        .replace(Regex("[^a-z0-9áéíóúñ_-]+"), "-")
        .trim('-')
        .ifEmpty { "copia" }

    private fun moveReplacing(source: File, destination: File) {
        try {
            Files.move(
                source.toPath(), destination.toPath(),
                StandardCopyOption.ATOMIC_MOVE, StandardCopyOption.REPLACE_EXISTING,
            )
        } catch (_: Exception) {
            Files.move(source.toPath(), destination.toPath(), StandardCopyOption.REPLACE_EXISTING)
        }
    }

    private fun File.mkdirsOrThrow() {
        if (!exists() && !mkdirs()) error("No se ha podido crear la carpeta $absolutePath")
        if (!isDirectory) error("$absolutePath no es una carpeta")
    }

    companion object {
        const val DATA_FILE_NAME = "datos.json"
        const val BACKUPS_DIRECTORY_NAME = "copias"
        const val MAX_BACKUPS = 20

        @OptIn(ExperimentalSerializationApi::class)
        val defaultJson = Json {
            prettyPrint = true
            prettyPrintIndent = "  "
            encodeDefaults = true
            ignoreUnknownKeys = true
            coerceInputValues = true
            explicitNulls = false
        }
    }
}
