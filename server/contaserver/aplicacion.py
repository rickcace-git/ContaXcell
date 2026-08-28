"""La API del servidor de sincronización.

Siete rutas y ninguna más:

- ``GET  /api/salud``            ¿está vivo el servidor?
- ``POST /api/cuentas/registro`` crear cuenta y recibir una ficha
- ``POST /api/cuentas/entrar``   entrar con usuario y contraseña
- ``GET  /api/libro``            bajar el libro guardado (con ficha)
- ``PUT  /api/libro``            subir el libro (con ficha)
- ``GET  /api/precios/buscar``   buscar la cotización de un fondo (con ficha)
- ``GET  /api/precios``          los cierres diarios de un fondo (con ficha)

Los precios están aquí y no en cada aplicación porque el proveedor pide una
clave, y la aplicación se reparte como un `.exe`: una clave metida ahí sería
pública. Además así se pregunta una vez al día por fondo para todo el grupo
en vez de una vez por cada uno.

El libro viaja como el mismo JSON que la aplicación guarda en disco; el
servidor no lo mira por dentro. Cada libro lleva un número de *revisión* que
sube en uno con cada grabación: quien sube tiene que decir de qué revisión
partía, y si ya no es la actual recibe un 409 con lo que hay en el servidor,
para que sea el cliente quien decida cómo juntar las dos versiones.
"""

from __future__ import annotations

import logging
import os
import time

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from . import almacen as modulo_almacen
from . import precios
from . import seguridad

registro_log = logging.getLogger("contaserver")

# Reglas de las cuentas. Cortas y claras, y el mensaje de error las repite
# para que el usuario sepa qué arreglar.
USUARIO_MINIMO = 3
USUARIO_MAXIMO = 30
CONTRASENA_MINIMA = 8


# Marca para distinguir «no me han dicho nada» de «me han dicho que sin
# cliente de precios». Con None no se podrían separar las dos cosas, y las
# pruebas que no van de precios acabarían avisando de que falta la clave.
_SIN_DECIR = object()


