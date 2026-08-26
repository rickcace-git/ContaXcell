"""La API del servidor de sincronización.

Seis rutas y ninguna más:

- ``GET  /api/salud``              ¿está vivo el servidor?
- ``POST /api/cuentas/registro``   crear cuenta y recibir una ficha
- ``POST /api/cuentas/entrar``     entrar con usuario y contraseña
- ``POST /api/cuentas/contrasena`` cambiar la contraseña (con ficha)
- ``GET  /api/libro``              bajar el libro guardado (con ficha)
- ``PUT  /api/libro``              subir el libro (con ficha)

El libro viaja como el mismo JSON que la aplicación guarda en disco; el
servidor no lo mira por dentro. Cada libro lleva un número de *revisión* que
sube en uno con cada grabación: quien sube tiene que decir de qué revisión
partía, y si ya no es la actual recibe un 409 con lo que hay en el servidor,
para que sea el cliente quien decida cómo juntar las dos versiones.

Las cuentas llevan tres cuidados que no se ven desde fuera: el nombre de
usuario se normaliza siempre igual (para que «Ana» y «ana» sean la misma
persona), los intentos fallidos se cuentan y se cortan, y cambiar la
contraseña invalida las fichas antiguas de ese usuario.
"""

from __future__ import annotations

import hmac
import logging
import os
import time
import unicodedata

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from . import almacen as modulo_almacen
from . import limites
from . import seguridad

registro_log = logging.getLogger("contaserver")

# Reglas de las cuentas. Cortas y claras, y el mensaje de error las repite
# para que el usuario sepa qué arreglar.
USUARIO_MINIMO = 3
USUARIO_MAXIMO = 30
CONTRASENA_MINIMA = 8
# Un tope arriba también: amasar con scrypt una contraseña de un megabyte es
# trabajo regalado para quien quiera atascar el servidor.
CONTRASENA_MAXIMA = 128

# Cuántos intentos se aguantan y en cuánto tiempo. Diez fallos de entrada por
# cuarto de hora son de sobra para un despiste, y muy pocos para quien está
# probando contraseñas a mano llena.
ENTRAR_FALLOS = 10
ENTRAR_VENTANA = 15 * 60
# Los registros se cuentan todos, acierten o no: es la puerta por la que
# alguien podría llenar la base de cuentas basura.
REGISTRO_INTENTOS = 5
REGISTRO_VENTANA = 60 * 60

AVISO_DEMASIADOS = "Demasiados intentos. Espera un rato y prueba de nuevo."


