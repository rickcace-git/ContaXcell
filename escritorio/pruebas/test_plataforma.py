"""Pruebas de lo que cambia de un sistema a otro: Windows, el Mac y el resto.

Casi todo se prueba haciéndose pasar por el otro sistema, para que en
cualquier ordenador se compruebe el camino de los dos. Lo único que necesita
ventana de verdad es la rueda y el trackpad, y eso se salta si no hay
pantalla.
"""

from __future__ import annotations

import struct
import subprocess
import sys
import tempfile
import tkinter as tk
import unittest
from tkinter import ttk
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(RAIZ / "recursos"))

import hacer_icono  # noqa: E402
from contaxcell import almacen, atajos, guia, tema, ventana, widgets  # noqa: E402


class PruebasCarpetaDeDatos(unittest.TestCase):
    def setUp(self):
        self.casa = Path(tempfile.mkdtemp(prefix="contaxcell-casa-"))
        parches = (mock.patch.object(Path, "home", return_value=self.casa),
                   mock.patch.dict(almacen.os.environ, clear=False))
        for parche in parches:
            parche.start()
            self.addCleanup(parche.stop)
        almacen.os.environ.pop("APPDATA", None)

    def en(self, plataforma: str) -> Path:
        with mock.patch.object(almacen.sys, "platform", plataforma):
            return almacen.carpeta_de_datos()

    def test_windows_usa_appdata(self):
        almacen.os.environ["APPDATA"] = str(self.casa / "AppData")
        self.assertEqual(self.en("win32"), self.casa / "AppData" / "ContaXcell")

    def test_mac_usa_application_support(self):
        self.assertEqual(self.en("darwin"),
                         self.casa / "Library" / "Application Support" / "ContaXcell")

    def test_mac_sigue_con_la_carpeta_oculta_si_ya_la_tenia(self):
        # Quien la usaba antes de tener sitio propio no puede ver su
        # contabilidad desaparecer de un día para otro.
        (self.casa / ".contaxcell").mkdir()
        self.assertEqual(self.en("darwin"), self.casa / ".contaxcell")

    def test_linux_usa_la_carpeta_oculta(self):
        self.assertEqual(self.en("linux"), self.casa / ".contaxcell")


class PruebasModoOscuroDelMac(unittest.TestCase):
    def contesta(self, **kw):
        return mock.patch.object(subprocess, "run", **kw)

    def test_oscuro(self):
        respuesta = subprocess.CompletedProcess([], 0, stdout="Dark\n")
        with self.contesta(return_value=respuesta):
            self.assertTrue(tema._mac_en_oscuro())

    def test_claro_es_que_la_clave_no_existe(self):
        respuesta = subprocess.CompletedProcess([], 1, stdout="")
        with self.contesta(return_value=respuesta):
            self.assertFalse(tema._mac_en_oscuro())

    def test_sin_poder_preguntar_se_queda_en_claro(self):
        with self.contesta(side_effect=FileNotFoundError):
            self.assertFalse(tema._mac_en_oscuro())
        with self.contesta(side_effect=subprocess.TimeoutExpired("defaults", 2)):
            self.assertFalse(tema._mac_en_oscuro())

    def test_el_sistema_pregunta_al_mac_estando_en_el_mac(self):
        with mock.patch.object(tema.sys, "platform", "darwin"), \
                mock.patch.object(tema, "_mac_en_oscuro", return_value=True):
            self.assertTrue(tema.sistema_en_oscuro())


