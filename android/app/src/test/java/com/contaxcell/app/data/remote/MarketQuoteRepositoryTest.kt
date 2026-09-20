package com.contaxcell.app.data.remote

import com.contaxcell.app.data.sync.SessionStore
import com.contaxcell.app.data.sync.SyncSession
import java.io.IOException
import kotlinx.coroutines.test.runTest
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonArray
import kotlinx.serialization.json.buildJsonObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Protocol
import okhttp3.Request
import okhttp3.Response
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class MarketQuoteRepositoryTest {
    @Test
    fun okHttpApiUsesExactAuthenticatedPathsAndEncodedQueryParameters() = runTest {
        val requests = mutableListOf<Request>()
        val client = OkHttpClient.Builder().addInterceptor { chain ->
            chain.request().also(requests::add).let { request ->
                Response.Builder()
                    .request(request)
                    .protocol(Protocol.HTTP_1_1)
                    .code(200)
                    .message("OK")
                    .body("{}".toResponseBody("application/json".toMediaType()))
                    .build()
            }
        }.build()
        val api = OkHttpContaXcellApi(client)

        api.searchQuotes("https://example.test/", "secret", "msci world & value")
        api.downloadQuotes("https://example.test", "secret", "SWDA:XMIL", "2026-01-01")

        assertEquals("/api/precios/buscar", requests[0].url.encodedPath)
        assertEquals("msci world & value", requests[0].url.queryParameter("q"))
        assertEquals("Bearer secret", requests[0].header("Authorization"))
        assertEquals("/api/precios", requests[1].url.encodedPath)
        assertEquals("SWDA:XMIL", requests[1].url.queryParameter("simbolo"))
        assertEquals("2026-01-01", requests[1].url.queryParameter("desde"))
    }

    @Test
    fun searchUsesAuthenticatedContractAndNormalizesResults() = runTest {
        val api = QuoteFakeApi().apply {
            searchResponse = HttpResult(200, buildJsonObject {
                put("encontrados", buildJsonArray {
                    add(buildJsonObject {
                        put("simbolo", JsonPrimitive("swda:xmil"))
                        put("nombre", JsonPrimitive("iShares World"))
                        put("bolsa", JsonPrimitive("Milan"))
                        put("moneda", JsonPrimitive("EUR"))
                        put("precio", JsonPrimitive(126.678))
                    })
                    add(buildJsonObject { put("nombre", JsonPrimitive("sin símbolo")) })
                })
            })
        }
        val repository = MarketQuoteRepository(api, QuoteMemorySessions(signedInSession()))

        val found = repository.search("  msci world  ")

        assertEquals("msci world", api.searchedFor)
        assertEquals(1, found.size)
        assertEquals(QuoteSearchResult("SWDA:XMIL", "iShares World", "Milan", "EUR", 126.678), found.single())
    }

    @Test
    fun unauthorizedSearchExpiresSessionAndRaisesTypedFailure() = runTest {
        val sessions = QuoteMemorySessions(signedInSession())
        val api = QuoteFakeApi().apply { searchResponse = HttpResult(401) }

        val error = runCatching { MarketQuoteRepository(api, sessions).search("msci") }
            .exceptionOrNull() as MarketQuoteException

        assertEquals(MarketQuoteException.Kind.SESSION_EXPIRED, error.kind)
        assertTrue(sessions.value.expired)
    }

    @Test
    fun providerSearchFailureKeepsServerDetail() = runTest {
        val api = QuoteFakeApi().apply {
            searchResponse = HttpResult(502, buildJsonObject {
                put("detail", JsonPrimitive("El proveedor de precios no ha contestado: se ha caído"))
            })
        }

        val error = runCatching {
            MarketQuoteRepository(api, QuoteMemorySessions(signedInSession())).search("msci")
        }.exceptionOrNull() as MarketQuoteException

        assertEquals(MarketQuoteException.Kind.PROVIDER_UNAVAILABLE, error.kind)
        assertEquals("El proveedor de precios no ha contestado: se ha caído", error.message)
    }

    @Test
    fun historicalRefreshIsSilentAndKeepsOnlyValidTwoDecimalCloses() = runTest {
        val api = QuoteFakeApi().apply {
            downloadResponse = HttpResult(200, buildJsonObject {
                put("cotizaciones", buildJsonArray {
                    add(buildJsonObject {
                        put("fecha", JsonPrimitive("2026-08-26"))
                        put("precio", JsonPrimitive(126.6789))
                        put("moneda", JsonPrimitive("EUR"))
                    })
                    add(buildJsonObject {
                        put("fecha", JsonPrimitive("ayer"))
                        put("precio", JsonPrimitive(99))
                    })
                    add(buildJsonObject {
                        put("fecha", JsonPrimitive("2026-08-27"))
                        put("precio", JsonPrimitive(0))
                    })
                })
            })
        }
        val repository = MarketQuoteRepository(api, QuoteMemorySessions(signedInSession()))

        assertEquals(
            listOf(MarketQuote("SWDA:XMIL", "2026-08-26", 126.68, "EUR")),
            repository.fetch(" swda:xmil ", "2026-01-01"),
        )
        api.downloadFailure = NetworkUnavailableException(IOException("offline"))
        assertEquals(emptyList<MarketQuote>(), repository.fetch("SWDA:XMIL", "2026-01-01"))
    }
}

private fun signedInSession() = SyncSession("https://example.test", "ana", "token")

private class QuoteMemorySessions(initial: SyncSession = SyncSession()) : SessionStore {
    var value = initial
    override suspend fun read() = value
    override suspend fun write(session: SyncSession) { value = session }
    override suspend fun clear() { value = SyncSession() }
}

private class QuoteFakeApi : ContaXcellApi {
    var searchedFor = ""
    var searchResponse = HttpResult(500)
    var downloadResponse = HttpResult(500)
    var downloadFailure: NetworkUnavailableException? = null

    override suspend fun searchQuotes(serverUrl: String, token: String, query: String): HttpResult {
        searchedFor = query
        return searchResponse
    }

    override suspend fun downloadQuotes(serverUrl: String, token: String, symbol: String, from: String): HttpResult {
        downloadFailure?.let { throw it }
        return downloadResponse
    }

    override suspend fun health(serverUrl: String) = HttpResult(200)
    override suspend fun register(serverUrl: String, username: String, password: String, invitationCode: String) = HttpResult(500)
    override suspend fun login(serverUrl: String, username: String, password: String) = HttpResult(500)
    override suspend fun changePassword(serverUrl: String, token: String, currentPassword: String, newPassword: String) = HttpResult(500)
    override suspend fun downloadBook(serverUrl: String, token: String) = HttpResult(500)
    override suspend fun uploadBook(serverUrl: String, token: String, baseRevision: Int, book: JsonObject) = HttpResult(500)
}