def crear_aplicacion(
    almacen=None,
    secreto: bytes | None = None,
    codigo_registro: str | None = None,
    limite_entrar: tuple[int, float] | None = None,
    limite_registro: tuple[int, float] | None = None,
) -> FastAPI:
    """Monta la aplicación con el almacén que le den.

    Las pruebas pasan un ``AlmacenSQLite`` en memoria, un secreto fijo y, si
    les interesa, límites de intentos más bajos para no tener que fallar diez
    veces. En producción no se pasa nada: se lee CONTAXCELL_BASE_DATOS,
    CONTAXCELL_SECRETO y CONTAXCELL_CODIGO_REGISTRO del entorno.
    """
    if almacen is None:
        almacen = _almacen_desde_entorno()
    if secreto is None:
        secreto, generado = seguridad.secreto_del_servidor()
        if generado:
            registro_log.warning(
                "CONTAXCELL_SECRETO no está puesto: se usa un secreto "
                "aleatorio y las sesiones NO sobrevivirán a un reinicio."
            )
    if codigo_registro is None:
        codigo_registro = os.environ.get("CONTAXCELL_CODIGO_REGISTRO", "")
    codigo_registro = codigo_registro.strip()

    # Tres contadores: los fallos por IP, los fallos por cuenta y los
    # registros por IP. Separados a propósito: quien falla mucho contra una
    # cuenta no puede dejar fuera a los demás usuarios de su misma casa.
    maximo_entrar, ventana_entrar = limite_entrar or (ENTRAR_FALLOS, ENTRAR_VENTANA)
    maximo_registro, ventana_registro = limite_registro or (REGISTRO_INTENTOS, REGISTRO_VENTANA)
    fallos_por_ip = limites.Limitador(maximo_entrar, ventana_entrar)
    fallos_por_cuenta = limites.Limitador(maximo_entrar, ventana_entrar)
    registros_por_ip = limites.Limitador(maximo_registro, ventana_registro)

    app = FastAPI(title="ContaXcell Servidor", docs_url=None, redoc_url=None)

    # --- quién llama -----------------------------------------------------

    def usuario_actual(peticion: Request) -> int:
        """Saca el id de usuario de la cabecera Authorization, o corta con 401."""
        cabecera = peticion.headers.get("Authorization", "")
        if not cabecera.startswith("Bearer "):
            raise HTTPException(401, "Hace falta una ficha de sesión.")
        validada = seguridad.validar_ficha(secreto, cabecera[len("Bearer "):].strip())
        if validada is None:
            raise HTTPException(401, "La ficha de sesión no vale o ha caducado.")
        usuario_id, generacion = validada
        # La generación que trae la ficha tiene que ser la que el usuario
        # tiene ahora mismo. Si cambió la contraseña después de emitirse esta
        # ficha (o si el usuario ya no está), aquí se cae.
        if almacen.generacion_de(usuario_id) != generacion:
            raise HTTPException(401, "La ficha de sesión no vale o ha caducado.")
        return usuario_id

    def apuntar_fallo(usuario: str, ip: str) -> None:
        """Un fallo de contraseña: se cuenta y se deja dicho en el registro."""
        fallos_por_ip.apunta(ip)
        fallos_por_cuenta.apunta(usuario)
        registro_log.warning(
            "Entrada fallida: usuario=%r ip=%s", usuario, ip
        )

    # --- rutas -------------------------------------------------------------

    @app.get("/api/salud")
    def salud():
        return {"estado": "bien"}

    @app.post("/api/cuentas/registro", status_code=201)
    async def registro(peticion: Request):
        ip = _ip(peticion)
        # Aquí cuentan todos los intentos, no solo los que fallan: lo que se
        # frena es la creación de cuentas en cadena.
        if registros_por_ip.bloqueado(ip):
            registro_log.warning("Demasiados registros seguidos desde ip=%s", ip)
            raise HTTPException(429, AVISO_DEMASIADOS)
        registros_por_ip.apunta(ip)

        cuerpo = await _cuerpo_json(peticion)
        if codigo_registro:
            _comprobar_codigo(cuerpo.get("codigo"), codigo_registro, ip)
        usuario, contrasena = _credenciales(cuerpo)
        sal = seguridad.nueva_sal()
        hash_contrasena = seguridad.amasar_contrasena(contrasena, sal)
        try:
            usuario_id = almacen.crear_usuario(usuario, hash_contrasena, sal)
        except modulo_almacen.UsuarioYaExiste:
            raise HTTPException(409, "Ese nombre de usuario ya está cogido.")
        generacion = almacen.generacion_de(usuario_id) or 0
        return {
            "token": seguridad.crear_ficha(secreto, usuario_id, generacion),
            "usuario": usuario,
        }

    @app.post("/api/cuentas/entrar")
    async def entrar(peticion: Request):
        ip = _ip(peticion)
        cuerpo = await _cuerpo_json(peticion)
        usuario, contrasena = _credenciales(cuerpo)
        # El corte va ANTES de amasar nada: quien está bloqueado no consigue
        # que el servidor gaste ni un scrypt por él.
        if fallos_por_ip.bloqueado(ip) or fallos_por_cuenta.bloqueado(usuario):
            registro_log.warning(
                "Demasiados intentos de entrada: usuario=%r ip=%s", usuario, ip
            )
            raise HTTPException(429, AVISO_DEMASIADOS)

        encontrado = almacen.buscar_usuario(usuario)
        if encontrado is None:
            # Amasamos igualmente una contraseña de mentira para que la
            # respuesta tarde lo mismo exista o no el usuario, y no se pueda
            # adivinar quién tiene cuenta cronometrando.
            seguridad.amasar_contrasena(contrasena, seguridad.nueva_sal())
            apuntar_fallo(usuario, ip)
            raise HTTPException(401, "Usuario o contraseña incorrectos.")
        usuario_id, hash_guardado, sal, generacion = encontrado
        if not seguridad.contrasena_correcta(contrasena, sal, hash_guardado):
            apuntar_fallo(usuario, ip)
            raise HTTPException(401, "Usuario o contraseña incorrectos.")
        # Al acertar, la cuenta empieza de cero: los despistes de antes no se
        # le siguen guardando a quien sí sabe su contraseña.
        fallos_por_cuenta.olvida(usuario)
        return {
            "token": seguridad.crear_ficha(secreto, usuario_id, generacion),
            "usuario": usuario,
        }

    @app.post("/api/cuentas/contrasena")
    async def cambiar_contrasena(
        peticion: Request, usuario_id: int = Depends(usuario_actual)
    ):
        """Cambia la contraseña y devuelve una ficha nueva.

        Las fichas de antes dejan de valer al momento, esta incluida: es la
        forma de echar a la calle una sesión que se haya quedado por ahí.
        """
        ip = _ip(peticion)
        cuerpo = await _cuerpo_json(peticion)
        actual = cuerpo.get("contrasena_actual")
        nueva = cuerpo.get("contrasena_nueva")
        actual = actual if isinstance(actual, str) else ""
        nueva = nueva if isinstance(nueva, str) else ""
        _validar_contrasena(actual)
        _validar_contrasena(nueva)

        # Los fallos aquí cuentan igual que los de la entrada: por cuenta, y
        # para esta la clave es el id, que es lo único que trae la ficha.
        clave = f"id:{usuario_id}"
        if fallos_por_cuenta.bloqueado(clave):
            registro_log.warning(
                "Demasiados intentos de cambio de contraseña: usuario_id=%s ip=%s",
                usuario_id, ip,
            )
            raise HTTPException(429, AVISO_DEMASIADOS)

        credenciales = almacen.credenciales_por_id(usuario_id)
        if credenciales is None:
            raise HTTPException(401, "La ficha de sesión no vale o ha caducado.")
        hash_guardado, sal = credenciales
        if not seguridad.contrasena_correcta(actual, sal, hash_guardado):
            fallos_por_cuenta.apunta(clave)
            registro_log.warning(
                "Cambio de contraseña con la actual equivocada: usuario_id=%s ip=%s",
                usuario_id, ip,
            )
            raise HTTPException(403, "La contraseña actual no es correcta.")

        sal_nueva = seguridad.nueva_sal()
        generacion = almacen.cambiar_contrasena(
            usuario_id, seguridad.amasar_contrasena(nueva, sal_nueva), sal_nueva
        )
        if generacion is None:
            raise HTTPException(401, "La ficha de sesión no vale o ha caducado.")
        fallos_por_cuenta.olvida(clave)
        return {"token": seguridad.crear_ficha(secreto, usuario_id, generacion)}

    @app.get("/api/libro")
    def bajar_libro(usuario_id: int = Depends(usuario_actual)):
        revision, libro = almacen.leer_libro(usuario_id)
        return {"revision": revision, "libro": libro}

    @app.put("/api/libro")
    async def subir_libro(peticion: Request, usuario_id: int = Depends(usuario_actual)):
        cuerpo = await _cuerpo_json(peticion)
        revision_base = cuerpo.get("revision_base")
        libro = cuerpo.get("libro")
        if not isinstance(revision_base, int) or isinstance(revision_base, bool) or revision_base < 0:
            raise HTTPException(422, "Falta revision_base, que debe ser un número entero.")
        if not isinstance(libro, dict):
            raise HTTPException(422, "Falta el libro, que debe ser un objeto JSON.")

        revision_nueva = almacen.guardar_libro(usuario_id, revision_base, libro)
        if revision_nueva is None:
            # Alguien grabó antes desde otro sitio. Devolvemos el estado
            # actual del servidor y es el cliente quien resuelve el cruce.
            revision_actual, libro_actual = almacen.leer_libro(usuario_id)
            return JSONResponse(
                status_code=409,
                content={"revision": revision_actual, "libro": libro_actual},
            )
        return {"revision": revision_nueva}

    return app