def crear_aplicacion(almacen=None, secreto: bytes | None = None,
                     cliente_precios=_SIN_DECIR) -> FastAPI:
    """Monta la aplicación con el almacén que le den.

    Las pruebas pasan un ``AlmacenSQLite`` en memoria, un secreto fijo y un
    cliente de precios de mentira, y así corren sin red y sin clave. En
    producción no se pasa nada: se lee todo del entorno.
    """
    if almacen is None:
        almacen = _almacen_desde_entorno()
    if cliente_precios is _SIN_DECIR:
        cliente_precios = _cliente_precios_desde_entorno()
    servicio_precios = precios.ServicioPrecios(almacen, cliente_precios)
    if secreto is None:
        secreto, generado = seguridad.secreto_del_servidor()
        if generado:
            registro_log.warning(
                "CONTAXCELL_SECRETO no está puesto: se usa un secreto "
                "aleatorio y las sesiones NO sobrevivirán a un reinicio."
            )

    app = FastAPI(title="ContaXcell Servidor", docs_url=None, redoc_url=None)

    # --- quién llama -----------------------------------------------------

    def usuario_actual(peticion: Request) -> int:
        """Saca el id de usuario de la cabecera Authorization, o corta con 401."""
        cabecera = peticion.headers.get("Authorization", "")
        if not cabecera.startswith("Bearer "):
            raise HTTPException(401, "Hace falta una ficha de sesión.")
        usuario_id = seguridad.validar_ficha(secreto, cabecera[len("Bearer "):].strip())
        if usuario_id is None:
            raise HTTPException(401, "La ficha de sesión no vale o ha caducado.")
        return usuario_id

    # --- rutas -------------------------------------------------------------

    @app.get("/api/salud")
    def salud():
        return {"estado": "bien"}

    @app.post("/api/cuentas/registro", status_code=201)
    async def registro(peticion: Request):
        usuario, contrasena = await _credenciales(peticion)
        sal = seguridad.nueva_sal()
        hash_contrasena = seguridad.amasar_contrasena(contrasena, sal)
        try:
            usuario_id = almacen.crear_usuario(usuario, hash_contrasena, sal)
        except modulo_almacen.UsuarioYaExiste:
            raise HTTPException(409, "Ese nombre de usuario ya está cogido.")
        return {"token": seguridad.crear_ficha(secreto, usuario_id), "usuario": usuario}

    @app.post("/api/cuentas/entrar")
    async def entrar(peticion: Request):
        usuario, contrasena = await _credenciales(peticion)
        encontrado = almacen.buscar_usuario(usuario)
        if encontrado is None:
            # Amasamos igualmente una contraseña de mentira para que la
            # respuesta tarde lo mismo exista o no el usuario, y no se pueda
            # adivinar quién tiene cuenta cronometrando.
            seguridad.amasar_contrasena(contrasena, seguridad.nueva_sal())
            raise HTTPException(401, "Usuario o contraseña incorrectos.")
        usuario_id, hash_guardado, sal = encontrado
        if not seguridad.contrasena_correcta(contrasena, sal, hash_guardado):
            raise HTTPException(401, "Usuario o contraseña incorrectos.")
        return {"token": seguridad.crear_ficha(secreto, usuario_id), "usuario": usuario}

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

    # --- precios ---------------------------------------------------------
    #
    # Piden ficha como todo lo demás: el servidor es de un grupo cerrado y no
    # tiene por qué servir de puente a cualquiera que pase por delante.

    @app.get("/api/precios/buscar")
    def buscar_cotizacion(q: str = "", _id: int = Depends(usuario_actual)):
        """Las cotizaciones que encajan con lo buscado.

        Hace falta porque el mismo fondo cotiza en varias bolsas y monedas:
        el de Londres va en dólares y el de Milán en euros. La buena es
        aquella en la que compraste, y eso solo lo sabe el usuario.
        """
        texto = q.strip()
        if len(texto) < 2:
            raise HTTPException(422, "Escribe al menos dos letras para buscar.")
        try:
            return {"encontrados": servicio_precios.buscar(texto)}
        except precios.SinClave:
            raise HTTPException(503, "El servidor no tiene configurada la clave "
                                     "de precios. Ponla en el archivo .env.")
        except precios.ErrorDelProveedor as error:
            raise HTTPException(502, f"El proveedor de precios no ha contestado: {error}")

    @app.get("/api/precios")
    def cotizaciones(simbolo: str = "", desde: str = "",
                     _id: int = Depends(usuario_actual)):
        """Los cierres diarios de un fondo, desde la fecha que se pida.

        No falla si el proveedor está caído: devuelve lo que haya guardado,
        que para una cartera es más útil que un error.
        """
        if not simbolo.strip():
            raise HTTPException(422, "Falta el símbolo del fondo.")
        if not _es_fecha(desde):
            raise HTTPException(422, "Falta «desde», con el formato AAAA-MM-DD.")
        encontradas = servicio_precios.cotizaciones(simbolo, desde)
        return {
            "simbolo": simbolo.strip().upper(),
            "cotizaciones": [c.a_json() for c in encontradas],
        }

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


async def _credenciales(peticion: Request) -> tuple[str, str]:
    """Saca y valida usuario y contraseña del cuerpo, con errores en español."""
    cuerpo = await _cuerpo_json(peticion)
    usuario = str(cuerpo.get("usuario") or "").strip()
    contrasena = cuerpo.get("contrasena")
    if not isinstance(contrasena, str):
        contrasena = ""
    if not (USUARIO_MINIMO <= len(usuario) <= USUARIO_MAXIMO):
        raise HTTPException(
            422,
            f"El usuario debe tener entre {USUARIO_MINIMO} y {USUARIO_MAXIMO} caracteres.",
        )
    if len(contrasena) < CONTRASENA_MINIMA:
        raise HTTPException(
            422,
            f"La contraseña debe tener al menos {CONTRASENA_MINIMA} caracteres.",
        )
    return usuario, contrasena


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

def _es_fecha(texto: str) -> bool:
    """'AAAA-MM-DD' y nada más. Las fechas viajan como texto en todo el
    proyecto, y aquí solo hace falta comprobar que lo son."""
    from datetime import date
    try:
        date.fromisoformat(str(texto or "").strip())
    except ValueError:
        return False
    return True


def _cliente_precios_desde_entorno():
    """El cliente de precios. El de ahora no pide clave, así que siempre hay
    uno; se deja la función para que cambiar de proveedor sea tocar aquí."""
    return precios.ClienteYahoo()


# uvicorn arranca esto: `uvicorn contaserver.aplicacion:app`
app = crear_aplicacion()
