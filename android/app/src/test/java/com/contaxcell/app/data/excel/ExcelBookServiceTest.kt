package com.contaxcell.app.data.excel

import com.contaxcell.app.domain.Activo
import com.contaxcell.app.domain.Ajustes
import com.contaxcell.app.domain.AportacionGratis
import com.contaxcell.app.domain.Libro
import com.contaxcell.app.domain.Movimiento
import com.contaxcell.app.domain.Valoracion
import java.io.ByteArrayInputStream
import java.io.ByteArrayOutputStream
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ExcelBookServiceTest {
    private val service = ExcelBookService()

    @Test
    fun exportedWorkbookCanBeImportedWithoutLosingCoreAccountingData() {
        val original = Libro.empty().copy(
            ajustes = Ajustes(saldoInicial = 1_000.0, objetivoInversion = 250.0),
            activos = listOf(Activo("MSCI World", 100.0, 210.0, "2026-08-20")),
            movimientos = listOf(
                Movimiento("2026-08-01", "Nómina", "Sueldo", 2_000.0),
                Movimiento("2026-08-02", "Compra", "Productos Básicos", 42.5),
            ),
            aportacionesGratis = listOf(AportacionGratis("2026-08-03", "MSCI World", "Cashback", 4.61)),
            historico = listOf(Valoracion("2026-08-20", 210.0)),
        )
        val bytes = ByteArrayOutputStream().also { service.export(it, original, 2026) }.toByteArray()

        val imported = service.import(ByteArrayInputStream(bytes)).book

        assertEquals(1_000.0, imported.ajustes.saldoInicial, 0.0)
        assertEquals(250.0, imported.ajustes.objetivoInversion, 0.0)
        assertEquals(2, imported.movimientos.size)
        assertEquals("Nómina", imported.movimientos.first().descripcion)
        assertEquals(1, imported.activos.size)
        assertEquals(1, imported.aportacionesGratis.size)
        assertEquals(1, imported.historico.size)
        assertTrue(imported.categorias.any { it.nombre == "Productos Básicos" })
    }
}
