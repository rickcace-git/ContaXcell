"""Pruebas del cliente de sincronización, sin red y sin ventana.

En vez del `urlopen` de verdad se enchufa un servidor de mentira: una lista
de respuestas preparadas que además apunta qué peticiones le llegan. Así se
puede comprobar lo que importa: qué se manda, qué se guarda en la sesión y
qué pasa cuando el servidor contesta mal o no contesta.
"""

from __future__ import annotations

import io
import json
import os
import stat
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from contaxcell import sincronia as modulo  # noqa: E402
from contaxcell.sincronia import (ErrorDeSincronia, FaltaCodigo,  # noqa: E402
                                  Sincronia)


# --- el servidor de mentira --------------------------------------------------

class RespuestaFalsa:
    """Lo justo para pasar por lo que devuelve `urlopen`."""

    def __init__(self, codigo: int, cuerpo):
        self.status = codigo
        self._cuerpo = json.dumps(cuerpo).encode("utf-8")

    def read(self) -> bytes:
        return self._cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class ServidorFalso:
    """Se le dan las respuestas por adelantado y apunta las peticiones.

    Cada respuesta es (codigo, cuerpo). Un código de error se lanza como
    HTTPError, igual que haría urllib; la cadena "sin-conexion" hace de
    cable desenchufado.
    """

    def __init__(self, *respuestas):
        self.respuestas = list(respuestas)
        self.peticiones: list[dict] = []

    def __call__(self, peticion, timeout=None):
        self.peticiones.append({
            "metodo": peticion.get_method(),
            "url": peticion.full_url,
            "cuerpo": json.loads(peticion.data.decode("utf-8")) if peticion.data else None,
            "cabeceras": dict(peticion.header_items()),
            "espera": timeout,
        })
        if not self.respuestas:
            raise AssertionError("petición de más: " + peticion.full_url)
        codigo, cuerpo = self.respuestas.pop(0)
        if codigo == "sin-conexion":
            raise urllib.error.URLError("cable desenchufado")
        if codigo >= 400:
            raise urllib.error.HTTPError(
                peticion.full_url, codigo, "error", {},
                io.BytesIO(json.dumps(cuerpo).encode("utf-8")))
        return RespuestaFalsa(codigo, cuerpo)


class ConCarpeta(unittest.TestCase):
    def setUp(self):
        self._temporal = tempfile.TemporaryDirectory(prefix="contaxcell-sincronia-")
        self.carpeta = Path(self._temporal.name)
        self.addCleanup(self._temporal.cleanup)

    def nueva(self, *respuestas) -> tuple[Sincronia, ServidorFalso]:
        servidor = ServidorFalso(*respuestas)
        return Sincronia(self.carpeta, abrir_url=servidor), servidor

    def con_sesion(self, *respuestas, revision=1, pendiente=False) -> tuple[Sincronia, ServidorFalso]:
        (self.carpeta).mkdir(parents=True, exist_ok=True)
        (self.carpeta / modulo.ARCHIVO_SESION).write_text(json.dumps({
            "servidor": "http://servidor:8000", "usuario": "pablo",
            "token": "t0ken", "ultima_revision": revision, "pendiente": pendiente,
        }), encoding="utf-8")
        return self.nueva(*respuestas)

    def escribir_datos(self, contenido=None) -> None:
        (self.carpeta / "datos.json").write_text(
            json.dumps(contenido or {"version": 1, "movimientos": []}),
            encoding="utf-8")

    def sesion_grabada(self) -> dict:
        return json.loads((self.carpeta / modulo.ARCHIVO_SESION).read_text(encoding="utf-8"))

    def avisos_de(self, sincronia) -> list[tuple]:
        avisos = []
        while not sincronia.avisos.empty():
            avisos.append(sincronia.avisos.get_nowait())
        return avisos


# --- entrar y registrarse ----------------------------------------------------

