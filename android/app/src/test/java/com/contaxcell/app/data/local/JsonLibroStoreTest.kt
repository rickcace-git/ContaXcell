package com.contaxcell.app.data.local

import com.contaxcell.app.domain.Ajustes
import com.contaxcell.app.domain.Activo
import com.contaxcell.app.domain.Cotizacion
import com.contaxcell.app.domain.Deuda
import com.contaxcell.app.domain.Libro
import com.contaxcell.app.domain.Movimiento
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.file.Files
import java.util.Date

class JsonLibroStoreTest {
    private val directory = Files.createTempDirectory("contaxcell-store-").toFile()
    private val fixedDate = Date(1_788_110_400_000L)
    private val store = JsonLibroStore(directory, now = { fixedDate })

    @After fun cleanUp() = directory.deleteRecursively().let { Unit }

    @Test fun `first load creates a desktop compatible empty file`() {
        val result = store.load()
        assertEquals(9, result.libro.categorias.size)
        assertTrue(store.dataFile.exists())
        assertTrue(store.dataFile.readText().contains("\"aportaciones_gratis\""))
    }

    @Test fun `save and load round trip normalized immutable book`() {
        val book = Libro(
            ajustes = Ajustes(saldoInicial = 12.345),
            movimientos = listOf(Movimiento("2026-01-01", importe = -15.0, id = "m")),
        )
        store.save(book)
        val loaded = store.load().libro
        assertEquals(12.35, loaded.ajustes.saldoInicial, 0.0)
        assertEquals(15.0, loaded.movimientos.single().importe, 0.0)
        assertFalse(File(directory, "datos.json.tmp").exists())
    }

    @Test fun `corrupt data is quarantined before a fresh book is written`() {
        directory.mkdirs()
        store.dataFile.writeText("{not json")
        val result = store.load()
        assertNotNull(result.quarantinedFile)
        assertTrue(result.quarantinedFile!!.readText().contains("not json"))
        assertTrue(result.startupNotice.contains("dañado"))
        assertEquals(9, result.libro.categorias.size)
        assertTrue(store.dataFile.exists())
    }

    @Test fun `replace backs up previous state and restore backs up replacement`() {
        store.save(Libro(ajustes = Ajustes(saldoInicial = 10.0)))
        store.replace(Libro(ajustes = Ajustes(saldoInicial = 20.0)))
        val originalBackup = store.listBackups().single()
        assertTrue(originalBackup.readText().contains("10.0"))

        store.restore(originalBackup)
        assertEquals(10.0, store.load().libro.ajustes.saldoInicial, 0.0)
        assertEquals(2, store.listBackups().size)
    }

    @Test fun `only newest twenty backups are retained`() {
        store.save(Libro.empty())
        repeat(25) { store.backup("copia-$it") }
        assertEquals(JsonLibroStore.MAX_BACKUPS, store.listBackups().size)
    }

    @Test fun `snapshot backup never replaces live data`() {
        store.save(Libro(ajustes = Ajustes(saldoInicial = 10.0)))
        val snapshot = store.backup(Libro(ajustes = Ajustes(saldoInicial = 99.0)), "conflicto")
        assertNotNull(snapshot)
        assertTrue(snapshot!!.readText().contains("99.0"))
        assertEquals(10.0, store.load().libro.ajustes.saldoInicial, 0.0)
    }

    @Test fun `new debts and quote cache round trip while old books keep empty defaults`() {
        store.save(Libro(
            ajustes = Ajustes(preciosAlDia = "2026-08-31"),
            activos = listOf(Activo("Fondo", simbolo = "swda:xmil")),
            cotizaciones = listOf(Cotizacion("swda:xmil", "2026-08-28", 126.68)),
            deudas = listOf(Deuda("Ana", fecha = "2026-08-30", importe = 20.0)),
        ))
        val current = store.load().libro
        assertEquals("SWDA:XMIL", current.activos.single().simbolo)
        assertEquals(126.68, current.cotizaciones.single().precio, 0.0)
        assertEquals("Ana", current.deudas.single().quien)
        assertEquals("2026-08-31", current.ajustes.preciosAlDia)

        store.dataFile.writeText("""{"version":1,"movimientos":[]}""")
        val old = store.load().libro
        assertTrue(old.deudas.isEmpty())
        assertTrue(old.cotizaciones.isEmpty())
        assertEquals("", old.ajustes.preciosAlDia)
    }
}
