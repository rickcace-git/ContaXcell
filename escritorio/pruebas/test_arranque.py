"""Lo que hace la ventana nada más abrirse cuando hay cuenta.

Abre la aplicación de verdad (con su hilo de fondo) contra un servidor de
mentira, así que estas pruebas necesitan pantalla, igual que test_dialogos.

El caso que se cubre es el que pasó: en un ordenador quedaba una copia
atrasada con recibos periódicos por vencer, y en el servidor estaba la
buena. Antes, la ventana apuntaba los recibos al instante, eso marcaba la
copia atrasada como «con cambios», y el hilo la subía encima de la buena.
"""

from __future__ import annotations

import json
import sys
import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from contaxcell import almacen, sincronia as modulo, ventana  # noqa: E402
from contaxcell.modelo import GASTO, MENSUAL, Libro, Movimiento, Periodico  # noqa: E402
from pruebas.test_sincronia import ServidorFalso  # noqa: E402


def libro_del_dia_9() -> Libro:
    libro = Libro.vacio()
    libro.ajustes.saldo_inicial = 1000.0
    libro.periodicos = [Periodico(nombre="Alquiler", categoria="Vivienda y Suministros",
                                  importe=700.0, periodo=MENSUAL, desde="2026-01-05",
                                  apuntado_hasta="2026-08-05", id="p1")]
    libro.movimientos = [Movimiento(fecha="2026-09-09", descripcion="Pan",
                                    categoria="Comida", importe=2.0, id="m9")]
    return libro


def libro_del_dia_18() -> Libro:
    libro = libro_del_dia_9()
    libro.movimientos.append(Movimiento(fecha="2026-09-18", descripcion="Cena",
                                        categoria="Comida", importe=30.0, id="m18"))
    return libro


class PruebaArranqueConCuenta(unittest.TestCase):
    def setUp(self):
        self._temporal = tempfile.TemporaryDirectory(prefix="contaxcell-arranque-")
        self.carpeta = Path(self._temporal.name)
        self.addCleanup(self._temporal.cleanup)
        # Nunca la contabilidad de verdad.
        self._carpeta_de_antes = almacen.carpeta_de_datos
        almacen.carpeta_de_datos = lambda: self.carpeta
        self.addCleanup(setattr, almacen, "carpeta_de_datos", self._carpeta_de_antes)

    def con_sesion(self, revision: int) -> None:
        (self.carpeta / modulo.ARCHIVO_SESION).write_text(json.dumps({
            "servidor": "http://servidor:8000", "usuario": "ricardo",
            "token": "t0ken", "ultima_revision": revision, "pendiente": False,
        }), encoding="utf-8")

    def abrir(self, servidor: ServidorFalso) -> ventana.Aplicacion:
        sinc = modulo.Sincronia(self.carpeta, abrir_url=servidor)
        try:
            app = ventana.Aplicacion(sincronia=sinc)
        except tk.TclError as error:
            raise unittest.SkipTest(f"no hay pantalla disponible: {error}") from error
        app.withdraw()
        self.addCleanup(self.cerrar, app, sinc)
        return app

    @staticmethod
    def cerrar(app: ventana.Aplicacion, sinc: modulo.Sincronia) -> None:
        sinc.detener()
        # Los `after` que queden programados chillarían al no existir ya la
        # ventana; se cancelan antes de tirarla.
        for pendiente in app.tk.call("after", "info"):
            app.after_cancel(pendiente)
        app.destroy()

    @staticmethod
    def esperar(app: ventana.Aplicacion, hasta, segundos: float = 5.0) -> None:
        """Deja correr la ventana (y con ella la cola de avisos) hasta que
        `hasta()` sea verdad o se acabe la paciencia."""
        tope = time.monotonic() + segundos
        while not hasta() and time.monotonic() < tope:
            app.update()
            time.sleep(0.05)

    def test_la_copia_atrasada_no_pisa_a_la_del_servidor(self):
        guardador = almacen.Almacen(self.carpeta)
        guardador.libro = libro_del_dia_9()
        guardador.guardar()
        self.con_sesion(revision=3)

        servidor = ServidorFalso(
            (200, {"revision": 7, "libro": libro_del_dia_18().a_json()}),
            (200, {"revision": 8}),
        )
        app = self.abrir(servidor)
        self.esperar(app, lambda: len(servidor.peticiones) >= 2)

        # Primero se ha mirado el servidor y después se ha subido, no al revés.
        self.assertEqual([p["metodo"] for p in servidor.peticiones], ["GET", "PUT"])
        subida = servidor.peticiones[1]["cuerpo"]
        # Lo subido parte de la revisión del servidor (nada de conflicto)...
        self.assertEqual(subida["revision_base"], 7)
        fechas = sorted(m["fecha"] for m in subida["libro"]["movimientos"])
        # ...lleva la cena del 18 que solo estaba allí, y el alquiler de
        # septiembre apuntado encima, que es lo único que ha cambiado aquí.
        self.assertEqual(fechas, ["2026-09-05", "2026-09-09", "2026-09-18"])
        self.assertEqual(subida["libro"]["periodicos"][0]["apuntado_hasta"], "2026-09-05")

        # Y en pantalla está lo mismo que se ha subido.
        self.assertEqual(sorted(m.fecha for m in app.libro.movimientos), fechas)
        self.assertEqual(json.loads((self.carpeta / modulo.ARCHIVO_SESION)
                                    .read_text(encoding="utf-8"))["ultima_revision"], 8)

    def test_sin_nada_nuevo_en_el_servidor_los_recibos_se_apuntan_igual(self):
        guardador = almacen.Almacen(self.carpeta)
        guardador.libro = libro_del_dia_9()
        guardador.guardar()
        self.con_sesion(revision=3)

        servidor = ServidorFalso(
            (200, {"revision": 3, "libro": libro_del_dia_9().a_json()}),
            (200, {"revision": 4}),
        )
        app = self.abrir(servidor)
        self.esperar(app, lambda: len(servidor.peticiones) >= 2)

        self.assertEqual([p["metodo"] for p in servidor.peticiones], ["GET", "PUT"])
        self.assertEqual(servidor.peticiones[1]["cuerpo"]["revision_base"], 3)
        self.assertEqual(sorted(m.fecha for m in app.libro.movimientos),
                         ["2026-09-05", "2026-09-09"])

    def test_sin_conexion_los_recibos_no_esperan_al_tope(self):
        guardador = almacen.Almacen(self.carpeta)
        guardador.libro = libro_del_dia_9()
        guardador.guardar()
        self.con_sesion(revision=3)

        servidor = ServidorFalso(("sin-conexion", None), ("sin-conexion", None))
        app = self.abrir(servidor)
        # Con el cable desenchufado, el hilo lo dice y la ventana no se queda
        # los quince segundos del tope de brazos cruzados.
        self.esperar(app, lambda: any(m.fecha == "2026-09-05" for m in app.libro.movimientos),
                     segundos=3.0)
        self.assertIn("2026-09-05", [m.fecha for m in app.libro.movimientos])


if __name__ == "__main__":
    unittest.main()