# --- ayudas -------------------------------------------------------------------

async def _cuerpo_json(peticion: Request) -> dict:
    """El cuerpo de la petición como diccionario, o 422 en español."""
    try:
        cuerpo = await peticion.json()
    except Exception:
        raise HTTPException(422, "El cuerpo de la petición no es JSON válido.")
    if not isinstance(cuerpo, dict):
        raise HTTPException(422, "El cuerpo de la petición debe ser un objeto JSON.")
    return cuerpo


def _credenciales(cuerpo: dict) -> tuple[str, str]:
    """Saca y valida usuario y contraseña del cuerpo, con errores en español.

    El usuario sale ya normalizado, y es esa forma normalizada la que se
    guarda y la que se busca: por eso entrar y registrarse pasan los dos por
    aquí. Si no, «Ana» crearía una cuenta que «ana» no encontraría nunca.
    """
    usuario = _normalizar_usuario(cuerpo.get("usuario"))
    contrasena = cuerpo.get("contrasena")
    if not isinstance(contrasena, str):
        contrasena = ""
    if not (USUARIO_MINIMO <= len(usuario) <= USUARIO_MAXIMO):
        raise HTTPException(
            422,
            f"El usuario debe tener entre {USUARIO_MINIMO} y {USUARIO_MAXIMO} caracteres.",
        )
    _validar_contrasena(contrasena)
    return usuario, contrasena


