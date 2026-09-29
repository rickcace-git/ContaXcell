"""Las cabeceras de las tablas no se cortan, sea cual sea el zoom de Windows."""

from __future__ import annotations

import sys
import tkinter as tk
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from contaxcell import tema, widgets  # noqa: E402


class PruebasAnchoDeColumnas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError as error:
            raise unittest.SkipTest(f"no hay pantalla disponible: {error}") from error
        cls.raiz.withdraw()

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def tabla(self, escala: float, columnas) -> widgets.Tabla:
        fuentes = tema.Fuentes(escala)
        tema.aplicar(self.raiz, tema.CLARA, fuentes)
        widgets.usar(tema.CLARA, fuentes)
        tabla = widgets.Tabla(self.raiz, columnas)
        self.addCleanup(tabla.destroy)
        return tabla

    def ancho(self, tabla, clave) -> int:
        return int(tabla.arbol.column(clave, "width"))

    def test_al_100_se_respeta_el_ancho_escrito(self):
        tabla = self.tabla(1.0, [widgets.Columna("a", "Fecha", 100)])
        self.assertEqual(100, self.ancho(tabla, "a"))

    def test_con_zoom_el_ancho_crece_con_la_letra(self):
        tabla = self.tabla(1.5, [widgets.Columna("a", "Fecha", 100)])
        self.assertEqual(150, self.ancho(tabla, "a"))

    def test_nunca_mas_estrecha_que_su_cabecera(self):
        for escala in (1.0, 1.25, 1.5, 2.0):
            with self.subTest(escala=escala):
                tabla = self.tabla(escala, [widgets.Columna("a", "Aportado acumulado", 60)])
                necesita = widgets.FUENTES.titulo.measure("Aportado acumulado") + 12
                self.assertGreaterEqual(self.ancho(tabla, "a"), necesita)

    def test_un_titulo_nuevo_mas_largo_ensancha_la_columna(self):
        tabla = self.tabla(1.0, [widgets.Columna("a", "Mes", 60)])
        tabla.titulo_columna("a", "Saldo a fin de mes y más")
        necesita = widgets.FUENTES.titulo.measure("Saldo a fin de mes y más") + 12
        self.assertGreaterEqual(self.ancho(tabla, "a"), necesita)


if __name__ == "__main__":
    unittest.main()
