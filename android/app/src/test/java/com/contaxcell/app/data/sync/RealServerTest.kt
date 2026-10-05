package com.contaxcell.app.data.sync

import com.contaxcell.app.data.remote.AuthRepository
import com.contaxcell.app.data.remote.MarketQuoteRepository
import com.contaxcell.app.data.remote.OkHttpContaXcellApi
import com.contaxcell.app.domain.Libro
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

/**
 * Lo mismo que hace el móvil al entrar, contra un servidor de verdad y con las
 * piezas de verdad (OkHttp, AuthRepository, SyncEngine): entrar con una cuenta
 * que ya tiene la contabilidad subida desde el escritorio y descargarla.
 *
 * Solo corre si hay servidor: GitHub arranca `server/pruebas/servidor_para_android.py`
 * y pasa su dirección en CONTAXCELL_SERVIDOR_PRUEBAS. En local, sin esa
 * variable, se salta.
 */
class RealServerTest {
    private val server = System.getenv("CONTAXCELL_SERVIDOR_PRUEBAS").orEmpty()

    @Test
    fun loginThenSyncDownloadsTheDesktopBookWithoutExpiring() = runBlocking {
        assumeTrue("Sin servidor de pruebas", server.isNotBlank())
        val api = OkHttpContaXcellApi()
        val sessions = RealMemorySessions()
        val books = RealMemoryBooks(Libro.empty())

        // Como en el móvil: primero entrar…
        val session = AuthRepository(api, sessions).login("escritorio", "contrasena-de-prueba", server)
        assertTrue("Sin ficha tras entrar", session.isSignedIn)
        assertFalse(session.expired)

        // …luego sincronizar…
        val result = SyncEngine(api, sessions, books).syncNow()
        val after = sessions.read()
        assertFalse("La sesión sale caducada tras sincronizar ($result)", after.expired)
        assertTrue("Esperaba descargar, y fue $result", result is SyncResult.Downloaded)

        // …y lo descargado es lo que subió el escritorio.
        val book = books.current!!
        assertEquals(2, book.movimientos.size)
        assertEquals(10.0, book.activos.single().titulosIniciales, 0.0)
        assertEquals(1, book.periodicos.size)
        assertEquals(1, after.lastRevision)

        // …y pedir precios, como hace la app justo después, tampoco la caduca.
        MarketQuoteRepository(api, sessions).fetch("SWDA.MI", "2026-09-01")
        assertFalse("Pedir precios caducó la sesión", sessions.read().expired)
    }
}

private class RealMemorySessions : SessionStore {
    private var value = SyncSession()
    override suspend fun read() = value
    override suspend fun write(session: SyncSession) { value = session }
    override suspend fun clear() { value = SyncSession() }
}

private class RealMemoryBooks(initial: Libro) : SyncBookStore {
    var current: Libro? = initial
    override suspend fun read() = current
    override suspend fun replace(book: Libro, reason: String) { current = book }
    override suspend fun backup(book: Libro, reason: String): String? = null
}