class PruebasAtajos(unittest.TestCase):
    def en_mac(self, si: bool):
        return mock.patch.object(atajos, "ES_MAC", si)

    def test_windows_va_con_control(self):
        with self.en_mac(False):
            self.assertEqual(atajos.atajo("e"),
                             atajos.Atajo("<Control-Key-e>", "Ctrl+E", "Ctrl+E"))
            # En Windows Ctrl+H no choca con nada: no lleva mayúsculas.
            self.assertEqual(atajos.atajo("h", con_shift_en_mac=True).evento,
                             "<Control-Key-h>")

    def test_mac_va_con_comando(self):
        with self.en_mac(True):
            self.assertEqual(atajos.atajo("e"),
                             atajos.Atajo("<Command-Key-e>", "Command-E", "⌘E"))
            # ⌘H es del sistema: ocultar los importes va con ⇧⌘H.
            self.assertEqual(atajos.atajo("h", con_shift_en_mac=True),
                             atajos.Atajo("<Command-Shift-Key-H>",
                                          "Shift-Command-H", "⇧⌘H"))

    def test_los_numeros_son_teclas_y_no_botones_del_raton(self):
        # «<Command-1>» sería pulsar el botón 1 del ratón con ⌘.
        with self.en_mac(True):
            self.assertEqual(atajos.pestana(1).evento, "<Command-Key-1>")

    def test_la_guia_cuenta_los_atajos_de_este_sistema(self):
        textos = "".join(apartado.texto for apartado in guia.APARTADOS)
        self.assertIn(atajos.OCULTAR.texto, textos)
        self.assertIn(f"{atajos.pestana(1).texto} a {atajos.pestana(8).texto}", textos)
        self.assertNotIn("{", textos.replace("{}", ""))  # ninguna marca sin cambiar
        if atajos.ES_MAC:
            self.assertNotIn("Ctrl+", textos)


class PruebasVolverALanzar(unittest.TestCase):
    """En el Mac el programa se relanza al entrar o salir de la cuenta."""

    def lanzar(self, **parches):
        with mock.patch.object(ventana.os, "execve") as execve, \
                mock.patch.multiple(ventana.sys, **parches):
            ventana.volver_a_lanzar()
        programa, orden, entorno = execve.call_args.args
        return programa, orden, entorno

    def test_desde_el_codigo_repite_la_orden_tal_cual(self):
        programa, orden, _ = self.lanzar(
            executable="/py/bin/python", orig_argv=["python", "-m", "contaxcell"],
            argv=["/ruta/contaxcell/__main__.py"])
        self.assertEqual(programa, "/py/bin/python")
        # Con `argv` saldría la ruta del __main__.py, que suelto no arranca.
        self.assertEqual(orden, ["/py/bin/python", "-m", "contaxcell"])

    def test_empaquetado_relanza_el_ejecutable(self):
        programa, orden, entorno = self.lanzar(
            executable="/Applications/ContaXcell.app/Contents/MacOS/ContaXcell",
            argv=["/Applications/ContaXcell.app/Contents/MacOS/ContaXcell"],
            frozen=True, create=True)
        self.assertEqual(orden, [programa])
        self.assertEqual(entorno["PYINSTALLER_RESET_ENVIRONMENT"], "1")


class PruebasTrackpad(unittest.TestCase):
    @staticmethod
    def empaquetado(horizontal: int, vertical: int) -> int:
        """Como lo manda Tk: las dos en un entero de 32 bits con signo."""
        crudo = ((horizontal & 0xFFFF) << 16) | (vertical & 0xFFFF)
        return struct.unpack(">i", struct.pack(">I", crudo))[0]

    def test_saca_la_vertical_con_su_signo(self):
        for horizontal, vertical in ((0, 7), (3, -5), (-4, 12), (-1, -1), (0, 0)):
            with self.subTest(horizontal=horizontal, vertical=vertical):
                self.assertEqual(
                    widgets.vertical_del_trackpad(self.empaquetado(horizontal, vertical)),
                    vertical)


class PruebasIconoDelMac(unittest.TestCase):
    def test_icns_bien_formado(self):
        pngs = [(b"icp4", b"uno"), (b"ic10", b"dos-dos")]
        datos = hacer_icono.a_icns(pngs)
        self.assertEqual(datos[:4], b"icns")
        self.assertEqual(struct.unpack(">I", datos[4:8])[0], len(datos))

        leidos, posicion = [], 8
        while posicion < len(datos):
            etiqueta = datos[posicion:posicion + 4]
            largo = struct.unpack(">I", datos[posicion + 4:posicion + 8])[0]
            leidos.append((etiqueta, datos[posicion + 8:posicion + largo]))
            posicion += largo
        self.assertEqual(leidos, pngs)

    def test_margen_centrado(self):
        lleno = (1, 2, 3, 255)
        resultado = hacer_icono.con_margen([[lleno] * 2 for _ in range(2)], 6)
        self.assertEqual(len(resultado), 6)
        self.assertTrue(all(len(fila) == 6 for fila in resultado))
        llenos = [(y, x) for y, fila in enumerate(resultado)
                  for x, pixel in enumerate(fila) if pixel == lleno]
        self.assertEqual(llenos, [(2, 2), (2, 3), (3, 2), (3, 3)])

    def test_cada_tamano_del_icns_es_de_los_que_salen_del_maestro(self):
        # Si no divide al maestro, la reducción se dejaría píxeles fuera.
        for _, lado in hacer_icono.TIPOS_ICNS:
            self.assertEqual(hacer_icono.LADO_MAESTRO_MAC % lado, 0, lado)