class PruebaEntrar(ConCarpeta):
    def test_entrar_guarda_la_sesion(self):
        sinc, servidor = self.nueva((200, {"token": "abc", "usuario": "pablo"}))
        sinc.entrar("pablo", "secreta", "http://servidor:8000/")

        self.assertTrue(sinc.hay_sesion())
        grabada = self.sesion_grabada()
        self.assertEqual(grabada["token"], "abc")
        self.assertEqual(grabada["usuario"], "pablo")
        self.assertEqual(grabada["servidor"], "http://servidor:8000")
        peticion = servidor.peticiones[0]
        self.assertEqual(peticion["url"], "http://servidor:8000/api/cuentas/entrar")
        self.assertEqual(peticion["cuerpo"], {"usuario": "pablo", "contrasena": "secreta"})

    def test_contrasena_mala_no_deja_sesion(self):
        sinc, _ = self.nueva((401, {"detail": "credenciales malas"}))
        with self.assertRaises(ErrorDeSincronia):
            sinc.entrar("pablo", "mala")
        self.assertFalse(sinc.hay_sesion())

    def test_usuario_cogido_al_registrar(self):
        sinc, _ = self.nueva((409, {}))
        with self.assertRaises(ErrorDeSincronia) as contexto:
            sinc.registrar("pablo", "secreta")
        self.assertIn("cogido", str(contexto.exception))

    def test_sin_conexion_al_entrar_avisa_con_palabras(self):
        sinc, _ = self.nueva(("sin-conexion", None))
        with self.assertRaises(ErrorDeSincronia):
            sinc.entrar("pablo", "secreta")

    def test_entrar_con_otro_usuario_aparta_los_datos(self):
        self.escribir_datos({"version": 1, "movimientos": [{"fecha": "2026-01-05"}]})
        sinc, _ = self.con_sesion((200, {"token": "nuevo", "usuario": "maria"}),
                                  revision=7, pendiente=True)
        sinc.entrar("maria", "secreta")

        # Los datos del usuario anterior están a salvo en copias…
        copias = list((self.carpeta / "copias").glob("*-cambio-de-usuario.json"))
        self.assertEqual(len(copias), 1)
        self.assertIn("2026-01-05", copias[0].read_text(encoding="utf-8"))
        # …y el archivo local desaparece para empezar de cero.
        self.assertFalse((self.carpeta / "datos.json").exists())
        grabada = self.sesion_grabada()
        self.assertEqual(grabada["usuario"], "maria")
        self.assertEqual(grabada["ultima_revision"], 0)
        self.assertFalse(grabada["pendiente"])

    def test_entrar_con_el_mismo_usuario_no_toca_nada(self):
        self.escribir_datos()
        sinc, _ = self.con_sesion((200, {"token": "renovado", "usuario": "pablo"}),
                                  revision=7, pendiente=True)
        sinc.entrar("pablo", "secreta")

        self.assertTrue((self.carpeta / "datos.json").exists())
        grabada = self.sesion_grabada()
        self.assertEqual(grabada["ultima_revision"], 7)
        self.assertTrue(grabada["pendiente"])

    def test_el_mismo_usuario_escrito_con_mayusculas_sigue_siendo_el_mismo(self):
        """El servidor deja el nombre en minúsculas y devuelve el bueno. Si se
        mirara lo tecleado, entrar como «Pablo» apartaría la contabilidad de
        «pablo» como si fuera de otra cuenta."""
        self.escribir_datos()
        sinc, _ = self.con_sesion((200, {"token": "renovado", "usuario": "pablo"}),
                                  revision=7, pendiente=True)
        sinc.entrar("Pablo", "secreta")

        self.assertTrue((self.carpeta / "datos.json").exists())
        self.assertEqual(list((self.carpeta / "copias").glob("*-cambio-de-usuario.json")),
                         [])
        grabada = self.sesion_grabada()
        self.assertEqual(grabada["usuario"], "pablo")
        self.assertEqual(grabada["ultima_revision"], 7)
        self.assertTrue(grabada["pendiente"])

    def test_salir_olvida_la_sesion(self):
        sinc, _ = self.con_sesion()
        sinc.salir()
        self.assertFalse(sinc.hay_sesion())
        self.assertFalse((self.carpeta / modulo.ARCHIVO_SESION).exists())

    def test_demasiados_intentos_lo_dice_con_palabras(self):
        sinc, _ = self.nueva((429, {"detail": "rate limited"}))
        with self.assertRaises(ErrorDeSincronia) as contexto:
            sinc.entrar("pablo", "secreta")
        self.assertEqual(str(contexto.exception), modulo.MENSAJE_DEMASIADOS_INTENTOS)
        self.assertFalse(sinc.hay_sesion())

    @unittest.skipIf(os.name == "nt", "los permisos de archivo son cosa de Unix")
    def test_la_sesion_solo_la_lee_su_dueno(self):
        # Dentro va el token: si lo lee cualquiera que entre en el ordenador,
        # tiene la cuenta entera sin saber la contraseña.
        sinc, _ = self.nueva((200, {"token": "abc", "usuario": "pablo"}))
        sinc.entrar("pablo", "secreta")
        modo = stat.S_IMODE((self.carpeta / modulo.ARCHIVO_SESION).stat().st_mode)
        self.assertEqual(modo, 0o600)


