package com.contaxcell.app.data.remote

import com.contaxcell.app.data.sync.SessionStore
import com.contaxcell.app.domain.DomainNumbers
import com.contaxcell.app.domain.IsoDates
import java.util.Locale
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonPrimitive

data class QuoteSearchResult(
    val symbol: String,
    val name: String,
    val exchange: String = "",
    val currency: String = "",
    val price: Double = 0.0,
)

/** A daily close stored locally so investment values also work offline. */
data class MarketQuote(
    val symbol: String,
    val date: String,
    val price: Double,
    val currency: String = "EUR",
) {
    fun normalized(): MarketQuote = copy(
        symbol = symbol.trim().uppercase(Locale.ROOT),
        date = date.takeIf(IsoDates::isValid).orEmpty(),
        price = DomainNumbers.money(price),
        currency = currency.trim().ifEmpty { "EUR" },
    )

    val isValid: Boolean
        get() = symbol.isNotBlank() && IsoDates.isValid(date) && price > 0.0
}

class MarketQuoteException(
    message: String,
    val kind: Kind,
) : Exception(message) {
    enum class Kind {
        NO_SESSION,
        INVALID_QUERY,
        SESSION_EXPIRED,
        SERVER_NOT_CONFIGURED,
        PROVIDER_UNAVAILABLE,
        SERVER_ERROR,
        OFFLINE,
    }
}

/**
 * Authenticated access to contaserver's quote proxy.
 *
 * Interactive search reports useful failures. Historical refresh is deliberately
 * silent and returns an empty list, matching the desktop background refresh: the
 * previously cached closes remain authoritative when the network is unavailable.
 */
class MarketQuoteRepository(
    private val api: ContaXcellApi,
    private val sessions: SessionStore,
) {
    suspend fun hasSession(): Boolean = sessions.read().isSignedIn

    suspend fun search(rawQuery: String): List<QuoteSearchResult> {
        val session = sessions.read()
        if (!session.isSignedIn) {
            fail("Hace falta una cuenta para buscar cotizaciones.", MarketQuoteException.Kind.NO_SESSION)
        }

        val response = try {
            api.searchQuotes(session.serverUrl, session.token, rawQuery.trim())
        } catch (_: NetworkUnavailableException) {
            fail("No se ha podido hablar con el servidor.", MarketQuoteException.Kind.OFFLINE)
        }
        when (response.statusCode) {
            200 -> Unit
            401 -> {
                sessions.write(session.copy(expired = true))
                fail("La sesión ha caducado: entra de nuevo.", MarketQuoteException.Kind.SESSION_EXPIRED)
            }
            422 -> fail(
                response.detail() ?: "Escribe al menos dos letras para buscar.",
                MarketQuoteException.Kind.INVALID_QUERY,
            )
            503 -> fail(
                "El servidor no tiene configurada la clave de precios. Hay que ponerla en su archivo .env.",
                MarketQuoteException.Kind.SERVER_NOT_CONFIGURED,
            )
            502 -> fail(
                response.detail() ?: "El proveedor de precios no ha contestado.",
                MarketQuoteException.Kind.PROVIDER_UNAVAILABLE,
            )
            else -> fail(
                response.detail() ?: "El servidor ha contestado ${response.statusCode}.",
                MarketQuoteException.Kind.SERVER_ERROR,
            )
        }

        val raw = response.objectBody?.get("encontrados") as? JsonArray ?: return emptyList()
        return raw.mapNotNull { element ->
            val item = element as? JsonObject ?: return@mapNotNull null
            val symbol = item.text("simbolo").trim().uppercase(Locale.ROOT)
            if (symbol.isEmpty()) return@mapNotNull null
            QuoteSearchResult(
                symbol = symbol,
                name = item.text("nombre").trim(),
                exchange = item.text("bolsa").trim(),
                currency = item.text("moneda").trim(),
                // Search is a wire result; preserve the provider's precision. Stored
                // daily closes are normalized separately by MarketQuote.
                price = item.number("precio") ?: 0.0,
            )
        }
    }

    /** Returns no data on any background failure, exactly like the desktop client. */
    suspend fun fetch(symbol: String, from: String): List<MarketQuote> {
        val session = sessions.read()
        if (!session.isSignedIn) return emptyList()
        val normalizedSymbol = symbol.trim().uppercase(Locale.ROOT)
        if (normalizedSymbol.isEmpty() || !IsoDates.isValid(from)) return emptyList()
        val response = try {
            api.downloadQuotes(session.serverUrl, session.token, normalizedSymbol, from)
        } catch (_: NetworkUnavailableException) {
            return emptyList()
        }
        if (response.statusCode != 200) return emptyList()
        val raw = response.objectBody?.get("cotizaciones") as? JsonArray ?: return emptyList()
        return raw.mapNotNull { element ->
            val item = element as? JsonObject ?: return@mapNotNull null
            MarketQuote(
                symbol = normalizedSymbol,
                date = item.text("fecha"),
                price = item.number("precio") ?: 0.0,
                currency = item.text("moneda").ifEmpty { "EUR" },
            ).normalized().takeIf { it.isValid }
        }
    }

    private fun fail(message: String, kind: MarketQuoteException.Kind): Nothing =
        throw MarketQuoteException(message, kind)
}

private fun JsonObject.text(name: String): String =
    runCatching { get(name)?.jsonPrimitive?.contentOrNull.orEmpty() }.getOrDefault("")

private fun JsonObject.number(name: String): Double? =
    runCatching { get(name)?.jsonPrimitive?.doubleOrNull }.getOrNull()