class PruebasDesplazamiento(unittest.TestCase):
    """La rueda y el trackpad sobre un marco de verdad, más alto que su hueco."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError as error:
            raise unittest.SkipTest(f"no hay pantalla disponible: {error}") from error
        fuentes = tema.Fuentes()
        tema.aplicar(cls.raiz, tema.CLARA, fuentes)
        widgets.usar(tema.CLARA, fuentes)
        cls.raiz.geometry("300x200")

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def setUp(self):
        self.marco = widgets.MarcoDesplazable(self.raiz)
        self.marco.pack(fill="both", expand=True)
        self.addCleanup(self.marco.destroy)
        tk.Frame(self.marco.interior, height=2000, width=100).pack()
        self.raiz.update()

    def arriba(self) -> float:
        return self.marco.lienzo.canvasy(0)

    def test_el_trackpad_mueve_los_pixeles_justos(self):
        self.marco._trackpad(PruebasTrackpad.empaquetado(0, -37))
        self.assertEqual(self.arriba(), 37)
        self.marco._trackpad(PruebasTrackpad.empaquetado(0, 12))
        self.assertEqual(self.arriba(), 25)

    def test_el_trackpad_no_se_pasa_de_arriba(self):
        self.marco._trackpad(PruebasTrackpad.empaquetado(0, 500))
        self.assertEqual(self.arriba(), 0)

    def test_los_trozos_de_muesca_se_juntan(self):
        un_tercio = widgets._RUEDA_POR_MUESCA / 3
        self.marco._rueda(-un_tercio)
        self.marco._rueda(-un_tercio)
        self.assertEqual(self.arriba(), 0)  # todavía no llega a una línea
        self.marco._rueda(-un_tercio)
        self.assertGreater(self.arriba(), 0)

    def test_subir_y_bajar_lo_mismo_deja_donde_estaba(self):
        self.marco._rueda(-2 * widgets._RUEDA_POR_MUESCA)
        abajo = self.arriba()
        self.assertGreater(abajo, 0)
        medio = widgets._RUEDA_POR_MUESCA / 2
        for _ in range(4):
            self.marco._rueda(medio)
        self.assertEqual(self.arriba(), 0)

    def con_tabla_debajo(self, filas: int) -> ttk.Treeview:
        tabla = ttk.Treeview(self.marco.interior, height=3)
        tabla.pack()
        for numero in range(filas):
            tabla.insert("", "end", text=str(numero))
        self.raiz.update()
        parche = mock.patch.object(self.marco, "winfo_containing", return_value=tabla)
        parche.start()
        self.addCleanup(parche.stop)
        return tabla

    def test_encima_de_una_tabla_larga_la_pagina_no_se_mueve(self):
        self.con_tabla_debajo(filas=40)
        self.marco._rueda(-widgets._RUEDA_POR_MUESCA)
        self.marco._trackpad(PruebasTrackpad.empaquetado(0, -30))
        self.assertEqual(self.arriba(), 0)

    def test_encima_de_una_tabla_que_cabe_se_mueve_la_pagina(self):
        self.con_tabla_debajo(filas=2)
        self.marco._trackpad(PruebasTrackpad.empaquetado(0, -30))
        self.assertEqual(self.arriba(), 30)

    def test_entrar_y_salir_no_va_dejando_funciones_por_ahi(self):
        # Atar la rueda con `bind_all` en cada entrada del ratón dejaba una
        # función nueva en Tcl cada vez, sin borrar nunca ninguna.
        antes = len(self.marco._tclCommands or [])
        for _ in range(50):
            self.marco._atar_rueda(True)
            self.marco._atar_rueda(False)
        self.assertEqual(len(self.marco._tclCommands or []), antes)
        self.assertEqual(self.raiz.tk.call("bind", "all", "<MouseWheel>"), "")


if __name__ == "__main__":
    unittest.main()