class PruebaCodigoDeInvitacion(ConCarpeta):
    """Hay servidores que solo dejan crear cuentas con invitación."""

    def test_el_codigo_va_en_el_cuerpo_cuando_se_pone(self):
        sinc, servidor = self.nueva((201, {"token": "abc", "usuario": "pablo"}))
        sinc.registrar("pablo", "secreta", "http://servidor:8000", "ABC-123")
        self.assertEqual(servidor.peticiones[0]["cuerpo"],
                         {"usuario": "pablo", "contrasena": "secreta",
                          "codigo": "ABC-123"})

    def test_sin_codigo_no_se_manda_el_campo(self):
        sinc, servidor = self.nueva((201, {"token": "abc", "usuario": "pablo"}))
        sinc.registrar("pablo", "secreta")
        self.assertNotIn("codigo", servidor.peticiones[0]["cuerpo"])

    def test_el_servidor_que_pide_invitacion_se_distingue(self):
        sinc, _ = self.nueva((403, {"detail": "Hace falta un código de invitación."}))
        with self.assertRaises(FaltaCodigo) as contexto:
            sinc.registrar("pablo", "secreta")
        # La ventana de acceso lo caza aparte para enseñar el campo, pero para
        # todo lo demás es un error como los otros.
        self.assertIsInstance(contexto.exception, ErrorDeSincronia)
        self.assertIn("código de invitación", str(contexto.exception))
        self.assertFalse(sinc.hay_sesion())


class PruebaCambiarContrasena(ConCarpeta):
    def test_el_token_nuevo_reemplaza_al_de_antes(self):
        sinc, servidor = self.con_sesion((200, {"token": "recien-hecho"}))
        sinc.cambiar_contrasena("la-de-antes", "la-nueva-larga")

        peticion = servidor.peticiones[0]
        self.assertEqual(peticion["url"],
                         "http://servidor:8000/api/cuentas/contrasena")
        self.assertEqual(peticion["cuerpo"], {"contrasena_actual": "la-de-antes",
                                              "contrasena_nueva": "la-nueva-larga"})
        self.assertEqual(peticion["cabeceras"].get("Authorization"), "Bearer t0ken")
        # Y queda grabado: al abrir mañana se sigue dentro con el token nuevo.
        self.assertEqual(self.sesion_grabada()["token"], "recien-hecho")

    def test_la_contrasena_de_ahora_mal_puesta(self):
        sinc, _ = self.con_sesion((403, {}))
        with self.assertRaises(ErrorDeSincronia) as contexto:
            sinc.cambiar_contrasena("la-que-no-es", "la-nueva-larga")
        self.assertEqual(str(contexto.exception),
                         "La contraseña actual no es correcta.")
        self.assertEqual(self.sesion_grabada()["token"], "t0ken")

    def test_sin_cuenta_no_hay_contrasena_que_cambiar(self):
        sinc, _ = self.nueva()
        with self.assertRaises(ErrorDeSincronia):
            sinc.cambiar_contrasena("la-de-antes", "la-nueva-larga")

    def test_la_nueva_que_no_le_gusta_al_servidor(self):
        sinc, _ = self.con_sesion((422, {"detail": "La contraseña es muy corta."}))
        with self.assertRaises(ErrorDeSincronia) as contexto:
            sinc.cambiar_contrasena("la-de-antes", "corta")
        self.assertIn("muy corta", str(contexto.exception))

    def test_la_sesion_caducada_a_mitad(self):
        sinc, _ = self.con_sesion((401, {}))
        with self.assertRaises(ErrorDeSincronia):
            sinc.cambiar_contrasena("la-de-antes", "la-nueva-larga")
        self.assertTrue(sinc.caducada)

    def test_sin_conexion_no_se_puede_cambiar(self):
        sinc, _ = self.con_sesion(("sin-conexion", None))
        with self.assertRaises(ErrorDeSincronia) as contexto:
            sinc.cambiar_contrasena("la-de-antes", "la-nueva-larga")
        self.assertIn("servidor", str(contexto.exception))


# --- subir cambios -------------------------------------------------------------

