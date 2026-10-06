package com.contaxcell.app.data.update

import java.io.File
import java.math.BigInteger
import java.security.KeyFactory
import java.security.KeyPairGenerator
import java.security.MessageDigest
import java.security.PrivateKey
import java.security.Signature
import java.security.spec.RSAPublicKeySpec
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Test

class AppUpdaterTest {
    private val keys = KeyPairGenerator.getInstance("RSA").apply { initialize(2048) }.generateKeyPair()
    private val apk = "un apk de mentira".toByteArray()

    private fun note(versionCode: Int = 48, path: String = "/api/actualizacion/ContaXcell-android-48.apk") = """
        {"versionCode": $versionCode, "versionName": "1.0.$versionCode", "archivo": "$path",
         "tamano": ${apk.size}, "sha256": "${sha256(apk)}", "notas": "Cosas nuevas",
         "historial": [
           {"versionCode": 48, "versionName": "1.0.48", "cambios": [{"titulo": "Lo de la 48", "detalle": "Con su porqué"}]},
           {"versionCode": 40, "versionName": "1.0.40", "cambios": [{"titulo": "Lo de la 40"}]}
         ]}
    """.trimIndent().toByteArray()

    private fun sign(bytes: ByteArray, key: PrivateKey = keys.private): ByteArray =
        Signature.getInstance("SHA256withRSA").run { initSign(key); update(bytes); sign() }

    private fun sha256(bytes: ByteArray) =
        MessageDigest.getInstance("SHA-256").digest(bytes).joinToString("") { "%02x".format(it) }

    private class FakeServer(val files: Map<String, FetchResult>) : UpdateFetcher {
        val tokens = mutableListOf<String>()
        override suspend fun get(url: String, token: String): FetchResult {
            tokens += token
            return files[url.removePrefix("https://servidor")] ?: FetchResult(404)
        }
        override suspend fun download(url: String, token: String, target: File, onProgress: (Float) -> Unit): Int {
            val file = files[url.removePrefix("https://servidor")] ?: return 404
            target.writeBytes(file.body)
            onProgress(1f)
            return file.status
        }
    }

    private fun server(note: ByteArray = note(), signature: ByteArray = sign(note), apkBytes: ByteArray = apk) =
        FakeServer(mapOf(
            UpdateNote.NOTE to FetchResult(200, note),
            UpdateNote.SIGNATURE to FetchResult(200, signature),
            "/api/actualizacion/ContaXcell-android-48.apk" to FetchResult(200, apkBytes),
        ))

    @Test
    fun aNewerSignedVersionIsOfferedWithTheSessionToken() = runTest {
        val fake = server()
        val update = AppUpdater(fake, keys.public).check("https://servidor/", "t0ken", currentCode = 40)!!
        assertEquals("1.0.48", update.versionName)
        assertEquals(listOf("t0ken", "t0ken"), fake.tokens)
    }

    @Test
    fun theSameOrAnOlderVersionIsNot() = runTest {
        assertNull(AppUpdater(server(), keys.public).check("https://servidor", "t", currentCode = 48))
    }

    @Test
    fun nothingPublishedIsNothingNew() = runTest {
        assertNull(AppUpdater(FakeServer(emptyMap()), keys.public).check("https://servidor", "t", 1))
    }

    @Test
    fun aNoteSignedByAnotherKeyIsRejected() = runTest {
        val other = KeyPairGenerator.getInstance("RSA").apply { initialize(2048) }.generateKeyPair()
        val note = note()
        expect<UntrustedUpdateException> {
            AppUpdater(server(note, sign(note, other.private)), keys.public).check("https://servidor", "t", 1)
        }
    }

    @Test
    fun aTamperedNoteIsRejected() = runTest {
        val note = note()
        val tampered = note.decodeToString().replace("1.0.48", "9.9.99").toByteArray()
        expect<UntrustedUpdateException> {
            AppUpdater(server(tampered, sign(note)), keys.public).check("https://servidor", "t", 1)
        }
    }

    @Test
    fun aPathOutsideTheUpdatesIsRejected() = runTest {
        val note = note(path = "/descargas/ContaXcell.apk")
        expect<UntrustedUpdateException> {
            AppUpdater(server(note), keys.public).check("https://servidor", "t", 1)
        }
    }

