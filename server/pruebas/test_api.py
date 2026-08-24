"""Pruebas de la API completa, sin red y sin Docker.

Se monta la aplicación con un almacén SQLite en memoria y se le habla con el
TestClient de FastAPI, que hace las peticiones por dentro sin abrir puertos.
Cada prueba arranca con un servidor recién hecho y vacío.
"""

from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path

# Para poder correr las pruebas desde server/ sin instalar el paquete.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from contaserver import seguridad
from contaserver.almacen import AlmacenSQLite
from contaserver.aplicacion import crear_aplicacion

SECRETO_DE_PRUEBA = b"secreto-solo-para-las-pruebas"


def cliente_nuevo() -> TestClient:
    """Un servidor recién levantado, con la base vacía."""
    app = crear_aplicacion(almacen=AlmacenSQLite(), secreto=SECRETO_DE_PRUEBA)
    return TestClient(app)


def registrar(cliente: TestClient, usuario: str = "ana", contrasena: str = "contrasena1") -> str:
    """Registra y devuelve el token, dando por buena la respuesta."""
    respuesta = cliente.post(
        "/api/cuentas/registro",
        json={"usuario": usuario, "contrasena": contrasena},
    )
    assert respuesta.status_code == 201, respuesta.text
    return respuesta.json()["token"]


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
        manipulado = f"999.{partes[1]}.{partes[2]}"
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
        firma = seguridad._firma(SECRETO_DE_PRUEBA, 1, expira_pasado)
        caducada = f"1.{expira_pasado}.{firma}"
        respuesta = cliente.get(
            "/api/libro", headers={"Authorization": f"Bearer {caducada}"}
        )
        self.assertEqual(respuesta.status_code, 401)

    def test_ficha_de_otro_servidor_da_401(self):
        # Firmada con otro secreto: mismo formato, firma que no cuadra.
        ajena = seguridad.crear_ficha(b"otro-secreto", 1)
        cliente = cliente_nuevo()
        registrar(cliente)
        respuesta = cliente.get(
            "/api/libro", headers={"Authorization": f"Bearer {ajena}"}
        )
        self.assertEqual(respuesta.status_code, 401)


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
