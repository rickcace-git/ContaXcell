package com.contaxcell.app.domain

import com.contaxcell.app.domain.ContaXcellValues.DEBO
import com.contaxcell.app.domain.ContaXcellValues.INVERSION
import com.contaxcell.app.domain.ContaXcellValues.ME_DEBEN
import com.contaxcell.app.domain.ContaXcellValues.MENSUAL
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class UpstreamParityTest {
    private fun accountingBook(): Libro = Libro.empty().copy(
        ajustes = Ajustes(saldoInicial = 1_000.0, objetivoInversion = 200.0),
        activos = listOf(Activo("Fondo", aportacionInicial = 500.0, valorMercado = 900.0)),
        movimientos = listOf(
            Movimiento("2026-03-01", "Nómina", "Sueldo", 2_000.0, id = "m1"),
            Movimiento("2026-03-05", "Alquiler", "Vivienda y Suministros", 700.0, id = "m2"),
            Movimiento("2026-03-10", "Súper", "Productos Básicos", 120.0, id = "m3"),
            Movimiento("2026-03-20", "Aportación", "Inversión", 300.0, activo = "Fondo", id = "m4"),
            Movimiento("2026-04-02", "Cena", "Comer fuera", 45.5, id = "m5"),
        ),
    )

    @Test fun `arbitrary periods partition into months years and days`() {
        val multiYear = accountingBook().copy(movimientos = accountingBook().movimientos + listOf(
            Movimiento("2025-06-01", "Nómina vieja", "Sueldo", 1_500.0, id = "m0"),
            Movimiento("2025-06-15", "Alquiler viejo", "Vivienda y Suministros", 600.0, id = "m0b"),
        ))
        assertEquals(listOf("2026-11", "2026-12", "2027-01", "2027-02"), Calculos.mesesEntre("2026-11", "2027-02"))
        assertTrue(Calculos.mesesEntre("2026-05", "2026-01").isEmpty())

        val month = Calculos.resumenPeriodo(accountingBook(), "2026-03", "2026-03")
        assertEquals(1, month.tramos.size)
        assertEquals(2_000.0, month.total.ingresos, 0.0)
        assertEquals(820.0, month.total.gastos, 0.0)
        assertEquals(300.0, month.total.inversion, 0.0)

        val years = Calculos.resumenPeriodo(multiYear, "2025-01", "2026-12", Calculos.POR_ANIOS)
        assertEquals(listOf("2025", "2026"), years.tramos.map { it.nombre })
        assertEquals(1_500.0, years.tramos[0].totales.ingresos, 0.0)
        assertEquals(2_000.0, years.tramos[1].totales.ingresos, 0.0)
        assertEquals(3, years.mesesConDatos)

        val days = Calculos.resumenPeriodo(accountingBook(), "2026-03", "2026-03", Calculos.POR_DIAS)
        assertEquals(31, days.tramos.size)
        assertEquals("dom 1", days.tramos.first().nombre)
        assertEquals(listOf("2026-03-01", "2026-03-05", "2026-03-10", "2026-03-20"), days.tramos.filter { it.hayDatos }.map { it.clave })
        assertEquals(28, Calculos.resumenPeriodo(accountingBook(), "2026-02", "2026-02", Calculos.POR_DIAS).tramos.size)
        assertEquals(29, Calculos.resumenPeriodo(accountingBook(), "2028-02", "2028-02", Calculos.POR_DIAS).tramos.size)
    }

    @Test fun `period indicators retain monthly averages and largest real expense`() {
        val book = accountingBook().copy(movimientos = accountingBook().movimientos + listOf(
            Movimiento("2025-06-01", "Nómina vieja", "Sueldo", 1_500.0),
            Movimiento("2025-06-15", "Alquiler viejo", "Vivienda y Suministros", 600.0),
            Movimiento("2026-03-25", "Fondo grande", "Inversión", 5_000.0),
        ))
        val indicators = Calculos.indicadoresDe(book, "2025-01", "2026-12", Calculos.POR_ANIOS)
        assertEquals(3, indicators.mesesConDatos)
        assertEquals(DomainNumbers.money((600.0 + 820.0 + 45.5) / 3), indicators.gastoMedio, 0.0)
        assertEquals("2026", indicators.tramoMayorGasto)
        assertEquals("Alquiler", indicators.mayorGasto?.descripcion)
        assertEquals(5_300.0, indicators.inversion, 0.0)
        assertNull(Calculos.mayorGastoEntre(book, "2020-01", "2020-12"))
    }

    private fun dinner(
        id: String = "d1", who: String = "Fulanito", direction: String = ME_DEBEN,
        amount: Double = 20.0, returned: Double = 0.0,
    ) = Deuda(who, direction, amount, "2026-03-10", "La cena", devuelto = returned, id = id)

    @Test fun `debts settle in parts without touching accounting`() {
        val debt = dinner(amount = 0.3)
        val first = Calculos.anotarPago(debt, 0.1)
        val second = Calculos.anotarPago(first.deuda, 0.1)
        assertEquals(0.1, second.apuntado, 0.0)
        assertEquals(0.1, Calculos.pendienteDe(second.deuda), 0.0)
        val finished = Calculos.anotarPago(second.deuda, 999.0)
        assertEquals(0.1, finished.apuntado, 0.0)
        assertTrue(Calculos.estaSaldada(finished.deuda))

        val book = accountingBook().copy(deudas = listOf(dinner(amount = 500.0), dinner("d2", direction = DEBO, amount = 300.0)))
        assertEquals(Calculos.saldoBanco(accountingBook()), Calculos.saldoBanco(book), 0.0)
        assertEquals(Calculos.totalesDelMes(accountingBook(), "2026-03"), Calculos.totalesDelMes(book, "2026-03"))
    }

    @Test fun `debt summaries compensate both directions per person`() {
        val book = Libro.empty().copy(deudas = listOf(
            dinner(amount = 50.0), dinner("d2", direction = DEBO, amount = 20.0),
            dinner("d3", who = "fulanito", amount = 5.0), dinner("d4", who = "Ana", amount = 90.0),
            dinner("d5", who = "Saldada", amount = 10.0, returned = 10.0),
        ))
        val summary = Calculos.resumenDeudas(book)
        assertEquals(145.0, summary.teDeben, 0.0)
        assertEquals(20.0, summary.debes, 0.0)
        assertEquals(4, summary.abiertas)
        assertEquals(1, summary.saldadas)
        assertEquals(2, summary.personas)
        val people = Calculos.deudasPorPersona(book)
        assertEquals(listOf("Ana", "Fulanito"), people.map { it.quien })
        assertEquals(35.0, people[1].neto, 0.0)
        assertEquals(3, people[1].cuantas)
    }

    @Test fun `debt normalization preserves JSON defaults and clamps invalid values`() {
        val book = Libro(deudas = listOf(
            Deuda(" Buena ", "inventado", -20.0, "2026-03-10", nota = " línea 1\nlínea 2 ", devuelto = 999.0),
            Deuda("", fecha = "2026-03-10"),
            Deuda("Sin fecha", fecha = ""),
        )).normalized()
        assertEquals(1, book.deudas.size)
        assertEquals("Buena", book.deudas.single().quien)
        assertEquals(ME_DEBEN, book.deudas.single().sentido)
        assertEquals(20.0, book.deudas.single().importe, 0.0)
        assertEquals(20.0, book.deudas.single().devuelto, 0.0)
        assertTrue(book.deudas.single().nota.contains('\n'))
        assertTrue(Libro.empty().deudas.isEmpty())
    }

    @Test fun `quick add recurring links first movement and skips intervening history`() {
        val movement = Movimiento("2026-01-10", "Gimnasio", "Ocio", 35.0)
        val created = Calculos.periodicoDe(movement, MENSUAL, "2026-03-15")
        assertEquals(created.periodico.id, created.movimiento.origen)
        assertEquals("2026-03-10", created.periodico.apuntadoHasta)
        val book = Libro.empty().copy(movimientos = listOf(created.movimiento), periodicos = listOf(created.periodico))
        assertTrue(Calculos.apuntarPendientes(book, "2026-03-15").creados.isEmpty())
        assertEquals(listOf("2026-04-10"), Calculos.apuntarPendientes(book, "2026-04-10").creados.map { it.fecha })
        val unnamed = Calculos.periodicoDe(movement.copy(descripcion = "  "), MENSUAL, "2026-01-10")
        assertEquals("Ocio", unnamed.periodico.nombre)
    }

    private fun quotedBook(symbol: String = "SWDA:XMIL"): Libro = Libro.empty().copy(
        activos = listOf(Activo("MSCI World", categoria = "Indexados", isin = "IE00B4L5Y983", simbolo = symbol)),
        movimientos = listOf(
            Movimiento("2026-07-02", "Compra", INVERSION, 100.0, "MSCI World", titulos = 0.795628, id = "c1"),
            Movimiento("2026-07-09", "Compra", INVERSION, 100.0, "MSCI World", titulos = 0.797130, id = "c2"),
        ),
    )

    @Test fun `quotes merge by date and latest close overrides manual valuation`() {
        val closes = listOf(
            Cotizacion("swda:xmil", "2026-07-02", 125.68),
            Cotizacion("SWDA:XMIL", "2026-07-09", 125.45),
            Cotizacion("SWDA:XMIL", "2026-08-26", 126.68),
        )
        val first = Calculos.guardarCotizaciones(quotedBook(), "SWDA:XMIL", closes)
        assertEquals(3, first.nuevas)
        val correction = Calculos.guardarCotizaciones(first.libro, "SWDA:XMIL", listOf(Cotizacion("x", "2026-08-26", 127.0)))
        assertEquals(0, correction.nuevas)
        assertEquals(3, correction.libro.cotizaciones.size)
        assertEquals(127.0, Calculos.ultimaCotizacion(correction.libro, "SWDA:XMIL")?.precio ?: 0.0, 0.0)
        assertEquals(125.45, Calculos.ultimaCotizacion(correction.libro, "SWDA:XMIL", "2026-07-15")?.precio ?: 0.0, 0.0)

        val asset = Calculos.cartera(correction.libro).activos.single()
        assertTrue(asset.cotizado)
        assertEquals(DomainNumbers.money(1.592758 * 127.0), asset.valorMercado, 0.0)
        assertEquals("2026-08-26", asset.ultimaValoracion)
        val purchases = Calculos.comprasDe(correction.libro, "MSCI World")
        assertEquals(125.68, purchases.first { it.fecha == "2026-07-02" }.quoteAtPurchase ?: 0.0, 0.0)
        assertEquals(127.0, purchases.first().quoteToday ?: 0.0, 0.0)
        assertTrue(purchases.first().quoteChange != null)
    }

    @Test fun `quote symbols and history start are derived from assigned assets`() {
        val book = quotedBook().copy(
            activos = quotedBook().activos + Activo("Otro", simbolo = "swda:xmil") + Activo("Bitcoin"),
            aportacionesGratis = listOf(AportacionGratis("2026-06-15", "MSCI World", importe = 4.61, titulos = 0.0366)),
        )
        assertEquals(listOf("SWDA:XMIL"), Calculos.simbolosDelLibro(book))
        assertEquals("2026-06-15", Calculos.desdeCuandoHacenFalta(book, "SWDA:XMIL", "2099-01-01"))
        assertEquals("2099-01-01", Calculos.desdeCuandoHacenFalta(Libro.empty(), "VUSA:XAMS", "2099-01-01"))
        assertFalse(Calculos.cartera(quotedBook(symbol = "")).activos.single().cotizado)
    }

    @Test fun `quotes require units and otherwise preserve manual valuation`() {
        val noUnits = Libro.empty().copy(
            activos = listOf(Activo("Oro", valorMercado = 500.0, ultimaValoracion = "2026-08-01", simbolo = "GOLD")),
            cotizaciones = listOf(Cotizacion("GOLD", "2026-08-30", 2_000.0)),
        )
        val manual = Calculos.cartera(noUnits).activos.single()
        assertFalse(manual.cotizado)
        assertEquals(500.0, manual.valorMercado, 0.0)

        val staleManual = quotedBook().copy(
            activos = listOf(quotedBook().activos.single().copy(valorMercado = 999.0, ultimaValoracion = "2026-05-01")),
            cotizaciones = listOf(Cotizacion("SWDA:XMIL", "2026-08-26", 126.68)),
        )
        val automatic = Calculos.cartera(staleManual).activos.single()
        assertTrue(automatic.cotizado)
        assertFalse(automatic.valorMercado == 999.0)
        assertEquals("2026-08-26", automatic.ultimaValoracion)
    }
}
