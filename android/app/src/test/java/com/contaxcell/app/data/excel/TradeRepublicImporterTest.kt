package com.contaxcell.app.data.excel

import com.contaxcell.app.domain.Activo
import com.contaxcell.app.domain.Libro
import com.contaxcell.app.domain.Movimiento
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class TradeRepublicImporterTest {
    private val importer = TradeRepublicImporter()

    @Test
    fun readsPurchasesInterestAndSixDecimalTitles() {
        val reading = importer.readLines(statement())

        assertEquals(2, reading.purchases.size)
        assertEquals(2, reading.income.size)
        assertEquals("2026-07-02", reading.purchases.first().date)
        assertEquals(0.795628, reading.purchases.first().titles, 0.0)
        assertEquals("MSCI World", reading.purchases.first().assetName)
        assertEquals("2026-07-01", reading.from)
        assertEquals("2026-07-09", reading.until)
    }

    @Test
    fun repeatedImportDoesNotDuplicateTransactions() {
        val reading = importer.readLines(statement())
        val options = TradeRepublicOptions("Inversión", "Otros Ingresos", "Indexados")
        val first = importer.apply(Libro.empty(), reading, options)
        val second = importer.apply(first.book, reading, options)

        assertEquals(4, second.summary.duplicates)
        assertEquals(first.book.movimientos.size, second.book.movimientos.size)
        assertEquals(1, second.book.activos.size)
    }

    @Test
    fun reinvestedRewardBecomesFreeContributionAndRepairsLegacyMovement() {
        val lines = reward("01 ago", "2026", "4,61") +
            purchase("03 ago", "2026", "4,61", "0.036630") +
            purchase("03 ago", "2026", "100,00", "0.794249")
        val reading = importer.readLines(lines)
        val legacy = Libro.empty().copy(
            activos = listOf(Activo("MSCI World", isin = "IE00B4L5Y983")),
            movimientos = listOf(
                Movimiento("2026-08-03", "Compra del plan de inversión", "Inversión", 4.61, "MSCI World", titulos = 0.036630),
            ),
        )

        val applied = importer.apply(legacy, reading, TradeRepublicOptions("Inversión", "Otros Ingresos"))

        assertEquals(1, applied.summary.free)
        assertEquals(1, applied.summary.corrected)
        assertEquals(1, applied.book.aportacionesGratis.size)
        assertTrue(applied.book.movimientos.none { it.importe == 4.61 })
    }

    @Test
    fun findsManualInvestmentContributionsCoveredByStatementMonths() {
        val book = Libro.empty().copy(
            movimientos = listOf(
                Movimiento("2026-07-01", "Aportación del mes", "Inversión", 200.0, id = "manual"),
                Movimiento("2026-06-01", "Anterior", "Inversión", 200.0, id = "old"),
            ),
        )
        assertEquals(listOf("manual"), importer.manualContributions(book, importer.readLines(statement())).map { it.id })
    }

    @Test
    fun acceptsFourLetterSeptemberAndSavebackReward() {
        val lines = reward("01 sept", "2026", "3,51", "Saveback cash reward") +
            purchase("02 sept", "2026", "3,51", "0.027685")

        val reading = importer.readLines(lines)

        assertTrue(reading.warnings.isEmpty())
        assertTrue(reading.income.isEmpty())
        assertEquals("2026-09-02", reading.free.single().date)
        assertEquals(3.51, reading.free.single().amount, 0.0)
    }

    private fun statement() = purchase("02 jul", "2026", "100,00", "0.795628") +
        purchase("09 jul", "2026", "100,00", "0.797130") +
        interest("01 jul", "2026", "2,47") + reward("01 jul", "2026", "0,05")

    private fun purchase(day: String, year: String, euros: String, titles: String) = listOf(
        "$day  |  Savings plan execution IE00B4L5Y983 iShares III plc - iShares Core MSCI",
        "Operar  |  $euros €  |  4.895,14 €",
        "$year  |  World UCITS ETF USD (Acc), quantity: $titles",
    )

    private fun interest(day: String, year: String, euros: String) =
        listOf(day, "Interés  |  Interest payment  |  $euros €  |  5.000,00 €", year)

    private fun reward(
        day: String,
        year: String,
        euros: String,
        mark: String = "Cash reward allocation",
    ) = listOf(day, "Bonificación  |  $mark  |  $euros €  |  5.000,00 €", year)
}
