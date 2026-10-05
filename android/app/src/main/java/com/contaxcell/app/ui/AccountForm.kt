package com.contaxcell.app.ui

/**
 * Lo que se comprueba al crear la cuenta antes de mandar nada al servidor, con
 * las mismas medidas que pone él (server/contaserver/aplicacion.py) y que el
 * escritorio (escritorio/contaxcell/acceso.py). Así el aviso sale al momento y
 * en su sitio, sin esperar a la red.
 */
object AccountForm {
    const val USER_MIN = 3
    const val USER_MAX = 30
    const val PASSWORD_MIN = 8
    const val PASSWORD_MAX = 128
    private const val EMAIL_MAX = 254

    /** Que tenga pinta de correo. Que exista de verdad no se sabe hasta que se le escribe. */
    fun isEmail(raw: String): Boolean {
        val email = raw.trim()
        val at = email.indexOf('@')
        if (at <= 0 || email.length > EMAIL_MAX) return false
        val domain = email.substring(at + 1)
        return '@' !in domain && '.' in domain && !domain.startsWith('.') && !domain.endsWith('.') &&
            email.none { it.isWhitespace() || it.isISOControl() }
    }

    /** El primer problema, en el orden de los campos, o null si todo está bien. */
    fun newAccountProblem(user: String, email: String, password: String, repeated: String): String? = when {
        user.trim().length !in USER_MIN..USER_MAX ->
            "El usuario tiene que tener entre $USER_MIN y $USER_MAX caracteres."
        email.isBlank() -> "Falta el correo electrónico."
        !isEmail(email) -> "El correo no parece válido. Revisa que esté bien escrito."
        password.length < PASSWORD_MIN -> "La contraseña tiene que tener al menos $PASSWORD_MIN caracteres."
        password.length > PASSWORD_MAX -> "La contraseña no puede pasar de $PASSWORD_MAX caracteres."
        password != repeated -> "Las dos contraseñas no son iguales."
        else -> null
    }
}
