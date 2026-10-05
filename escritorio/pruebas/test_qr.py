"""El QR de la descarga de la app, hecho sin librerías.

Que un lector de verdad lo lee se comprobó a mano con zxing-cpp (las
versiones 1 a 10, con tildes y con el máximo de cada una). Aquí se fija lo
que no depende de tener un lector: la corrección de errores contra el
ejemplo de la norma, el tamaño de cada versión y las marcas fijas.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contaxcell import qr  # noqa: E402


class PruebaCorreccion(unittest.TestCase):
    def test_el_ejemplo_de_la_norma(self):
        # «HELLO WORLD» en versión 1-M: los datos y los diez bytes de
        # corrección que salen en todos los tutoriales del QR.
        datos = [32, 91, 11, 120, 209, 114, 220, 77, 67, 64, 236, 17, 236, 17, 236, 17]
        self.assertEqual(qr._correccion(datos, qr._divisor(10)),
                         [196, 35, 39, 119, 235, 215, 231, 226, 93, 23])


class PruebaTamanos(unittest.TestCase):
    def test_cada_texto_va_a_la_version_mas_pequena_en_que_cabe(self):
        # El máximo en bytes de cada versión con corrección M.
        for version, cabe in enumerate((14, 26, 42, 62, 84, 106, 122, 152, 180, 213), start=1):
            with self.subTest(version=version):
                self.assertEqual(len(qr.matriz("x" * cabe)), version * 4 + 17)
                if version < 10:
                    self.assertEqual(len(qr.matriz("x" * (cabe + 1))), version * 4 + 21)

    def test_lo_que_no_cabe_lo_dice(self):
        with self.assertRaises(qr.DemasiadoLargo):
            qr.matriz("x" * 214)

    def test_la_direccion_de_la_app_cabe_en_poco(self):
        self.assertLessEqual(len(qr.matriz("https://52.215.253.227/descargas/ContaXcell.apk")), 33)


class PruebaDibujo(unittest.TestCase):
    def setUp(self):
        self.m = qr.matriz("https://ejemplo.es/descargas/ContaXcell.apk")
        self.lado = len(self.m)

    def test_los_tres_cuadros_de_las_esquinas(self):
        for cx, cy in ((3, 3), (self.lado - 4, 3), (3, self.lado - 4)):
            with self.subTest(esquina=(cx, cy)):
                self.assertTrue(self.m[cy][cx])          # el centro, negro
                self.assertFalse(self.m[cy][cx + 2])     # el anillo blanco
                self.assertTrue(self.m[cy][cx + 3])      # el borde, negro

    def test_las_lineas_de_ritmo(self):
        for i in range(8, self.lado - 8):
            self.assertEqual(self.m[6][i], i % 2 == 0)
            self.assertEqual(self.m[i][6], i % 2 == 0)

    def test_el_cuadrito_que_siempre_va_negro(self):
        self.assertTrue(self.m[self.lado - 8][8])

    def test_el_png_es_un_png_cuadrado_con_su_margen(self):
        datos = qr.png("hola", tamano_modulo=3, margen=4)
        self.assertTrue(datos.startswith(b"\x89PNG\r\n\x1a\n"))
        ancho = int.from_bytes(datos[16:20], "big")
        alto = int.from_bytes(datos[20:24], "big")
        self.assertEqual((ancho, alto), ((21 + 8) * 3, (21 + 8) * 3))


if __name__ == "__main__":
    unittest.main()
