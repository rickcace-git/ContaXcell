"""publicar.py: la lista de cambios que viaja en la nota y el enlace al código.

Sin red ni git de verdad: se prueba lo que convierte la salida de git en lo
que ve el usuario. Lo de subir al servidor se comprueba publicando.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import publicar  # noqa: E402


def registro(titulo: str, cuerpo: str = "") -> str:
    return f"{titulo}\x1f{cuerpo}\x1e"


class PruebaLeerCambios(unittest.TestCase):
    def test_titulo_y_detalle_en_parrafos(self):
        salida = registro("Lo nuevo", "Una frase cortada\na los setenta y dos.\n\nOtro párrafo.\n")
        self.assertEqual(publicar.leer_cambios(salida), [
            {"titulo": "Lo nuevo", "detalle": "Una frase cortada a los setenta y dos.\nOtro párrafo."},
        ])

    def test_las_listas_se_respetan(self):
        salida = registro("Varias cosas", "Trae:\n- una\n- otra que sigue\n  en otra línea\n")
        self.assertEqual(publicar.leer_cambios(salida)[0]["detalle"],
                         "Trae:\n- una\n- otra que sigue en otra línea")

    def test_sin_firmas_de_coautoria(self):
        salida = registro("Arreglo", "Lo que sea.\n\nCo-Authored-By: Alguien <a@b.c>\n")
        self.assertEqual(publicar.leer_cambios(salida)[0]["detalle"], "Lo que sea.")

    def test_subir_el_numero_no_es_un_cambio(self):
        salida = registro("Versión 1.1.5") + registro("Lo de verdad")
        self.assertEqual([c["titulo"] for c in publicar.leer_cambios(salida)], ["Lo de verdad"])

    def test_varios_en_orden_y_sin_cuerpo(self):
        salida = registro("El último") + "\n" + registro("El primero", "")
        self.assertEqual([c["titulo"] for c in publicar.leer_cambios(salida)],
                         ["El último", "El primero"])
        self.assertEqual(publicar.leer_cambios(""), [])


class PruebaEnlaceCodigo(unittest.TestCase):
    def test_github_por_https_y_por_ssh(self):
        for remoto in ("https://github.com/ana/Conta.git\n", "git@github.com:ana/Conta.git"):
            with self.subTest(remoto):
                self.assertEqual(publicar.enlace_codigo(remoto, "a" * 40, "b" * 40),
                                 f"https://github.com/ana/Conta/compare/{'a' * 12}...{'b' * 12}")

    def test_otro_sitio_o_sin_commits_no_da_enlace(self):
        self.assertEqual(publicar.enlace_codigo("https://gitlab.com/ana/x.git", "a", "b"), "")
        self.assertEqual(publicar.enlace_codigo("https://github.com/ana/x.git", "", "b"), "")


class PruebaParaLasDeAntes(unittest.TestCase):
    """La 1.1.3 y la 1.1.4 solo leen «cambios»: les va todo, con la versión."""

    def test_lleva_lo_de_la_1_1_4_en_adelante_con_su_version(self):
        entradas = [
            {"version": "1.1.5", "desde": "b" * 40, "hasta": "c" * 40,
             "cambios": [{"titulo": "Nuevo", "detalle": ""}]},
            {"version": "1.1.4", "desde": "a" * 40, "hasta": "b" * 40,
             "cambios": [{"titulo": "De antes", "detalle": "x"}]},
            {"version": "1.1.3", "desde": "9" * 40, "hasta": "a" * 40,
             "cambios": [{"titulo": "Viejo", "detalle": ""}]},
        ]
        cambios, codigo = publicar.para_las_de_antes(entradas)
        self.assertEqual([c["titulo"] for c in cambios], ["1.1.5 · Nuevo", "1.1.4 · De antes"])
        self.assertTrue(codigo.endswith(f"/compare/{'a' * 12}...{'c' * 12}"))


if __name__ == "__main__":
    unittest.main()
