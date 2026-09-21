package com.contaxcell.app.domain

import com.contaxcell.app.domain.ContaXcellValues.GASTO
import com.contaxcell.app.domain.ContaXcellValues.INGRESO
import com.contaxcell.app.domain.ContaXcellValues.INVERSION
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class DomainCalculationsTest {
    private fun book(): Libro = Libro(
        ajustes = Ajustes(saldoInicial = 1_000.0, objetivoInversion = 300.0),
        categorias = listOf(
            Categoria("Sueldo", INGRESO),
            Categoria("Casa", GASTO, 700.0),
            Categoria("Inversión", INVERSION),
        ),
        activos = listOf(Activo("Fondo", aportacionInicial = 500.0, valorMercado = 1_050.0, ultimaValoracion = "2026-03-31")),
        movimientos = listOf(
            Movimiento("2026-03-01", "Nómina", "Sueldo", 2_000.0, id = "a"),
            Movimiento("2026-03-02", "Alquiler", "Casa", 700.0, id = "b"),
            Movimiento("2026-03-03", "Aportación", "Inversión", 400.0, activo = "Fondo", titulos = 4.0, id = "c"),
        ),
        aportacionesGratis = listOf(AportacionGratis("2026-03-04", "Fondo", "Cashback", 50.0, titulos = 0.5, id = "g")),
        historico = listOf(Valoracion("2026-03-31", 1_050.0, "h")),
    )

    @Test fun `bank, saving and cash flow keep investments separate`() {
        val totals = Calculos.totalesDelMes(book(), "2026-03")
        assertEquals(1_900.0, Calculos.saldoBanco(book()), 0.0)
        assertEquals(2_000.0, totals.ingresos, 0.0)
        assertEquals(700.0, totals.gastos, 0.0)
        assertEquals(400.0, totals.inversion, 0.0)
        assertEquals(1_300.0, totals.ahorro, 0.0)
        assertEquals(900.0, totals.flujoNeto, 0.0)
    }

    @Test fun `balance rows are deterministic and cumulative`() {
        val rows = Calculos.conBalance(book().copy(movimientos = book().movimientos.reversed()))
        assertEquals(listOf("a", "b", "c"), rows.map { it.id })
        assertEquals(listOf(3_000.0, 2_300.0, 1_900.0), rows.map { it.balance })
    }

    @Test fun `budget and annual summary match desktop formulas`() {
        val budget = Calculos.presupuestoDelMes(book(), "2026-03")
        val annual = Calculos.resumenAnual(book(), 2026)
        assertEquals(700.0, budget.presupuestado, 0.0)
        assertEquals(700.0, budget.gastado, 0.0)
        assertEquals(0.0, budget.disponible, 0.0)
        assertEquals(0.0, budget.pendiente, 0.0)
        assertEquals(1, annual.mesesConDatos)
        assertEquals(1_900.0, annual.meses[2].saldoFinal, 0.0)
    }

    @Test fun `portfolio includes initial bank and free contributions`() {
        val portfolio = Calculos.cartera(book())
        val asset = portfolio.activos.single()
        assertEquals(950.0, asset.totalAportado, 0.0)
        assertEquals(100.0, asset.generado, 0.0)
        assertEquals(4.5, asset.titulos, 0.0)
        assertEquals(0.0, portfolio.sinAsignarBanco, 0.0)
        assertEquals(0.0, portfolio.sinAsignarGratis, 0.0)
        assertEquals(950.0, portfolio.historico.single().aportado, 0.0)
    }

    @Test fun `unvalued assets assume contributed value without inventing purchase returns`() {
        val unvalued = book().copy(activos = listOf(Activo("Fondo", aportacionInicial = 500.0)))
        val asset = Calculos.cartera(unvalued).activos.single()
        assertTrue(asset.sinValorar)
        assertEquals(asset.totalAportado, asset.valorMercado, 0.0)
        assertEquals(0.0, Calculos.comprasDe(unvalued, "Fondo").single().precioHoy, 0.0)
    }

    @Test fun `monthly dates return to original day after February`() {
        val recurring = Periodico("Alquiler", "Casa", 700.0, desde = "2026-01-31", id = "p")
        assertEquals(
            listOf("2026-01-31", "2026-02-28", "2026-03-31", "2026-04-30"),
            Calculos.vencimientos(recurring, "2026-04-30"),
        )
    }

    @Test fun `recurring posting is immutable idempotent and respects end date`() {
        val original = book().copy(
            movimientos = emptyList(),
            periodicos = listOf(Periodico("Alquiler", "Casa", 700.0, desde = "2026-01-05", hasta = "2026-03-05", id = "p")),
        )
        val first = Calculos.apuntarPendientes(original, "2026-12-31")
        val second = Calculos.apuntarPendientes(first.libro, "2026-12-31")
        assertTrue(original.movimientos.isEmpty())
        assertEquals(listOf("2026-01-05", "2026-02-05", "2026-03-05"), first.creados.map { it.fecha })
        assertEquals("2026-03-05", first.libro.periodicos.single().apuntadoHasta)
        assertTrue(second.creados.isEmpty())
        assertFalse(Calculos.estaVigente(original.periodicos.single(), "2026-03-06"))
    }

    @Test fun `reactivation skips disabled history without moving marker backwards`() {
        val recurring = Periodico("Gimnasio", "Casa", 35.0, desde = "2026-01-05", apuntadoHasta = "2026-03-05")
        assertEquals("2026-08-05", Calculos.saltarLoPasado(recurring, "2026-08-26").apuntadoHasta)
        assertEquals("2026-03-05", Calculos.saltarLoPasado(recurring, "2026-03-05").apuntadoHasta)
    }

    @Test fun `rounding and date helpers follow financial semantics`() {
        assertEquals(2.68, DomainNumbers.money(2.675), 0.0)
        assertEquals(0.795628, DomainNumbers.titles(0.7956275), 0.0)
        assertEquals("2024-02-29", IsoDates.plusMonths("2024-01-31", 1))
        assertFalse(IsoDates.isValid("2026-02-30"))
    }
}
