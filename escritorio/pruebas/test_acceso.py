"""Lo que se comprueba al crear la cuenta, antes de mandar nada al servidor.

Va sin ventana: son las funciones de acceso.py que deciden si el formulario
está bien. Las pantallas se revisan con capturas.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contaxcell.acceso import correo_valido, fallo_cuenta_nueva  # noqa: E402


class PruebaCorreo(unittest.TestCase):
    def test_buenos(self):
        for bueno in ("ana@correo.es", "  Ana.Perez+conta@sub.correo.com ", "a@b.co"):
            with self.subTest(bueno):
                self.assertTrue(correo_valido(bueno))

    def test_malos(self):
        for malo in ("", "ana", "ana@", "@correo.es", "ana@correo", "ana@.es",
                     "ana@correo.", "ana perez@correo.es", "ana@co@rreo.es",
                     "a" * 250 + "@correo.es"):
            with self.subTest(malo):
                self.assertFalse(correo_valido(malo))


class PruebaCuentaNueva(unittest.TestCase):
    BIEN = ("ana", "ana@correo.es", "contrasena1", "contrasena1")

    def con(self, **cambios):
        usuario, correo, contrasena, repetida = self.BIEN
        valores = {"usuario": usuario, "correo": correo, "contrasena": contrasena,
                   "repetida": repetida, **cambios}
        return fallo_cuenta_nueva(valores["usuario"], valores["correo"],
                                  valores["contrasena"], valores["repetida"])

    def test_todo_bien(self):
        self.assertEqual(self.con(), "")

    def test_cada_fallo_con_su_mensaje(self):
        self.assertIn("usuario", self.con(usuario="ab"))
        self.assertIn("usuario", self.con(usuario="a" * 31))
        self.assertIn("Falta el correo", self.con(correo="  "))
        self.assertIn("no parece válido", self.con(correo="ana@correo"))
        self.assertIn("al menos 8", self.con(contrasena="corta", repetida="corta"))
        self.assertIn("no son iguales", self.con(repetida="contrasena2"))

    def test_avisa_del_primero_de_arriba(self):
        # Con todo mal, el aviso es el del usuario, que es el primer campo.
        self.assertIn("usuario", fallo_cuenta_nueva("", "", "", "x"))


if __name__ == "__main__":
    unittest.main()
