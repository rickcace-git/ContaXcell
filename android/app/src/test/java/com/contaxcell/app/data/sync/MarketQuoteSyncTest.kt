package com.contaxcell.app.data.sync

import com.contaxcell.app.data.remote.ContaXcellApi
import com.contaxcell.app.data.remote.HttpResult
import com.contaxcell.app.data.remote.MarketQuote
import com.contaxcell.app.data.remote.MarketQuoteRepository
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class MarketQuoteSyncTest {
    private val closes = listOf(
        MarketQuote("SWDA:XMIL", "2026-08-24", 126.23),
        MarketQuote("SWDA:XMIL", "2026-08-26", 126.68),
    )

    @Test
    fun requestsDeduplicateSymbolsAndStartAtFirstContribution() {
        val requests = MarketQuoteRules.refreshRequests(
            listOf(
                TrackedQuoteAsset("swda:xmil", listOf("2026-07-02", "bad")),
                TrackedQuoteAsset("SWDA:XMIL", listOf("2026-06-15")),
                TrackedQuoteAsset("VUSA:XAMS"),
                TrackedQuoteAsset(""),
            ),
            "2026-08-31",
        )

        assertEquals(
            listOf(
                QuoteRefreshRequest("SWDA:XMIL", "2026-06-15"),
                QuoteRefreshRequest("VUSA:XAMS", "2026-08-31"),
            ),
            requests,
        )
    }

    @Test
    fun mergeDoesNotDuplicateAndIncomingCorrectionWins() {
        val existing = closes + MarketQuote("VUSA:XAMS", "2026-08-26", 95.0)

        val merged = MarketQuoteRules.merge(
            existing,
            "swda:xmil",
            listOf(
                MarketQuote("ignored", "2026-08-26", 127.0),
                MarketQuote("ignored", "2026-08-27", 128.0),
            ),
        )

        assertEquals(1, merged.newDates)
        assertEquals(4, merged.quotes.size)
        assertEquals(127.0, MarketQuoteRules.latest(merged.quotes, "SWDA:XMIL", "2026-08-26")?.price)
        assertEquals(95.0, MarketQuoteRules.latest(merged.quotes, "VUSA:XAMS")?.price)
    }

    @Test
    fun latestCloseOverridesManualValuationAndWeekendUsesPreviousClose() {
        val result = MarketQuoteRules.resolveValuation(
            manualMarketValue = 999.0,
            manualValuationDate = "2026-05-01",
            totalTitles = 1.592758,
            symbol = "SWDA:XMIL",
            quotes = closes,
            through = "2026-08-30",
        )

        assertTrue(result.quoted)
        assertFalse(result.unvalued)
        assertEquals(201.77, result.marketValue, 0.0)
        assertEquals(126.68, result.unitPrice, 0.0)
        assertEquals("2026-08-26", result.valuationDate)
    }

    @Test
    fun zeroTitlesOrMissingClosePreservesManualValuation() {
        val zeroTitles = MarketQuoteRules.resolveValuation(
            500.0, "2026-08-01", 0.0, "SWDA:XMIL", closes,
        )
        val noClose = MarketQuoteRules.resolveValuation(
            210.0, "2026-08-25", 2.0, "", closes,
        )

        assertFalse(zeroTitles.quoted)
        assertEquals(500.0, zeroTitles.marketValue, 0.0)
        assertFalse(noClose.quoted)
        assertEquals(210.0, noClose.marketValue, 0.0)
    }

    @Test
    fun dailyMarkerSkipsAutomaticButForceStillDownloads() = runTest {
        val api = SyncQuoteFakeApi(quoteBody())
        val sessions = SyncQuoteSessions(SyncSession("https://example.test", "ana", "token"))
        val port = SyncQuotePort(
            QuoteBookSnapshot("2026-08-31", listOf(TrackedQuoteAsset("SWDA:XMIL", listOf("2026-07-02")))),
        )
        val sync = MarketQuoteSync(MarketQuoteRepository(api, sessions), port) { "2026-08-31" }

        assertEquals(QuoteRefreshResult.AlreadyCurrent, sync.refresh())
        assertEquals(0, api.downloads)
        assertTrue(sync.refresh(force = true) is QuoteRefreshResult.Applied)
        assertEquals(1, api.downloads)
        assertEquals("2026-08-31", port.appliedOn)
    }

    @Test
    fun emptyDownloadDoesNotAdvanceDailyMarker() = runTest {
        val api = SyncQuoteFakeApi(HttpResult(200, buildJsonObject { put("cotizaciones", buildJsonArray {}) }))
        val sessions = SyncQuoteSessions(SyncSession("https://example.test", "ana", "token"))
        val port = SyncQuotePort(QuoteBookSnapshot(trackedAssets = listOf(TrackedQuoteAsset("SWDA:XMIL"))))
        val sync = MarketQuoteSync(MarketQuoteRepository(api, sessions), port) { "2026-08-31" }

        assertEquals(QuoteRefreshResult.NoData, sync.refresh())
        assertEquals("", port.appliedOn)
    }

    private fun quoteBody() = HttpResult(200, buildJsonObject {
        put("cotizaciones", buildJsonArray {
            add(buildJsonObject {
                put("fecha", JsonPrimitive("2026-08-26"))
                put("precio", JsonPrimitive(126.68))
                put("moneda", JsonPrimitive("EUR"))
            })
        })
    })
}

private class SyncQuoteSessions(initial: SyncSession) : SessionStore {
    private var value = initial
    override suspend fun read() = value
    override suspend fun write(session: SyncSession) { value = session }
    override suspend fun clear() { value = SyncSession() }
}

private class SyncQuotePort(private val state: QuoteBookSnapshot) : MarketQuoteBookPort {
    var appliedOn = ""
    override suspend fun snapshot() = state
    override suspend fun applyQuotes(downloaded: Map<String, List<MarketQuote>>, refreshedOn: String): AppliedQuoteRefresh {
        appliedOn = refreshedOn
        return AppliedQuoteRefresh(downloaded.values.sumOf { it.size }, downloaded.values.sumOf { it.size })
    }
}

private class SyncQuoteFakeApi(private val response: HttpResult) : ContaXcellApi {
    var downloads = 0
    override suspend fun downloadQuotes(serverUrl: String, token: String, symbol: String, from: String): HttpResult {
        downloads++
        return response
    }
    override suspend fun searchQuotes(serverUrl: String, token: String, query: String) = HttpResult(500)
    override suspend fun health(serverUrl: String) = HttpResult(200)
    override suspend fun register(serverUrl: String, username: String, password: String, invitationCode: String) = HttpResult(500)
    override suspend fun login(serverUrl: String, username: String, password: String) = HttpResult(500)
    override suspend fun changePassword(serverUrl: String, token: String, currentPassword: String, newPassword: String) = HttpResult(500)
    override suspend fun downloadBook(serverUrl: String, token: String) = HttpResult(500)
    override suspend fun uploadBook(serverUrl: String, token: String, baseRevision: Int, book: JsonObject) = HttpResult(500)
}
