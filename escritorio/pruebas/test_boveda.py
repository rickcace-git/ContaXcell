"""El archivo de llaves cifrado: que solo se abre con la contraseña buena y
que nadie puede retocarlo sin que se note."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import boveda  # noqa: E402


class PruebaBoveda(unittest.TestCase):
    DATOS = b"la llave del servidor y la de firmar" * 50

    def test_ida_y_vuelta(self):
        cifrado = boveda.cifrar(self.DATOS, "una frase larga de verdad")
        self.assertEqual(boveda.descifrar(cifrado, "una frase larga de verdad"), self.DATOS)

    def test_no_se_ve_lo_de_dentro(self):
        cifrado = boveda.cifrar(self.DATOS, "una frase larga de verdad")
        self.assertNotIn(b"llave", cifrado)

    def test_cada_vez_sale_distinto(self):
        # Con su sal propia: dos archivos iguales no se delatan entre sí.
        self.assertNotEqual(boveda.cifrar(self.DATOS, "contrasena123"),
                            boveda.cifrar(self.DATOS, "contrasena123"))

    def test_contrasena_mala(self):
        cifrado = boveda.cifrar(self.DATOS, "la buena de verdad")
        with self.assertRaises(boveda.ContrasenaMala):
            boveda.descifrar(cifrado, "la mala de verdad")

    def test_retocado_se_nota(self):
        cifrado = bytearray(boveda.cifrar(self.DATOS, "la buena de verdad"))
        cifrado[-1] ^= 1
        with self.assertRaises(boveda.ContrasenaMala):
            boveda.descifrar(bytes(cifrado), "la buena de verdad")

    def test_otra_cosa_no_es_un_archivo_de_llaves(self):
        with self.assertRaises(boveda.ContrasenaMala):
            boveda.descifrar(b"PK\x03\x04 un zip cualquiera", "lo que sea")


if __name__ == "__main__":
    unittest.main()
