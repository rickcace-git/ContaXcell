package com.contaxcell.app.domain

import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class ModelAndFormatTest {
    @Test fun `normalization sanitizes and deduplicates desktop data`() {
        val normalized = Libro(
            categorias = listOf(Categoria(" Casa ", "Raro", 2.675), Categoria("Casa", GASTO)),
            movimientos = listOf(Movimiento("2026-01-01", importe = -5.0), Movimiento("imposible")),
            activos = listOf(Activo(" Fondo ", isin = " es123 ")),
            periodicos = listOf(Periodico(" Renta ", desde = "2026-01-05", hasta = "2025-01-01")),
        ).normalized()
        assertEquals(1, normalized.categorias.size)
        assertEquals("Casa", normalized.categorias.single().nombre)
        assertEquals(GASTO, normalized.categorias.single().tipo)
        assertEquals(2.68, normalized.categorias.single().presupuesto, 0.0)
        assertEquals(5.0, normalized.movimientos.single().importe, 0.0)
        assertEquals("ES123", normalized.activos.single().isin)
        assertEquals("", normalized.periodicos.single().hasta)
    }

    @Test fun `serialized field names remain desktop compatible`() {
        val encoded = Json { encodeDefaults = true }.encodeToString(
            Libro(
                ajustes = Ajustes(saldoInicial = 10.0),
                aportacionesGratis = listOf(AportacionGratis("2026-01-01")),
                periodicos = listOf(Periodico("Renta", desde = "2026-01-01")),
            ),
        )
        assertTrue("\"saldo_inicial\"" in encoded)
        assertTrue("\"aportaciones_gratis\"" in encoded)
        assertTrue("\"apuntado_hasta\"" in encoded)
        assertTrue("\"precios_al_dia\"" in encoded)
        assertTrue("\"cotizaciones\"" in encoded)
        assertTrue("\"deudas\"" in encoded)
    }

    @Test fun `Spanish number and date formatting mirrors desktop`() {
        assertEquals("1.234,56", SpanishFormat.number(1234.56))
        assertEquals("-1.234,6", SpanishFormat.number(-1234.56, 1))
        assertEquals("+10,00 €", SpanishFormat.signedEuros(10.0))
        assertEquals(SpanishFormat.HIDDEN, SpanishFormat.euros(10.0, hidden = true))
        assertEquals(1234.56, SpanishFormat.parseNumber("1.234,56 €")!!, 0.0)
        assertEquals("24 ago 2026", SpanishFormat.shortDate("2026-08-24"))
        assertEquals("24/08/2026", SpanishFormat.dateToText("2026-08-24"))
        assertEquals("2026-08-24", SpanishFormat.parseDate("24/8/26"))
        assertNull(SpanishFormat.parseDate("31/2/2026"))
    }

    private companion object { const val GASTO = ContaXcellValues.GASTO }
}