def _normalizar_usuario(valor) -> str:
    """El nombre de usuario en su única forma buena.

    Tres cosas, en este orden: NFC junta las letras con tilde en un solo
    carácter (hay dos maneras de escribir «josé» y tienen que ser la misma),
    casefold pasa a minúsculas de verdad (también para la ß y compañía) y
    strip quita los espacios de los lados.

    Además se rechazan los caracteres de control y los invisibles: un nombre
    con un tabulador o con una marca de dirección de texto por dentro se
    parece a otro sin serlo, y eso vale para hacerse pasar por alguien.
    """
    usuario = unicodedata.normalize("NFC", str(valor or "")).casefold().strip()
    if any(unicodedata.category(letra).startswith("C") for letra in usuario):
        raise HTTPException(
            422, "El usuario no puede llevar caracteres invisibles ni de control."
        )
    return usuario


def _validar_contrasena(contrasena: str) -> None:
    """Comprueba el largo de la contraseña, con el mensaje en español."""
    if len(contrasena) < CONTRASENA_MINIMA:
        raise HTTPException(
            422,
            f"La contraseña debe tener al menos {CONTRASENA_MINIMA} caracteres.",
        )
    if len(contrasena) > CONTRASENA_MAXIMA:
        raise HTTPException(
            422,
            f"La contraseña no puede pasar de {CONTRASENA_MAXIMA} caracteres.",
        )


def _comprobar_codigo(codigo, esperado: str, ip: str) -> None:
    """El código de invitación, cuando el servidor pide uno.

    Se compara en tiempo constante para no ir chivando letra a letra por
    cuánto tarda la respuesta.
    """
    recibido = codigo if isinstance(codigo, str) else ""
    if not hmac.compare_digest(
        recibido.encode("utf-8"), esperado.encode("utf-8")
    ):
        registro_log.warning("Registro sin código de invitación válido: ip=%s", ip)
        raise HTTPException(
            403, "Este servidor pide un código de invitación para crear una cuenta."
        )


def _ip(peticion: Request) -> str:
    """La IP de quien llama, o 'desconocido' si el servidor no la sabe."""
    cliente = getattr(peticion, "client", None)
    return getattr(cliente, "host", None) or "desconocido"


def _almacen_desde_entorno():
    """El almacén de producción, con paciencia por si la base aún arranca.

    En docker-compose la API espera al healthcheck de Postgres, pero un
    pequeño reintento propio hace el arranque robusto también fuera de él.
    """
    url = os.environ.get("CONTAXCELL_BASE_DATOS", "").strip()
    if not url:
        registro_log.warning(
            "CONTAXCELL_BASE_DATOS no está puesta: se usa SQLite en memoria "
            "y los datos NO sobrevivirán a un reinicio. Solo vale para probar."
        )
        return modulo_almacen.AlmacenSQLite()

    ultimo_error = None
    for intento in range(10):
        try:
            return modulo_almacen.AlmacenPostgres(url)
        except Exception as error:  # la base aún no acepta conexiones
            ultimo_error = error
            registro_log.info("Esperando a la base de datos… (%s)", error)
            time.sleep(2)
    raise RuntimeError(f"No se pudo conectar con la base de datos: {ultimo_error}")


# uvicorn arranca esto: `uvicorn contaserver.aplicacion:app`
app = crear_aplicacion()