    @Test
    fun anAccountThatIsNotAcceptedGetsNothing() = runTest {
        val fake = FakeServer(mapOf(UpdateNote.NOTE to FetchResult(403)))
        expect<UpdateNotAllowedException> { AppUpdater(fake, keys.public).check("https://servidor", "t", 1) }
    }

    @Test
    fun eachPhoneSeesOnlyWhatItIsMissing() = runTest {
        val update = AppUpdater(server(), keys.public).check("https://servidor", "t", 1)!!
        assertEquals(listOf(48, 40), update.changesSince(1).map { it.versionCode })
        assertEquals(listOf(48), update.changesSince(40).map { it.versionCode })
        assertEquals("Con su porqué", update.changesSince(40).single().changes.single().detail)
    }

    @Test
    fun theDownloadMustBeTheApkOfTheNote() = runTest {
        val folder = createTempDir()
        val good = AppUpdater(server(), keys.public)
        val update = good.check("https://servidor", "t", 1)!!
        assertEquals(apk.toList(), good.download("https://servidor", "t", update, folder) {}.readBytes().toList())

        val bad = AppUpdater(server(apkBytes = "otro apk de mentira".toByteArray()), keys.public)
        expect<UntrustedUpdateException> { bad.download("https://servidor", "t", update, folder) {} }
        assertTrue(folder.listFiles().orEmpty().isEmpty())
    }

    /** Una firma hecha con escritorio/contaxcell/firma.py, el que firma de verdad, vale aquí. */
    @Test
    fun aSignatureFromTheDesktopSignerIsAccepted() {
        val key = KeyFactory.getInstance("RSA").generatePublic(
            RSAPublicKeySpec(BigInteger(PYTHON_N), BigInteger("65537")),
        )
        val note = "{\"versionCode\": 48, \"versionName\": \"1.0.48\"}".toByteArray()
        val signature = PYTHON_SIGNATURE.chunked(2).map { it.toInt(16).toByte() }.toByteArray()
        assertTrue(UpdateNote.verify(note, signature, key))
        assertTrue(!UpdateNote.verify(note + ' '.code.toByte(), signature, key))
    }

    @Test
    fun theHistoryInsideTheAppIsRead() {
        val json = """
            [{"versionCode": 14, "versionName": "1.0.14", "fecha": "2026-10-06",
              "cambios": [{"titulo": "Ayuda en Ajustes", "detalle": "Condiciones e historial"}]},
             {"versionCode": 13, "versionName": "1.0.13", "fecha": "2026-10-06", "cambios": []}]
        """.trimIndent().toByteArray()
        val history = UpdateNote.parseHistory(json)
        assertEquals(listOf(14, 13), history.map { it.versionCode })
        assertEquals("2026-10-06", history.first().date)
        assertEquals("Condiciones e historial", history.first().changes.single().detail)
        assertEquals(emptyList<AppRelease>(), UpdateNote.parseHistory("no es json".toByteArray()))
    }

    @Test
    fun theOfficialKeyLoads() {
        assertEquals(3072, (UpdateNote.officialKey() as java.security.interfaces.RSAPublicKey).modulus.bitLength())
    }

    private suspend inline fun <reified T : Throwable> expect(crossinline block: suspend () -> Unit) {
        try {
            block()
            fail("se esperaba ${T::class.simpleName}")
        } catch (error: Throwable) {
            if (error !is T) throw error
        }
    }

    private companion object {
        const val PYTHON_N = "159068668402647288499261017995004884084355403753739287110533782634692032880133668123124281287465385782174533874016730144748252546151700906948274223602069605313120669315307698991464571585906387696325481311843083221249106592104895378918273355502818890247622845655558652845365612377385940833524411345944586851859"
        const val PYTHON_SIGNATURE = "5d8d1146fb84087799bafc055c14128a4f14cd846fff87cad10c8139a1364121470e087f33516af66dfc3b17c4e7f712a7b28dfa91b6e06c3db81f60549877d681f826a589cda203ba943c71abec3c155f791997fdff057c6fff416b9da2f5186c228e32ee5b8459fb1026ee817b5b1bfde5720a0fd431870d38456d6ca4fc2e"
    }
}
