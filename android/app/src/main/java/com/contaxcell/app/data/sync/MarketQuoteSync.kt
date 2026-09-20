package com.contaxcell.app.data.sync

import com.contaxcell.app.data.remote.MarketQuote
import com.contaxcell.app.data.remote.MarketQuoteRepository
import com.contaxcell.app.domain.DomainNumbers
import com.contaxcell.app.domain.IsoDates
import com.contaxcell.app.domain.Calculos
import com.contaxcell.app.domain.Cotizacion
import com.contaxcell.app.domain.Libro
import java.util.Locale

/** One asset's symbol and the dates on which the user acquired units. */
data class TrackedQuoteAsset(
    val symbol: String,
    val contributionDates: List<String> = emptyList(),
)

/** Minimal book view required by quote refresh; domain/UI supply the adapter. */
data class QuoteBookSnapshot(
    val pricesCurrentOn: String = "",
    val trackedAssets: List<TrackedQuoteAsset> = emptyList(),
)

data class AppliedQuoteRefresh(
    val newDates: Int,
    val storedQuotes: Int,
)

interface MarketQuoteBookPort {
    suspend fun snapshot(): QuoteBookSnapshot

    /** Merge closes by symbol/date and persist [refreshedOn] through the normal book mutation path. */
    suspend fun applyQuotes(
        downloaded: Map<String, List<MarketQuote>>,
        refreshedOn: String,
    ): AppliedQuoteRefresh
}

/**
 * Domain adapter whose writer should be the app's ordinary persisted mutation path
 * (including its pending-sync marker), not a second source of book state.
 */
class DomainMarketQuoteBookPort(
    private val readBook: suspend () -> Libro,
    private val writeBook: suspend (Libro) -> Unit,
) : MarketQuoteBookPort {
    override suspend fun snapshot(): QuoteBookSnapshot {
        val libro = readBook()
        return QuoteBookSnapshot(
            pricesCurrentOn = libro.ajustes.preciosAlDia,
            trackedAssets = libro.activos.map { asset ->
                val namesSharingSymbol = libro.activos.asSequence()
                    .filter { it.simbolo.equals(asset.simbolo, ignoreCase = true) }
                    .map { it.nombre }
                    .toSet()
                val dates = libro.movimientos.asSequence()
                    .filter { it.activo in namesSharingSymbol }
                    .map { it.fecha }
                    .plus(
                        libro.aportacionesGratis.asSequence()
                            .filter { it.activo in namesSharingSymbol }
                            .map { it.fecha },
                    )
                    .filter(IsoDates::isValid)
                    .toList()
                TrackedQuoteAsset(asset.simbolo, dates)
            },
        )
    }

    override suspend fun applyQuotes(
        downloaded: Map<String, List<MarketQuote>>,
        refreshedOn: String,
    ): AppliedQuoteRefresh {
        var changed = readBook()
        var newDates = 0
        downloaded.forEach { (symbol, quotes) ->
            val domainQuotes = quotes.map { quote ->
                Cotizacion(quote.symbol, quote.date, quote.price, quote.currency)
            }
            val update = Calculos.guardarCotizaciones(changed, symbol, domainQuotes)
            changed = update.libro
            newDates += update.nuevas
        }
        changed = changed.copy(ajustes = changed.ajustes.copy(preciosAlDia = refreshedOn))
        writeBook(changed)
        return AppliedQuoteRefresh(newDates, downloaded.values.sumOf { it.size })
    }
}

sealed interface QuoteRefreshResult {
    data object NoSession : QuoteRefreshResult
    data object NoTrackedSymbols : QuoteRefreshResult
    data object AlreadyCurrent : QuoteRefreshResult
    data object NoData : QuoteRefreshResult
    data class Applied(val result: AppliedQuoteRefresh) : QuoteRefreshResult
}

/**
 * Coordinates desktop-compatible once-per-day refresh without depending on UI.
 * A forced refresh bypasses the client marker; the server still owns its global
 * once-per-symbol/day provider cache. Empty/offline downloads never advance the marker.
 */
