"""Pruebas de la API completa, sin red y sin Docker.

Se monta la aplicación con un almacén SQLite en memoria y se le habla con el
TestClient de FastAPI, que hace las peticiones por dentro sin abrir puertos.
Cada prueba arranca con un servidor recién hecho y vacío.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

# Para poder correr las pruebas desde server/ sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from contaserver import limites
from contaserver import seguridad
from contaserver.almacen import AlmacenSQLite
from contaserver.aplicacion import crear_aplicacion

SECRETO_DE_PRUEBA = b"secreto-solo-para-las-pruebas"

# Varias pruebas provocan avisos a propósito (entradas fallidas, límites de
# intentos, registros sin código). Sin este manejador que no hace nada, el
# registro los escupiría por pantalla y parecería que algo va mal.
logging.getLogger("contaserver").addHandler(logging.NullHandler())


def cliente_nuevo(**opciones) -> TestClient:
    """Un servidor recién levantado, con la base vacía.

    Las opciones van tal cual a ``crear_aplicacion``: sirven para pedir un
    código de invitación o unos límites de intentos más bajos, que es lo que
    permite probar el 429 sin tener que fallar diez veces.

    Sin cliente de precios: estas pruebas no van de eso y así no avisan de
    nada por una fuente que no van a usar.
    """
    opciones.setdefault("cliente_precios", None)
    app = crear_aplicacion(almacen=AlmacenSQLite(), secreto=SECRETO_DE_PRUEBA, **opciones)
    return TestClient(app)


def registrar(
    cliente: TestClient,
    usuario: str = "ana",
    contrasena: str = "contrasena1",
    codigo: str | None = None,
) -> str:
    """Registra y devuelve el token, dando por buena la respuesta."""
    cuerpo = {"usuario": usuario, "contrasena": contrasena}
    if codigo is not None:
        cuerpo["codigo"] = codigo
    respuesta = cliente.post("/api/cuentas/registro", json=cuerpo)
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["token"]


def cabecera_cruda(valor: str) -> bytes:
    """La cabecera tal cual, byte a byte.

    El cliente de las pruebas no deja mandar como texto una cabecera con
    caracteres fuera del ASCII, y aquí lo raro es justo lo que se quiere
    probar: la ficha llega del mundo exterior y puede traer cualquier cosa.
    """
    return valor.encode("latin-1")


UN_LIBRO = {"version": 1, "movimientos": [{"fecha": "2026-01-15", "importe": 12.5}]}
OTRO_LIBRO = {"version": 1, "movimientos": []}


class PruebaSalud(unittest.TestCase):
    def test_salud(self):
        respuesta = cliente_nuevo().get("/api/salud")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"estado": "bien"})


class PruebaCuentas(unittest.TestCase):
    def test_registro_devuelve_token(self):
        respuesta = cliente_nuevo().post(
            "/api/cuentas/registro",
            json={"usuario": "  ana  ", "contrasena": "contrasena1"},
        )
        self.assertEqual(respuesta.status_code, 201)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["usuario"], "ana")  # llega recortado
        self.assertTrue(cuerpo["token"])

    def test_registro_usuario_repetido_da_409(self):
        cliente = cliente_nuevo()
        registrar(cliente, "ana")
        respuesta = cliente.post(
            "/api/cuentas/registro",
            json={"usuario": "ana", "contrasena": "otracontrasena"},
        )
        self.assertEqual(respuesta.status_code, 409)

    def test_registro_valida_usuario_y_contrasena(self):
        cliente = cliente_nuevo()
        casos = [
            {"usuario": "ab", "contrasena": "contrasena1"},        # usuario corto
            {"usuario": "a" * 31, "contrasena": "contrasena1"},    # usuario largo
            {"usuario": "ana", "contrasena": "corta"},             # contraseña corta
            {"usuario": "   ", "contrasena": "contrasena1"},       # solo espacios
        ]
        for cuerpo in casos:
            respuesta = cliente.post("/api/cuentas/registro", json=cuerpo)
            self.assertEqual(respuesta.status_code, 422, cuerpo)
            # El mensaje va en 'detail' y en español.
            self.assertIn("detail", respuesta.json())

    def test_entrar_con_credenciales_buenas(self):
        cliente = cliente_nuevo()
        registrar(cliente, "ana", "contrasena1")
        respuesta = cliente.post(
            "/api/cuentas/entrar",
            json={"usuario": "ana", "contrasena": "contrasena1"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["usuario"], "ana")
        self.assertTrue(respuesta.json()["token"])

    def test_entrar_con_contrasena_mala_da_401(self):
        cliente = cliente_nuevo()
        registrar(cliente, "ana", "contrasena1")
        respuesta = cliente.post(
            "/api/cuentas/entrar",
            json={"usuario": "ana", "contrasena": "equivocada1"},
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_entrar_con_usuario_inexistente_da_401(self):
        respuesta = cliente_nuevo().post(
            "/api/cuentas/entrar",
            json={"usuario": "nadie", "contrasena": "contrasena1"},
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_contrasena_de_129_no_vale_y_de_128_si(self):
        # El tope de arriba está para que nadie mande un megabyte y ponga al
        # servidor a amasarlo. 128 caracteres son de sobra para cualquiera.
        cliente = cliente_nuevo()
        larga = cliente.post(
            "/api/cuentas/registro",
            json={"usuario": "ana", "contrasena": "a" * 129},
        )
        self.assertEqual(larga.status_code, 422)
        justa = cliente.post(
            "/api/cuentas/registro",
            json={"usuario": "ana", "contrasena": "a" * 128},
        )
        self.assertEqual(justa.status_code, 201)


class PruebaNombresDeUsuario(unittest.TestCase):
    """El nombre se normaliza siempre igual, se escriba como se escriba."""

    def test_mayusculas_y_espacios_son_la_misma_cuenta(self):
        cliente = cliente_nuevo()
        registrar(cliente, "Ana ", "contrasena1")
        respuesta = cliente.post(
            "/api/cuentas/entrar",
            json={"usuario": "ana", "contrasena": "contrasena1"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["usuario"], "ana")

    def test_las_dos_maneras_de_escribir_jose_son_la_misma(self):
        # Unicode deja escribir «josé» con la é entera o con la e y la tilde
        # por separado. Se ven igual, así que tienen que ser la misma cuenta.
        separado = "jose\u0301"   # la e y la tilde, cada una por su lado
        entero = "jos\u00e9"      # la é de una pieza
        cliente = cliente_nuevo()
        registrar(cliente, separado, "contrasena1")
        respuesta = cliente.post(
            "/api/cuentas/entrar",
            json={"usuario": entero, "contrasena": "contrasena1"},
        )
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["usuario"], entero)

    def test_caracteres_invisibles_dan_422(self):
        cliente = cliente_nuevo()
        # Nulo, tabulador por dentro y marca de dirección de texto: tres
        # cosas que no se ven pero cuelan un nombre parecido a otro.
        casos = ["an\u0000a", "an\ta", "an\u200ea"]
        for usuario in casos:
            respuesta = cliente.post(
                "/api/cuentas/registro",
                json={"usuario": usuario, "contrasena": "contrasena1"},
            )
            self.assertEqual(respuesta.status_code, 422, repr(usuario))


class PruebaLimiteDeIntentos(unittest.TestCase):
    """Los intentos se cuentan y en algún momento se corta.

    Los límites se bajan a dos para no tener que fallar diez veces: amasar
    cada contraseña cuesta una décima de segundo a propósito.
    """

    def test_pasarse_de_fallos_al_entrar_da_429(self):
        cliente = cliente_nuevo(limite_entrar=(2, 900), limite_registro=(9, 3600))
        registrar(cliente, "ana", "contrasena1")
        for _ in range(2):
            fallo = cliente.post(
                "/api/cuentas/entrar",
                json={"usuario": "ana", "contrasena": "equivocada1"},
            )
            self.assertEqual(fallo.status_code, 401)
        cortado = cliente.post(
            "/api/cuentas/entrar",
            json={"usuario": "ana", "contrasena": "equivocada1"},
        )
        self.assertEqual(cortado.status_code, 429)
        self.assertIn("Demasiados intentos", cortado.json()["detail"])
        # Y con la contraseña buena tampoco pasa: el corte va antes de mirarla.
        self.assertEqual(
            cliente.post(
                "/api/cuentas/entrar",
                json={"usuario": "ana", "contrasena": "contrasena1"},
            ).status_code,
            429,
        )

    def test_pasarse_de_registros_da_429(self):
        cliente = cliente_nuevo(limite_registro=(1, 3600))
        registrar(cliente, "ana", "contrasena1")
        cortado = cliente.post(
            "/api/cuentas/registro",
            json={"usuario": "bea", "contrasena": "contrasena2"},
        )
        self.assertEqual(cortado.status_code, 429)
        self.assertIn("Demasiados intentos", cortado.json()["detail"])


class PruebaCodigoDeInvitacion(unittest.TestCase):
    """Con código puesto, el registro deja de estar abierto a cualquiera."""

    def test_sin_codigo_da_403(self):
        cliente = cliente_nuevo(codigo_registro="abrete-sesamo")
        respuesta = cliente.post(
            "/api/cuentas/registro",
            json={"usuario": "ana", "contrasena": "contrasena1"},
        )
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("código de invitación", respuesta.json()["detail"])

    def test_codigo_equivocado_da_403(self):
        cliente = cliente_nuevo(codigo_registro="abrete-sesamo")
        respuesta = cliente.post(
            "/api/cuentas/registro",
            json={"usuario": "ana", "contrasena": "contrasena1", "codigo": "otro"},
        )
        self.assertEqual(respuesta.status_code, 403)

    def test_con_el_codigo_bueno_se_registra(self):
        cliente = cliente_nuevo(codigo_registro="abrete-sesamo")
        self.assertTrue(registrar(cliente, "ana", "contrasena1", "abrete-sesamo"))

    def test_sin_codigo_configurado_el_registro_sigue_abierto(self):
        cliente = cliente_nuevo()
        self.assertTrue(registrar(cliente, "ana", "contrasena1"))


class PruebaCambioDeContrasena(unittest.TestCase):
    """Cambiar la contraseña tira todas las fichas de antes."""

    def setUp(self):
        self.cliente = cliente_nuevo()
        self.token_viejo = registrar(self.cliente, "ana", "contrasena1")
        self.cabeceras = {"Authorization": f"Bearer {self.token_viejo}"}

    def test_cambio_bueno_da_ficha_nueva_y_tira_la_vieja(self):
        respuesta = self.cliente.post(
            "/api/cuentas/contrasena",
            headers=self.cabeceras,
            json={"contrasena_actual": "contrasena1", "contrasena_nueva": "contrasena2"},
        )
        self.assertEqual(respuesta.status_code, 200)
        token_nuevo = respuesta.json()["token"]
        self.assertNotEqual(token_nuevo, self.token_viejo)

        # La ficha de antes ya no abre nada.
        vieja = self.cliente.get("/api/libro", headers=self.cabeceras)
        self.assertEqual(vieja.status_code, 401)
        # La nueva sí.
        nueva = self.cliente.get(
            "/api/libro", headers={"Authorization": f"Bearer {token_nuevo}"}
        )
        self.assertEqual(nueva.status_code, 200)
        # Y se entra con la contraseña nueva.
        entrada = self.cliente.post(
            "/api/cuentas/entrar",
            json={"usuario": "ana", "contrasena": "contrasena2"},
        )
        self.assertEqual(entrada.status_code, 200)

    def test_contrasena_actual_equivocada_da_403(self):
        respuesta = self.cliente.post(
            "/api/cuentas/contrasena",
            headers=self.cabeceras,
            json={"contrasena_actual": "equivocada1", "contrasena_nueva": "contrasena2"},
        )
        self.assertEqual(respuesta.status_code, 403)
        # Y la ficha de antes sigue valiendo: no se ha cambiado nada.
        self.assertEqual(
            self.cliente.get("/api/libro", headers=self.cabeceras).status_code, 200
        )

    def test_contrasena_nueva_corta_da_422(self):
        respuesta = self.cliente.post(
            "/api/cuentas/contrasena",
            headers=self.cabeceras,
            json={"contrasena_actual": "contrasena1", "contrasena_nueva": "corta"},
        )
        self.assertEqual(respuesta.status_code, 422)

    def test_sin_ficha_da_401(self):
        respuesta = self.cliente.post(
            "/api/cuentas/contrasena",
            json={"contrasena_actual": "contrasena1", "contrasena_nueva": "contrasena2"},
        )
        self.assertEqual(respuesta.status_code, 401)


class PruebaFichas(unittest.TestCase):
    def test_sin_ficha_da_401(self):
        respuesta = cliente_nuevo().get("/api/libro")
        self.assertEqual(respuesta.status_code, 401)

    def test_ficha_inventada_da_401(self):
        respuesta = cliente_nuevo().get(
            "/api/libro", headers={"Authorization": "Bearer 1.999.abcdef"}
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_ficha_manipulada_da_401(self):
        cliente = cliente_nuevo()
        token = registrar(cliente)
        # Cambiamos el id de usuario dejando la firma como estaba.
        partes = token.split(".")
        manipulado = f"999.{partes[1]}.{partes[2]}.{partes[3]}"
        respuesta = cliente.get(
            "/api/libro", headers={"Authorization": f"Bearer {manipulado}"}
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_ficha_caducada_da_401(self):
        cliente = cliente_nuevo()
        registrar(cliente)
        # Fabricamos una ficha con el secreto bueno pero ya caducada: la
        # firma cuadra, pero la fecha no.
        expira_pasado = 1000  # año 1970
        firma = seguridad._firma(SECRETO_DE_PRUEBA, 1, 0, expira_pasado)
        caducada = f"1.0.{expira_pasado}.{firma}"
        respuesta = cliente.get(
            "/api/libro", headers={"Authorization": f"Bearer {caducada}"}
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_ficha_de_otro_servidor_da_401(self):
        # Firmada con otro secreto: mismo formato, firma que no cuadra.
        ajena = seguridad.crear_ficha(b"otro-secreto", 1, 0)
        cliente = cliente_nuevo()
        registrar(cliente)
        respuesta = cliente.get(
            "/api/libro", headers={"Authorization": f"Bearer {ajena}"}
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_ficha_del_formato_antiguo_da_401(self):
        # Las de antes traían tres trozos y no llevaban generación. Ya no
        # valen: quien tenga una solo tiene que volver a entrar.
        cliente = cliente_nuevo()
        registrar(cliente)
        antigua = f"1.99999999999.{seguridad._firma(SECRETO_DE_PRUEBA, 1, 0, 99999999999)}"
        respuesta = cliente.get(
            "/api/libro", headers={"Authorization": f"Bearer {antigua}"}
        )
        self.assertEqual(respuesta.status_code, 401)


class PruebaFichasRotas(unittest.TestCase):
    """Una ficha viene de fuera y puede traer cualquier cosa dentro.

    Lo que no puede pasar nunca es que tumbe el servidor: todas las formas
    raras tienen que acabar en un 401 tranquilo, no en un 500.
    """

    def test_ficha_con_digito_raro_da_401_y_no_un_500(self):
        # `"²".isdigit()` dice que sí, pero `int("²")` revienta. Un servidor
        # que se fiara del isdigit se caía con esta ficha, y sin necesidad de
        # identificarse para nada.
        respuesta = cliente_nuevo().get(
            "/api/libro",
            headers={"Authorization": cabecera_cruda("Bearer ².1.99999999999.x")},
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_cabeceras_con_cualquier_forma_dan_401(self):
        cliente = cliente_nuevo()
        casos = [
            "Bearer ",
            "Bearer .",
            "Bearer 1",
            "Bearer 1.0.99999999999",            # le falta la firma
            "Bearer 1.0.99999999999.x.y",        # un trozo de más
            "Bearer ².².².²",
            "Bearer a.b.c.d",
            "Bearer -1.0.99999999999.x",
            "Bearer 1.0.99999999999.x",          # forma buena, firma inventada
            "Ficha 1.0.99999999999.x",           # ni siquiera dice Bearer
        ]
        for cabecera in casos:
            respuesta = cliente.get(
                "/api/libro", headers={"Authorization": cabecera_cruda(cabecera)}
            )
            self.assertEqual(respuesta.status_code, 401, cabecera)

    def test_validar_ficha_no_revienta_con_basura(self):
        # Lo mismo pero por dentro, donde sí se pueden meter caracteres que
        # una cabecera HTTP no admite: dígitos que no son ASCII.
        basura = [
            "",
            "....",
            "1.0.99999999999",
            "².1.99999999999.x",
            "１.0.99999999999.x",       # dígito ancho: isdecimal sí, ASCII no
            "1.٢.99999999999.x",        # dígito árabe
            "1.0.99999999999e5.x",
            "1.0. 99999999999.x",
            "1.0.99999999999.",
            "1.0." + "9" * 5000 + ".x",  # un número de miles de cifras
        ]
        for ficha in basura:
            self.assertIsNone(
                seguridad.validar_ficha(SECRETO_DE_PRUEBA, ficha), ficha
            )

    def test_una_ficha_buena_dice_quien_es_y_de_que_generacion(self):
        ficha = seguridad.crear_ficha(SECRETO_DE_PRUEBA, 7, 3)
        self.assertEqual(seguridad.validar_ficha(SECRETO_DE_PRUEBA, ficha), (7, 3))


class PruebaSecretoDelServidor(unittest.TestCase):
    """El secreto que firma las sesiones no puede ser de juguete."""

    def test_secreto_corto_no_deja_arrancar(self):
        with mock.patch.dict(os.environ, {"CONTAXCELL_SECRETO": "cuatro-letras"}):
            with self.assertRaises(RuntimeError) as fallo:
                seguridad.secreto_del_servidor()
        # El aviso dice cuánto hace falta y cómo generarlo.
        self.assertIn("32", str(fallo.exception))
        self.assertIn("openssl rand -hex 32", str(fallo.exception))

    def test_secreto_de_treinta_y_dos_vale(self):
        largo = "a" * seguridad.SECRETO_MINIMO
        with mock.patch.dict(os.environ, {"CONTAXCELL_SECRETO": largo}):
            secreto, generado = seguridad.secreto_del_servidor()
        self.assertEqual(secreto, largo.encode("utf-8"))
        self.assertFalse(generado)

    def test_sin_secreto_se_inventa_uno_y_lo_dice(self):
        with mock.patch.dict(os.environ, {"CONTAXCELL_SECRETO": ""}):
            secreto, generado = seguridad.secreto_del_servidor()
        self.assertEqual(len(secreto), 32)
        self.assertTrue(generado)


class PruebaLibro(unittest.TestCase):
    def setUp(self):
        self.cliente = cliente_nuevo()
        token = registrar(self.cliente)
        self.cabeceras = {"Authorization": f"Bearer {token}"}

    def test_sin_subir_nada_devuelve_revision_cero_y_libro_nulo(self):
        respuesta = self.cliente.get("/api/libro", headers=self.cabeceras)
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json(), {"revision": 0, "libro": None})

    def test_ida_y_vuelta(self):
        subida = self.cliente.put(
            "/api/libro",
            headers=self.cabeceras,
            json={"revision_base": 0, "libro": UN_LIBRO},
        )
        self.assertEqual(subida.status_code, 200)
        self.assertEqual(subida.json(), {"revision": 1})

        bajada = self.cliente.get("/api/libro", headers=self.cabeceras)
        self.assertEqual(bajada.status_code, 200)
        self.assertEqual(bajada.json(), {"revision": 1, "libro": UN_LIBRO})

    def test_subidas_sucesivas_suben_la_revision(self):
        self.cliente.put(
            "/api/libro", headers=self.cabeceras,
            json={"revision_base": 0, "libro": UN_LIBRO},
        )
        segunda = self.cliente.put(
            "/api/libro", headers=self.cabeceras,
            json={"revision_base": 1, "libro": OTRO_LIBRO},
        )
        self.assertEqual(segunda.status_code, 200)
        self.assertEqual(segunda.json(), {"revision": 2})

    def test_revision_desfasada_da_409_con_el_estado_del_servidor(self):
        self.cliente.put(
            "/api/libro", headers=self.cabeceras,
            json={"revision_base": 0, "libro": UN_LIBRO},
        )
        # Otro ordenador que aún cree que la revisión es 0 intenta subir.
        conflicto = self.cliente.put(
            "/api/libro", headers=self.cabeceras,
            json={"revision_base": 0, "libro": OTRO_LIBRO},
        )
        self.assertEqual(conflicto.status_code, 409)
        # El 409 trae lo que hay en el servidor, para que el cliente resuelva.
        self.assertEqual(conflicto.json(), {"revision": 1, "libro": UN_LIBRO})

    def test_cuerpo_incompleto_da_422(self):
        sin_libro = self.cliente.put(
            "/api/libro", headers=self.cabeceras, json={"revision_base": 0}
        )
        self.assertEqual(sin_libro.status_code, 422)
        sin_revision = self.cliente.put(
            "/api/libro", headers=self.cabeceras, json={"libro": UN_LIBRO}
        )
        self.assertEqual(sin_revision.status_code, 422)

    def test_cada_usuario_tiene_su_libro(self):
        token_bea = registrar(self.cliente, "bea", "contrasena2")
        cabeceras_bea = {"Authorization": f"Bearer {token_bea}"}
        self.cliente.put(
            "/api/libro", headers=self.cabeceras,
            json={"revision_base": 0, "libro": UN_LIBRO},
        )
        respuesta = self.cliente.get("/api/libro", headers=cabeceras_bea)
        self.assertEqual(respuesta.json(), {"revision": 0, "libro": None})


class PruebaLimitador(unittest.TestCase):
    """El contador de intentos, por dentro y con un reloj de mentira."""

    def setUp(self):
        self.ahora = 0.0
        self.limitador = limites.Limitador(2, 10, reloj=lambda: self.ahora)

    def test_bloquea_al_llegar_al_maximo(self):
        self.assertFalse(self.limitador.bloqueado("ana"))
        self.limitador.apunta("ana")
        self.assertFalse(self.limitador.bloqueado("ana"))
        self.limitador.apunta("ana")
        self.assertTrue(self.limitador.bloqueado("ana"))
        # Y a cada uno lo suyo: lo de ana no bloquea a bea.
        self.assertFalse(self.limitador.bloqueado("bea"))

    def test_pasada_la_ventana_se_desbloquea_solo(self):
        self.limitador.apunta("ana")
        self.limitador.apunta("ana")
        self.assertTrue(self.limitador.bloqueado("ana"))
        self.ahora += 11  # ha pasado la ventana entera
        self.assertFalse(self.limitador.bloqueado("ana"))

    def test_olvidar_borra_la_cuenta(self):
        self.limitador.apunta("ana")
        self.limitador.apunta("ana")
        self.limitador.olvida("ana")
        self.assertFalse(self.limitador.bloqueado("ana"))

    def test_no_se_queda_con_claves_caducadas(self):
        self.limitador.apunta("ana")
        self.ahora += 11
        self.limitador.apunta("bea")
        # Al apuntar se barren las claves que ya no tienen nada vigente: si no,
        # cada IP que pasara por aquí dejaría su hueco para siempre.
        self.assertEqual(list(self.limitador._intentos), ["bea"])


class PruebaBaseDeAntes(unittest.TestCase):
    """Una base de datos de una versión anterior tiene que seguir sirviendo.

    A la tabla de usuarios le falta la columna de la generación, y abrirla
    tiene que añadirla sin perder a nadie.
    """

    def test_se_le_anade_la_columna_que_falta(self):
        with tempfile.TemporaryDirectory() as carpeta:
            ruta = str(Path(carpeta) / "vieja.sqlite")
            vieja = sqlite3.connect(ruta)
            vieja.executescript("""
                CREATE TABLE usuarios (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL UNIQUE,
                    hash    TEXT NOT NULL,
                    sal     TEXT NOT NULL,
                    creado  TEXT NOT NULL DEFAULT (datetime('now'))
                );
                INSERT INTO usuarios (usuario, hash, sal)
                VALUES ('ana', 'un-hash', 'una-sal');
            """)
            vieja.commit()
            vieja.close()

            almacen = AlmacenSQLite(ruta)
            self.assertEqual(
                almacen.buscar_usuario("ana"), (1, "un-hash", "una-sal", 0)
            )
            self.assertEqual(almacen.generacion_de(1), 0)
            # Y abrirla otra vez no se atraganca al ver que la columna ya está.
            otra_vez = AlmacenSQLite(ruta)
            self.assertEqual(otra_vez.generacion_de(1), 0)
            # La del último uso también llega, vacía: nadie la ha usado aún.
            otra_vez.apuntar_uso(1)
            self.assertIsNotNone(otra_vez.resumen_usuarios()[0]["ultimo_uso"])
            # Cerramos a mano, que el archivo está en una carpeta de usar y
            # tirar y en Windows no se borra con la base abierta.
            almacen._conexion.close()
            otra_vez._conexion.close()


class PruebaQuienLoUsa(unittest.TestCase):
    """El `./usuarios` del administrador: quién tiene cuenta y quién la usa."""

    def setUp(self):
        self.almacen = AlmacenSQLite()
        self.cliente = TestClient(crear_aplicacion(
            almacen=self.almacen, secreto=SECRETO_DE_PRUEBA, cliente_precios=None,
        ))

    def resumen(self, usuario: str) -> dict:
        return next(f for f in self.almacen.resumen_usuarios() if f["usuario"] == usuario)

    def poner_ultimo_uso(self, usuario: str, hace: str) -> None:
        self.almacen._conexion.execute(
            "UPDATE usuarios SET ultimo_uso = datetime('now', ?) WHERE usuario = ?",
            (hace, usuario),
        )
        self.almacen._conexion.commit()

    def test_registrarse_no_es_usarlo_pero_sincronizar_si(self):
        token = registrar(self.cliente, "ana")
        self.assertIsNone(self.resumen("ana")["ultimo_uso"])
        self.cliente.get("/api/libro", headers={"Authorization": f"Bearer {token}"})
        self.assertIsNotNone(self.resumen("ana")["ultimo_uso"])

    def test_entrar_con_contrasena_cuenta_como_uso(self):
        registrar(self.cliente, "ana", "contrasena1")
        self.cliente.post("/api/cuentas/entrar",
                          json={"usuario": "ana", "contrasena": "contrasena1"})
        self.assertIsNotNone(self.resumen("ana")["ultimo_uso"])

    def test_no_escribe_en_cada_peticion(self):
        token = registrar(self.cliente, "ana")
        cabeceras = {"Authorization": f"Bearer {token}"}
        # Hace un minuto: todavía vale, no se toca.
        self.poner_ultimo_uso("ana", "-1 minutes")
        antes = self.resumen("ana")["ultimo_uso"]
        self.cliente.get("/api/libro", headers=cabeceras)
        self.assertEqual(self.resumen("ana")["ultimo_uso"], antes)
        # Hace una hora: ya toca apuntarlo otra vez.
        self.poner_ultimo_uso("ana", "-60 minutes")
        antes = self.resumen("ana")["ultimo_uso"]
        self.cliente.get("/api/libro", headers=cabeceras)
        self.assertGreater(self.resumen("ana")["ultimo_uso"], antes)

    def test_cuenta_las_subidas_y_el_tamano_pero_no_ensena_el_libro(self):
        token = registrar(self.cliente, "ana")
        registrar(self.cliente, "bea")
        cabeceras = {"Authorization": f"Bearer {token}"}
        for base in (0, 1, 2):
            self.cliente.put("/api/libro", headers=cabeceras,
                             json={"revision_base": base, "libro": UN_LIBRO})
        ana = self.resumen("ana")
        self.assertEqual(ana["subidas"], 3)
        self.assertGreater(ana["tamano"], 0)
        self.assertEqual(set(ana), {"usuario", "creado", "ultimo_uso", "subidas", "tamano", "vetado"})
        # Quien nunca subió nada sale igual, con ceros.
        self.assertEqual((self.resumen("bea")["subidas"], self.resumen("bea")["tamano"]), (0, 0))

    def test_los_que_lo_usan_salen_primero(self):
        for nombre in ("ana", "bea", "carlos"):
            registrar(self.cliente, nombre)
        self.poner_ultimo_uso("ana", "-3 days")
        self.poner_ultimo_uso("carlos", "-1 hours")
        orden = [f["usuario"] for f in self.almacen.resumen_usuarios()]
        self.assertEqual(orden, ["carlos", "ana", "bea"])


class PruebaVeto(unittest.TestCase):
    """`./usuarios vetar`: fuera de la cuenta al momento, sin perder nada."""

    def setUp(self):
        self.almacen = AlmacenSQLite()
        self.cliente = TestClient(crear_aplicacion(
            almacen=self.almacen, secreto=SECRETO_DE_PRUEBA, cliente_precios=None,
        ))
        self.token = registrar(self.cliente, "ana", "contrasena1")
        self.cabeceras = {"Authorization": f"Bearer {self.token}"}
        self.cliente.put("/api/libro", headers=self.cabeceras,
                         json={"revision_base": 0, "libro": UN_LIBRO})

    def entrar(self, contrasena="contrasena1"):
        return self.cliente.post("/api/cuentas/entrar",
                                 json={"usuario": "ana", "contrasena": contrasena})

    def test_la_sesion_abierta_deja_de_valer_al_momento(self):
        self.assertTrue(self.almacen.vetar("ana", True))
        for respuesta in (self.cliente.get("/api/libro", headers=self.cabeceras),
                          self.cliente.put("/api/libro", headers=self.cabeceras,
                                           json={"revision_base": 1, "libro": OTRO_LIBRO})):
            self.assertEqual(respuesta.status_code, 401)
            self.assertIn("bloqueada", respuesta.json()["detail"])

    def test_al_entrar_se_le_dice_por_que(self):
        self.almacen.vetar("ana", True)
        respuesta = self.entrar()
        self.assertEqual(respuesta.status_code, 403)
        self.assertIn("bloqueada", respuesta.json()["detail"])

    def test_con_la_contrasena_mala_no_se_chiva_del_veto(self):
        self.almacen.vetar("ana", True)
        respuesta = self.entrar("equivocada1")
        self.assertEqual(respuesta.status_code, 401)
        self.assertNotIn("bloqueada", respuesta.json()["detail"])

    def test_readmitido_vuelve_con_su_libro_intacto(self):
        self.almacen.vetar("ana", True)
        self.almacen.vetar("ana", False)
        respuesta = self.entrar()
        self.assertEqual(respuesta.status_code, 200)
        token = respuesta.json()["token"]
        libro = self.cliente.get("/api/libro", headers={"Authorization": f"Bearer {token}"}).json()
        self.assertEqual(libro, {"revision": 1, "libro": UN_LIBRO})

    def test_los_demas_siguen_igual(self):
        token_bea = registrar(self.cliente, "bea")
        self.almacen.vetar("ana", True)
        respuesta = self.cliente.get("/api/libro", headers={"Authorization": f"Bearer {token_bea}"})
        self.assertEqual(respuesta.status_code, 200)

    def test_vetar_a_quien_no_existe_lo_dice(self):
        self.assertFalse(self.almacen.vetar("nadie", True))

    def test_vetar_dos_veces_guarda_la_primera_fecha(self):
        self.almacen.vetar("ana", True)
        primera = self.almacen.resumen_usuarios()[0]["vetado"]
        self.almacen._conexion.execute("UPDATE usuarios SET vetado = '2026-01-01 10:00:00'")
        self.almacen._conexion.commit()
        self.almacen.vetar("ana", True)
        self.assertNotEqual(self.almacen.resumen_usuarios()[0]["vetado"], primera)
        self.assertEqual(self.almacen.resumen_usuarios()[0]["vetado"].year, 2026)
        self.assertEqual(self.almacen.resumen_usuarios()[0]["vetado"].month, 1)

    def test_la_orden_de_la_terminal(self):
        from contaserver.usuarios import ejecutar
        ahora = datetime.now(timezone.utc)
        codigo, texto = ejecutar(self.almacen, ["vetar", "  Ana "], ahora)
        self.assertEqual(codigo, 0)
        self.assertIn("«ana» queda vetado", texto)
        self.assertEqual(self.entrar().status_code, 403)
        codigo, texto = ejecutar(self.almacen, [], ahora)
        self.assertIn("ana  (VETADO)", texto)
        self.assertIn("· 1 vetado", texto)
        codigo, texto = ejecutar(self.almacen, ["readmitir", "ana"], ahora)
        self.assertEqual(codigo, 0)
        self.assertEqual(self.entrar().status_code, 200)
        self.assertEqual(ejecutar(self.almacen, ["vetar", "nadie"], ahora)[0], 1)
        self.assertEqual(ejecutar(self.almacen, ["borrar", "ana"], ahora)[0], 2)
        self.assertEqual(ejecutar(self.almacen, ["vetar"], ahora)[0], 2)


class PruebaInformeDeUsuarios(unittest.TestCase):
    """Lo que se lee en la terminal. La hora es de España."""

    # Mediodía en España (10:00 UTC en octubre, horario de verano).
    AHORA = datetime(2026, 10, 5, 10, 0, tzinfo=timezone.utc)

    def fila(self, usuario, ultimo_uso=None, subidas=0, tamano=0):
        return {"usuario": usuario, "creado": datetime(2026, 10, 1, tzinfo=timezone.utc),
                "ultimo_uso": ultimo_uso, "subidas": subidas, "tamano": tamano}

    def test_cuando(self):
        from contaserver.usuarios import cuando
        self.assertEqual(cuando(None, self.AHORA), "nunca")
        self.assertEqual(cuando(datetime(2026, 10, 5, 7, 41, tzinfo=timezone.utc), self.AHORA), "hoy 09:41")
        self.assertEqual(cuando(datetime(2026, 10, 4, 20, 10, tzinfo=timezone.utc), self.AHORA), "ayer 22:10")
        self.assertEqual(cuando(datetime(2026, 10, 2, 9, 0, tzinfo=timezone.utc), self.AHORA), "hace 3 días")
        self.assertEqual(cuando(datetime(2026, 5, 2, 9, 0, tzinfo=timezone.utc), self.AHORA), "2026-05-02")
        # Las 23:30 UTC del día 4 ya son el día 5 en España: es «hoy».
        self.assertEqual(cuando(datetime(2026, 10, 4, 23, 30, tzinfo=timezone.utc), self.AHORA), "hoy 01:30")

    def test_tamano(self):
        from contaserver.usuarios import tamano
        self.assertEqual(tamano(0), "—")
        self.assertEqual(tamano(512), "512 B")
        self.assertEqual(tamano(48 * 1024), "48 KB")
        self.assertEqual(tamano(int(1.5 * 1024 * 1024)), "1,5 MB")

    def test_cuenta_los_registrados_y_los_activos(self):
        from contaserver.usuarios import informe
        texto = informe([
            self.fila("ana", self.AHORA - timedelta(hours=2), 152, 48 * 1024),
            self.fila("bea", self.AHORA - timedelta(days=20), 3, 900),
            self.fila("carlos"),
        ], self.AHORA)
        self.assertTrue(texto.startswith(
            "3 usuarios registrados · 1 activo en los últimos 7 días"))
        self.assertIn("ÚLTIMO USO", texto)
        self.assertIn("nunca", texto)
        self.assertIn("152", texto)

    def test_uno_solo_va_en_singular(self):
        from contaserver.usuarios import informe
        texto = informe([self.fila("ana", self.AHORA)], self.AHORA)
        self.assertTrue(texto.startswith("1 usuario registrado · 1 activo"))

    def test_sin_nadie(self):
        from contaserver.usuarios import informe
        self.assertEqual(informe([], self.AHORA), "Todavía no hay nadie registrado.")


class PruebaAtomicidad(unittest.TestCase):
    """Dos subidas a la vez con la misma revisión de partida: exactamente una
    tiene que ganar. Es la garantía que impide perder datos en silencio."""

    def test_dos_subidas_simultaneas_solo_gana_una(self):
        cliente = cliente_nuevo()
        token = registrar(cliente)
        cabeceras = {"Authorization": f"Bearer {token}"}
        cliente.put(
            "/api/libro", headers=cabeceras,
            json={"revision_base": 0, "libro": UN_LIBRO},
        )

        # Dos hilos empujan a la vez partiendo los dos de la revisión 1.
        barrera = threading.Barrier(2)
        resultados: list[int] = []
        candado = threading.Lock()

        def empujar(libro: dict) -> None:
            barrera.wait()  # que salgan a la vez de verdad
            respuesta = cliente.put(
                "/api/libro", headers=cabeceras,
                json={"revision_base": 1, "libro": libro},
            )
            with candado:
                resultados.append(respuesta.status_code)

        hilos = [
            threading.Thread(target=empujar, args=({"quien": "primero"},)),
            threading.Thread(target=empujar, args=({"quien": "segundo"},)),
        ]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join()

        # Una gana (200) y la otra se lleva el conflicto (409). Nunca dos 200.
        self.assertEqual(sorted(resultados), [200, 409])

        # Y el servidor quedó en la revisión 2, con el libro de la que ganó.
        final = cliente.get("/api/libro", headers=cabeceras).json()
        self.assertEqual(final["revision"], 2)
        self.assertIn(final["libro"], [{"quien": "primero"}, {"quien": "segundo"}])


if __name__ == "__main__":
    unittest.main()