class PruebaEmpujar(ConCarpeta):
    def test_marcar_pendiente_queda_grabado(self):
        sinc, _ = self.con_sesion()
        sinc.marcar_pendiente()
        # Lo importante: aunque se cierre la aplicación ahora mismo, el
        # pendiente está en el disco y se subirá en el próximo arranque.
        self.assertTrue(self.sesion_grabada()["pendiente"])

    def test_subida_con_exito(self):
        self.escribir_datos()
        sinc, servidor = self.con_sesion((200, {"revision": 4}), revision=3)
        sinc.marcar_pendiente()

        self.assertTrue(sinc.empujar())
        peticion = servidor.peticiones[0]
        self.assertEqual(peticion["metodo"], "PUT")
        self.assertEqual(peticion["cuerpo"]["revision_base"], 3)
        self.assertEqual(peticion["cabeceras"].get("Authorization"), "Bearer t0ken")
        grabada = self.sesion_grabada()
        self.assertFalse(grabada["pendiente"])
        self.assertEqual(grabada["ultima_revision"], 4)
        self.assertIn(("estado", "Sincronizado.", "bien"), self.avisos_de(sinc))

    def test_sin_conexion_conserva_el_pendiente(self):
        self.escribir_datos()
        sinc, _ = self.con_sesion(("sin-conexion", None))
        sinc.marcar_pendiente()

        self.assertFalse(sinc.empujar())
        self.assertTrue(self.sesion_grabada()["pendiente"])
        avisos = self.avisos_de(sinc)
        self.assertEqual(avisos, [("estado", modulo.MENSAJE_SIN_CONEXION, "")])

    def test_reintento_tras_volver_la_conexion(self):
        self.escribir_datos()
        sinc, servidor = self.con_sesion(("sin-conexion", None), (200, {"revision": 2}),
                                         revision=1)
        sinc.marcar_pendiente()
        self.assertFalse(sinc.empujar())
        self.assertTrue(sinc.empujar())  # el bucle de fondo haría esto a los 30 s
        self.assertEqual(len(servidor.peticiones), 2)
        self.assertFalse(self.sesion_grabada()["pendiente"])

    def test_conflicto_guarda_copia_y_gana_lo_local(self):
        self.escribir_datos({"version": 1, "ajustes": {"saldo_inicial": 100}})
        del_servidor = {"version": 1, "ajustes": {"saldo_inicial": 999}}
        sinc, servidor = self.con_sesion(
            (409, {"revision": 7, "libro": del_servidor}),
            (200, {"revision": 8}),
            revision=3)
        sinc.marcar_pendiente()

        self.assertTrue(sinc.empujar())
        # La versión del servidor queda a salvo en una copia fechada…
        copias = list((self.carpeta / "copias").glob("*-conflicto-sincronia.json"))
        self.assertEqual(len(copias), 1)
        self.assertIn("999", copias[0].read_text(encoding="utf-8"))
        # …y se vuelve a subir lo local sobre la revisión que dijo el servidor.
        segunda = servidor.peticiones[1]
        self.assertEqual(segunda["cuerpo"]["revision_base"], 7)
        self.assertEqual(segunda["cuerpo"]["libro"]["ajustes"]["saldo_inicial"], 100)
        self.assertEqual(self.sesion_grabada()["ultima_revision"], 8)

    def test_el_conflicto_se_avisa_en_voz_alta(self):
        """Callarse un conflicto es callarse que puede haberse perdido el
        trabajo del otro ordenador."""
        self.escribir_datos({"version": 1, "ajustes": {"saldo_inicial": 100}})
        del_servidor = {"version": 1, "ajustes": {"saldo_inicial": 999}}
        sinc, _ = self.con_sesion((409, {"revision": 7, "libro": del_servidor}),
                                  (200, {"revision": 8}),
                                  revision=3)
        sinc.marcar_pendiente()
        self.assertTrue(sinc.empujar())

        conflictos = [a for a in self.avisos_de(sinc) if a[0] == "conflicto"]
        self.assertEqual(len(conflictos), 1)
        # El aviso dice dónde está la copia, que es lo único que sirve para
        # rescatar lo del otro ordenador.
        copias = list((self.carpeta / "copias").glob("*-conflicto-sincronia.json"))
        self.assertEqual(len(copias), 1)
        self.assertIn(copias[0].name, conflictos[0][1])

    def test_dos_conflictos_seguidos_avisan_una_sola_vez(self):
        self.escribir_datos({"version": 1, "ajustes": {"saldo_inicial": 100}})
        remoto = {"version": 1, "ajustes": {"saldo_inicial": 999}}
        sinc, _ = self.con_sesion((409, {"revision": 7, "libro": remoto}),
                                  (409, {"revision": 8, "libro": remoto}),
                                  (200, {"revision": 9}),
                                  revision=3)
        sinc.marcar_pendiente()
        self.assertTrue(sinc.empujar())

        conflictos = [a for a in self.avisos_de(sinc) if a[0] == "conflicto"]
        self.assertEqual(len(conflictos), 1)

    def test_token_caducado_pide_entrar_sin_perder_el_pendiente(self):
        self.escribir_datos()
        sinc, _ = self.con_sesion((401, {}))
        sinc.marcar_pendiente()

        self.assertFalse(sinc.empujar())
        self.assertTrue(sinc.caducada)
        self.assertTrue(self.sesion_grabada()["pendiente"])
        avisos = self.avisos_de(sinc)
        self.assertEqual(avisos[0][0], "caducada")


