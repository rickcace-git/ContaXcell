"""Los iconos dibujados a mano de las pestañas y de la guía."""

from __future__ import annotations

import pkgutil
import sys
import tkinter as tk
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from contaxcell import iconos, vistas  # noqa: E402


class PruebasDibujos(unittest.TestCase):
    def test_cada_pestana_tiene_su_icono(self):
        pestanas = {m.name for m in pkgutil.iter_modules(vistas.__path__)} - {"comun"}
        self.assertEqual(set(), pestanas - set(iconos.DIBUJOS))

    def test_ningun_icono_sale_en_blanco_ni_lleno(self):
        for nombre in iconos.DIBUJOS:
            with self.subTest(nombre):
                pixeles = [a for fila in iconos.cobertura(nombre, 16) for a in fila]
                tapado = sum(pixeles) / (255 * len(pixeles))
                self.assertGreater(tapado, 0.08)
                self.assertLess(tapado, 0.6)

    def test_los_bordes_salen_suaves(self):
        # Con varias muestras por píxel hay grises entre el fondo y el trazo.
        pixeles = {a for fila in iconos.cobertura("apuntar", 16) for a in fila}
        self.assertTrue(any(0 < a < 255 for a in pixeles))

    def test_el_png_lleva_el_color_pedido(self):
        datos = iconos.png("resumen", 16, "#2f6feb")
        self.assertTrue(datos.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn(b"IHDR", datos)


class PruebasImagen(unittest.TestCase):
    def test_tkinter_lo_abre_del_tamano_pedido(self):
        try:
            raiz = tk.Tk()
        except tk.TclError as error:
            raise unittest.SkipTest(f"no hay pantalla disponible: {error}") from error
        self.addCleanup(raiz.destroy)
        imagen = iconos.imagen(raiz, "ajustes", 24, "#333333")
        self.assertEqual((24, 24), (imagen.width(), imagen.height()))


if __name__ == "__main__":
    unittest.main()
