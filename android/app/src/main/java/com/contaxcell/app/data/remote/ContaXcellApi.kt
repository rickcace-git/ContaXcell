package com.contaxcell.app.data.remote

import java.io.IOException
import java.net.URI
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonNull
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.HttpUrl.Companion.toHttpUrl

/** The exact transport surface exposed by contaserver. */
interface ContaXcellApi {
    suspend fun health(serverUrl: String): HttpResult
    suspend fun register(serverUrl: String, username: String, password: String, invitationCode: String = ""): HttpResult
    suspend fun login(serverUrl: String, username: String, password: String): HttpResult
    suspend fun changePassword(serverUrl: String, token: String, currentPassword: String, newPassword: String): HttpResult
    suspend fun downloadBook(serverUrl: String, token: String): HttpResult
    suspend fun uploadBook(serverUrl: String, token: String, baseRevision: Int, book: JsonObject): HttpResult
    suspend fun searchQuotes(serverUrl: String, token: String, query: String): HttpResult
    suspend fun downloadQuotes(serverUrl: String, token: String, symbol: String, from: String): HttpResult
}

data class HttpResult(
    val statusCode: Int,
    val body: JsonElement? = null,
) {
    val objectBody: JsonObject?
        get() = body as? JsonObject

    fun detail(): String? {
        val detail = objectBody?.get("detail") ?: objectBody?.get("detalle")
        return when (detail) {
            is JsonPrimitive -> detail.content
            else -> null
        }
    }
}

class NetworkUnavailableException(cause: IOException) : IOException(cause)

class InvalidServerUrlException(url: String) :
    IllegalArgumentException("La dirección del servidor no es válida: $url")

class OkHttpContaXcellApi(
    private val client: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(10, TimeUnit.SECONDS)
        .writeTimeout(10, TimeUnit.SECONDS)
        .build(),
    private val json: Json = Json { ignoreUnknownKeys = true },
) : ContaXcellApi {
    override suspend fun health(serverUrl: String) = request(serverUrl, "/api/salud", "GET")

    override suspend fun register(
        serverUrl: String,
        username: String,
        password: String,
        invitationCode: String,
    ): HttpResult = request(
        serverUrl,
        "/api/cuentas/registro",
        "POST",
        body = buildJsonObject {
            put("usuario", JsonPrimitive(username))
            put("contrasena", JsonPrimitive(password))
            invitationCode.trim().takeIf(String::isNotEmpty)?.let {
                put("codigo", JsonPrimitive(it))
            }
        },
    )

    override suspend fun login(serverUrl: String, username: String, password: String): HttpResult =
        request(
            serverUrl,
            "/api/cuentas/entrar",
            "POST",
            body = buildJsonObject {
                put("usuario", JsonPrimitive(username))
                put("contrasena", JsonPrimitive(password))
            },
        )

    override suspend fun changePassword(
        serverUrl: String,
        token: String,
        currentPassword: String,
        newPassword: String,
    ): HttpResult = request(
        serverUrl,
        "/api/cuentas/contrasena",
        "POST",
        token,
        buildJsonObject {
            put("contrasena_actual", JsonPrimitive(currentPassword))
            put("contrasena_nueva", JsonPrimitive(newPassword))
        },
    )

    override suspend fun downloadBook(serverUrl: String, token: String): HttpResult =
        request(serverUrl, "/api/libro", "GET", token)

    override suspend fun uploadBook(
        serverUrl: String,
        token: String,
        baseRevision: Int,
        book: JsonObject,
    ): HttpResult = request(
        serverUrl,
        "/api/libro",
        "PUT",
        token,
        buildJsonObject {
            put("revision_base", JsonPrimitive(baseRevision))
            put("libro", book)
        },
    )

    override suspend fun searchQuotes(
        serverUrl: String,
        token: String,
        query: String,
    ): HttpResult = request(
        serverUrl,
        "/api/precios/buscar",
        "GET",
        token,
        query = mapOf("q" to query),
    )

    override suspend fun downloadQuotes(
        serverUrl: String,
        token: String,
        symbol: String,
        from: String,
    ): HttpResult = request(
        serverUrl,
        "/api/precios",
        "GET",
        token,
        query = mapOf("simbolo" to symbol, "desde" to from),
    )

    private suspend fun request(
        serverUrl: String,
        path: String,
        method: String,
        token: String? = null,
        body: JsonObject? = null,
        query: Map<String, String> = emptyMap(),
    ): HttpResult = withContext(Dispatchers.IO) {
        val url = (normalizeServerUrl(serverUrl) + path).toHttpUrl().newBuilder().apply {
            query.forEach { (name, value) -> addQueryParameter(name, value) }
        }.build()
        val builder = Request.Builder()
            .url(url)
            .header("Accept", "application/json")
        if (!token.isNullOrBlank()) builder.header("Authorization", "Bearer $token")

        val requestBody = body?.let {
            json.encodeToString(JsonObject.serializer(), it)
                .toRequestBody(JSON_MEDIA_TYPE)
        }
        when (method) {
            "GET" -> builder.get()
            "POST" -> builder.post(requestBody ?: EMPTY_JSON_BODY)
            "PUT" -> builder.put(requestBody ?: EMPTY_JSON_BODY)
            else -> error("Unsupported HTTP method: $method")
        }

        try {
            client.newCall(builder.build()).execute().use { response ->
                val raw = response.body?.string().orEmpty()
                val parsed = if (raw.isBlank()) null else runCatching { json.parseToJsonElement(raw) }.getOrNull()
                HttpResult(response.code, parsed)
            }
        } catch (error: IOException) {
            throw NetworkUnavailableException(error)
        }
    }

    companion object {
        private val JSON_MEDIA_TYPE = "application/json; charset=utf-8".toMediaType()
        private val EMPTY_JSON_BODY = "{}".toRequestBody(JSON_MEDIA_TYPE)

        fun normalizeServerUrl(value: String): String {
            val trimmed = value.trim().trimEnd('/')
            val uri = runCatching { URI(trimmed) }.getOrNull()
                ?: throw InvalidServerUrlException(value)
            if (uri.scheme !in setOf("http", "https") || uri.host.isNullOrBlank()) {
                throw InvalidServerUrlException(value)
            }
            if (!uri.rawQuery.isNullOrEmpty() || !uri.rawFragment.isNullOrEmpty()) {
                throw InvalidServerUrlException(value)
            }
            return trimmed
        }
    }
}