# --- descargar al arrancar --------------------------------------------------------

class PruebaDescargar(ConCarpeta):
    def test_el_servidor_va_por_delante_y_aqui_no_hay_nada_pendiente(self):
        remoto = {"version": 1, "movimientos": []}
        sinc, _ = self.con_sesion((200, {"revision": 5, "libro": remoto}), revision=2)
        sinc.descargar()

        avisos = self.avisos_de(sinc)
        # El último elemento dice si lo de aquí venía de esta misma cuenta;
        # aquí sí (hay revisión apuntada), así que la ventana no da la lata.
        self.assertEqual(avisos, [("descargar", remoto, 5, False)])
        # La revisión no se apunta hasta que la ventana aplica el libro.
        self.assertEqual(self.sesion_grabada()["ultima_revision"], 2)
        sinc.confirmar_descarga(5)
        self.assertEqual(self.sesion_grabada()["ultima_revision"], 5)

    def test_lo_del_servidor_es_igual_que_lo_de_aqui(self):
        """Volver a entrar sin haber cambiado nada no es una descarga: es
        apuntar la revisión y callarse."""
        mismo = {"version": 1, "movimientos": []}
        self.escribir_datos(mismo)
        sinc, _ = self.con_sesion((200, {"revision": 5, "libro": mismo}), revision=2)
        sinc.descargar()

        self.assertEqual(self.avisos_de(sinc), [])
        self.assertEqual(sinc.sesion["ultima_revision"], 5)
        self.assertEqual(self.sesion_grabada()["ultima_revision"], 5)

    def test_sin_revision_apuntada_lo_de_aqui_no_se_sabe_de_donde_viene(self):
        # El caso feo: se cerró sesión, se apuntaron cosas sin conexión y se
        # vuelve a entrar. Esos apuntes están a punto de ser reemplazados.
        self.escribir_datos({"version": 1, "movimientos": [{"fecha": "2026-01-05"}]})
        remoto = {"version": 1, "movimientos": []}
        sinc, _ = self.con_sesion((200, {"revision": 3, "libro": remoto}), revision=0)
        sinc.descargar()

        self.assertEqual(self.avisos_de(sinc), [("descargar", remoto, 3, True)])

    def test_con_revision_apuntada_la_descarga_es_de_las_normales(self):
        self.escribir_datos({"version": 1, "movimientos": [{"fecha": "2026-01-05"}]})
        remoto = {"version": 1, "movimientos": []}
        sinc, _ = self.con_sesion((200, {"revision": 3, "libro": remoto}), revision=2)
        sinc.descargar()

        self.assertEqual(self.avisos_de(sinc), [("descargar", remoto, 3, False)])

    def test_misma_revision_no_toca_nada(self):
        sinc, _ = self.con_sesion((200, {"revision": 2, "libro": {"version": 1}}),
                                  revision=2)
        sinc.descargar()
        self.assertEqual(self.avisos_de(sinc), [])

    def test_con_pendiente_local_no_se_pisa_nada(self):
        remoto = {"version": 1}
        sinc, _ = self.con_sesion((200, {"revision": 9, "libro": remoto}),
                                  revision=2, pendiente=True)
        sinc.descargar()
        # Primero se sube lo de aquí; si hay conflicto ya lo dirá el servidor.
        self.assertEqual(self.avisos_de(sinc), [])

    def test_cuenta_estrenada_sube_lo_local(self):
        self.escribir_datos()
        sinc, _ = self.con_sesion((200, {"revision": 0, "libro": None}), revision=0)
        sinc.descargar()
        self.assertTrue(self.sesion_grabada()["pendiente"])

    def test_sin_conexion_al_arrancar_no_molesta_mas_de_una_vez(self):
        sinc, _ = self.con_sesion(("sin-conexion", None), ("sin-conexion", None))
        sinc.descargar()
        sinc.descargar()
        avisos = self.avisos_de(sinc)
        self.assertEqual(len(avisos), 1)

    def test_token_caducado_al_arrancar(self):
        sinc, _ = self.con_sesion((401, {}))
        sinc.descargar()
        self.assertTrue(sinc.caducada)
        self.assertEqual(self.avisos_de(sinc)[0][0], "caducada")


