package com.contaxcell.app.ui

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Las mismas comprobaciones que escritorio/pruebas/test_acceso.py. */
class AccountFormTest {
    @Test
    fun goodEmails() {
        listOf("ana@correo.es", "  Ana.Perez+conta@sub.correo.com ", "a@b.co").forEach {
            assertTrue(it, AccountForm.isEmail(it))
        }
    }

    @Test
    fun badEmails() {
        listOf(
            "", "ana", "ana@", "@correo.es", "ana@correo", "ana@.es", "ana@correo.",
            "ana perez@correo.es", "ana@co@rreo.es", "a".repeat(250) + "@correo.es",
        ).forEach { assertFalse(it, AccountForm.isEmail(it)) }
    }

    @Test
    fun everythingRight() {
        assertNull(AccountForm.newAccountProblem("ana", "ana@correo.es", "contrasena1", "contrasena1"))
    }

    @Test
    fun eachProblemWithItsMessage() {
        fun problem(user: String = "ana", email: String = "ana@correo.es", password: String = "contrasena1", repeated: String = password) =
            AccountForm.newAccountProblem(user, email, password, repeated).orEmpty()
        assertTrue(problem(user = "ab").contains("usuario"))
        assertTrue(problem(email = " ").contains("Falta el correo"))
        assertTrue(problem(email = "ana@correo").contains("no parece válido"))
        assertTrue(problem(password = "corta").contains("al menos 8"))
        assertTrue(problem(repeated = "contrasena2").contains("no son iguales"))
    }

    @Test
    fun theFirstFieldWins() {
        assertEquals(
            "El usuario tiene que tener entre 3 y 30 caracteres.",
            AccountForm.newAccountProblem("", "", "", "x"),
        )
    }
}