class MarketQuoteSync(
    private val quotes: MarketQuoteRepository,
    private val book: MarketQuoteBookPort,
    private val today: () -> String = IsoDates::today,
) {
    suspend fun refresh(force: Boolean = false): QuoteRefreshResult {
        if (!quotes.hasSession()) return QuoteRefreshResult.NoSession
        val date = today()
        val snapshot = book.snapshot()
        val requests = MarketQuoteRules.refreshRequests(snapshot.trackedAssets, date)
        if (requests.isEmpty()) return QuoteRefreshResult.NoTrackedSymbols
        if (!force && snapshot.pricesCurrentOn == date) return QuoteRefreshResult.AlreadyCurrent

        val downloaded = linkedMapOf<String, List<MarketQuote>>()
        requests.forEach { request ->
            quotes.fetch(request.symbol, request.from).takeIf { it.isNotEmpty() }?.let {
                downloaded[request.symbol] = it
            }
        }
        if (downloaded.isEmpty()) return QuoteRefreshResult.NoData
        return QuoteRefreshResult.Applied(book.applyQuotes(downloaded, date))
    }
}

data class QuoteRefreshRequest(val symbol: String, val from: String)

data class QuoteMergeResult(
    val quotes: List<MarketQuote>,
    val newDates: Int,
)

data class ResolvedQuoteValuation(
    val marketValue: Double,
    val valuationDate: String,
    val unitPrice: Double,
    val quoted: Boolean,
    val unvalued: Boolean,
)

/** Pure quote rules shared by a book adapter and investment calculations. */
object MarketQuoteRules {
    fun refreshRequests(assets: List<TrackedQuoteAsset>, today: String): List<QuoteRefreshRequest> {
        val bySymbol = linkedMapOf<String, MutableList<String>>()
        assets.forEach { asset ->
            val symbol = normalizeSymbol(asset.symbol)
            if (symbol.isNotEmpty()) {
                bySymbol.getOrPut(symbol, ::mutableListOf)
                    .addAll(asset.contributionDates.filter(IsoDates::isValid))
            }
        }
        return bySymbol.map { (symbol, dates) ->
            QuoteRefreshRequest(symbol, dates.minOrNull() ?: today)
        }
    }

    fun quotesFor(quotes: List<MarketQuote>, symbol: String): List<MarketQuote> {
        val normalizedSymbol = normalizeSymbol(symbol)
        if (normalizedSymbol.isEmpty()) return emptyList()
        return quotes.asSequence()
            .map(MarketQuote::normalized)
            .filter { it.isValid && it.symbol == normalizedSymbol }
            .sortedBy(MarketQuote::date)
            .toList()
    }

    /** Latest close up to a date, so weekends and holidays use the previous trading day. */
    fun latest(quotes: List<MarketQuote>, symbol: String, through: String = ""): MarketQuote? =
        quotesFor(quotes, symbol).lastOrNull { through.isEmpty() || it.date <= through }

    /** Incoming same-day corrections win; [newDates] excludes corrected existing dates. */
    fun merge(
        existing: List<MarketQuote>,
        symbol: String,
        incoming: List<MarketQuote>,
    ): QuoteMergeResult {
        val normalizedSymbol = normalizeSymbol(symbol)
        if (normalizedSymbol.isEmpty()) return QuoteMergeResult(existing, 0)
        val byDate = quotesFor(existing, normalizedSymbol).associateByTo(linkedMapOf(), MarketQuote::date)
        val before = byDate.size
        incoming.asSequence()
            .map { it.copy(symbol = normalizedSymbol).normalized() }
            .filter { it.isValid }
            .forEach { byDate[it.date] = it }
        val otherSymbols = existing.filter { normalizeSymbol(it.symbol) != normalizedSymbol }
        return QuoteMergeResult(
            quotes = otherSymbols + byDate.toSortedMap().values,
            newDates = byDate.size - before,
        )
    }

    /**
     * A usable quote overrides both manual value and manual date. With no units,
     * no symbol, or no close, the manual valuation remains exactly as before.
     */
    fun resolveValuation(
        manualMarketValue: Double,
        manualValuationDate: String,
        totalTitles: Double,
        symbol: String,
        quotes: List<MarketQuote>,
        through: String = "",
    ): ResolvedQuoteValuation {
        val close = latest(quotes, symbol, through)
        val quoted = close != null && totalTitles > 0.0
        if (!quoted) {
            return ResolvedQuoteValuation(
                marketValue = manualMarketValue,
                valuationDate = manualValuationDate,
                unitPrice = 0.0,
                quoted = false,
                unvalued = manualValuationDate.isEmpty() && manualMarketValue == 0.0,
            )
        }
        val usedClose = checkNotNull(close)
        return ResolvedQuoteValuation(
            marketValue = DomainNumbers.money(totalTitles * usedClose.price),
            valuationDate = usedClose.date,
            unitPrice = usedClose.price,
            quoted = true,
            unvalued = false,
        )
    }

    private fun normalizeSymbol(value: String): String = value.trim().uppercase(Locale.ROOT)
}