class PruebaCuandoTocaDescargar(ConCarpeta):
    """El otro ordenador puede estar apuntando cosas ahora mismo, así que hay
    que volver a mirar el servidor cada tanto. La decisión se prueba pasándole
    la hora a mano: esperar dos minutos de verdad no lo comprueba mejor."""

    def test_recien_arrancada_toca_ya(self):
        sinc, _ = self.con_sesion()
        self.assertTrue(sinc.toca_descargar(time.monotonic()))

    def test_justo_despues_de_bajar_no_toca(self):
        sinc, _ = self.con_sesion((200, {"revision": 1, "libro": {"version": 1}}),
                                  revision=1)
        antes = time.monotonic()
        sinc.descargar()
        self.assertFalse(sinc.toca_descargar(antes))

    def test_pasado_el_rato_vuelve_a_tocar(self):
        sinc, _ = self.con_sesion((200, {"revision": 1, "libro": {"version": 1}}),
                                  revision=1)
        antes = time.monotonic()
        sinc.descargar()
        self.assertTrue(sinc.toca_descargar(antes + modulo.SEGUNDOS_ENTRE_DESCARGAS + 1))

    def test_con_algo_por_subir_primero_se_sube(self):
        sinc, _ = self.con_sesion(pendiente=True)
        self.assertFalse(sinc.toca_descargar(time.monotonic()))

    def test_con_la_sesion_caducada_no_se_insiste(self):
        sinc, _ = self.con_sesion()
        sinc._caducar()
        self.assertFalse(sinc.toca_descargar(time.monotonic()))

    def test_sin_cuenta_no_hay_nada_que_bajar(self):
        sinc, _ = self.nueva()
        self.assertFalse(sinc.toca_descargar(time.monotonic()))

    def test_el_bucle_sube_lo_pendiente_antes_de_bajar(self):
        sinc, _ = self.con_sesion(pendiente=True)
        pasos = []

        def empujar():
            pasos.append("subir")
            sinc.sesion["pendiente"] = False
            # Acorta la espera del bucle: aquí solo importa comprobar el orden.
            sinc._despertador.set()
            return True

        def descargar():
            pasos.append("bajar")
            sinc.detener()

        sinc.empujar = empujar
        sinc.descargar = descargar
        sinc._bucle()

        self.assertEqual(pasos, ["subir", "bajar"])


class PruebaGuardadoDuranteLaSubida(ConCarpeta):
    """El caso fino: se guarda un cambio mientras otro está subiéndose."""

    def test_un_cambio_durante_la_subida_no_se_da_por_subido(self):
        sinc, servidor = self.con_sesion((200, {"revision": 2}), pendiente=True)
        self.escribir_datos()

        # En cuanto la petición sale hacia el servidor, entra otro guardado.
        de_verdad = servidor.__call__

        def con_cambio_a_mitad(peticion, timeout=None):
            sinc.marcar_pendiente()
            return de_verdad(peticion, timeout=timeout)

        sinc._abrir_url = con_cambio_a_mitad
        sinc.empujar()

        # La subida fue bien (la revisión avanza), pero el cambio que llegó a
        # mitad sigue pendiente: se subirá en la siguiente vuelta.
        self.assertEqual(self.sesion_grabada()["ultima_revision"], 2)
        self.assertTrue(self.sesion_grabada()["pendiente"])

    def test_sin_cambios_a_mitad_la_subida_deja_todo_al_dia(self):
        sinc, _ = self.con_sesion((200, {"revision": 2}), pendiente=True)
        self.escribir_datos()
        sinc.empujar()
        self.assertFalse(self.sesion_grabada()["pendiente"])


if __name__ == "__main__":
    unittest.main()
