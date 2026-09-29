"""Pruebas de la guía de uso (Ayuda ▸ Guía de uso, o F1)."""

from __future__ import annotations

import pkgutil
import sys
import tkinter as tk
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from contaxcell import guia, tema, vistas, widgets  # noqa: E402


class PruebasContenido(unittest.TestCase):
    def test_hay_un_apartado_por_cada_pestana(self):
        # Una pestaña nueva sin su apartado haría que F1 abriera el de
        # «Para empezar» sin avisar: mejor que falle aquí.
        pestanas = {m.name for m in pkgutil.iter_modules(vistas.__path__)} - {"comun"}
        claves = {a.clave for a in guia.APARTADOS}
        self.assertEqual(set(), pestanas - claves)

    def test_las_claves_no_se_repiten(self):
        claves = [a.clave for a in guia.APARTADOS]
        self.assertEqual(len(claves), len(set(claves)))

    def test_ningun_apartado_esta_vacio(self):
        for a in guia.APARTADOS:
            with self.subTest(a.clave):
                self.assertTrue(guia.trozos(a.texto))

    def test_una_clave_desconocida_abre_el_primero(self):
        self.assertIs(guia.APARTADOS[0], guia.apartado("no-existe"))

    def test_trozos_reconoce_cada_formato(self):
        texto = "\n## Título\n\n1. Un paso\n• Un punto\nUn párrafo\n\n"
        self.assertEqual([("titulo", "Título"), ("paso", "1. Un paso"),
                          ("punto", "• Un punto"), ("parrafo", "Un párrafo")],
                         guia.trozos(texto))


class PruebasVentana(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError as error:
            raise unittest.SkipTest(f"no hay pantalla disponible: {error}") from error
        cls.raiz.withdraw()
        fuentes = tema.Fuentes()
        tema.aplicar(cls.raiz, tema.CLARA, fuentes)
        widgets.usar(tema.CLARA, fuentes)

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def guia(self, clave: str) -> guia.Guia:
        ventana = guia.Guia(self.raiz, clave)
        self.addCleanup(ventana.destroy)
        return ventana

    def test_abre_por_el_apartado_pedido(self):
        ventana = self.guia("deudas")
        self.assertEqual("deudas", ventana.apartado_actual.clave)
        self.assertEqual((guia.APARTADOS.index(guia.apartado("deudas")),),
                         ventana.lista.curselection())
        self.assertTrue(ventana.texto.get("1.0", "2.0").startswith("Deudas"))

    def test_ir_a_cambia_el_texto(self):
        ventana = self.guia("apuntar")
        ventana.ir_a("inversiones")
        self.assertIn("Añadir activo", ventana.texto.get("1.0", "end"))

    def test_el_texto_es_de_solo_lectura(self):
        ventana = self.guia("empezar")
        self.assertEqual("disabled", str(ventana.texto.cget("state")))

    def test_las_flechas_mueven_de_apartado(self):
        ventana = self.guia("empezar")
        ventana._mover(1)
        self.assertEqual(guia.APARTADOS[1].clave, ventana.apartado_actual.clave)
        ventana._mover(-1)
        ventana._mover(-1)  # ya en el primero: se queda
        self.assertEqual(guia.APARTADOS[0].clave, ventana.apartado_actual.clave)


if __name__ == "__main__":
    unittest.main()
