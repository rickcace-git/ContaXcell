"""Las ventanitas (calendario, diálogos, globos) se quedan en la pantalla de
la ventana, aunque no sea la principal. Se probó a mano con dos monitores de
verdad; aquí, la cuenta de dónde cabe, sin abrir nada."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contaxcell.widgets import dentro_de_pantalla  # noqa: E402

PRINCIPAL = (0, 0, 1440, 852)
DERECHA = (1440, -63, 2840, 939)
IZQUIERDA = (-1920, 0, 0, 1040)


class PruebaDentroDePantalla(unittest.TestCase):
    def test_si_cabe_no_se_mueve(self):
        self.assertEqual(dentro_de_pantalla(DERECHA, 1643, 300, 280, 260), (1643, 300))

    def test_en_la_pantalla_derecha_no_se_va_a_la_principal(self):
        # Antes se recortaba contra la principal y acababa en x=1218.
        x, _ = dentro_de_pantalla(DERECHA, 1643, 300, 280, 260)
        self.assertGreaterEqual(x, 1440)

    def test_en_una_pantalla_a_la_izquierda_admite_negativos(self):
        # Antes el max(0, x) la mandaba a x=0, a la principal.
        self.assertEqual(dentro_de_pantalla(IZQUIERDA, -1500, 200, 280, 260), (-1500, 200))

    def test_pegada_al_borde_se_mete_dentro_de_su_pantalla(self):
        x, y = dentro_de_pantalla(DERECHA, 2700, 900, 280, 260)
        self.assertLessEqual(x + 280, 2840)
        self.assertLessEqual(y + 260, 939)
        self.assertGreaterEqual(x, 1440)

    def test_no_tapa_la_barra_de_tareas(self):
        _, y = dentro_de_pantalla(PRINCIPAL, 100, 800, 280, 260)
        self.assertLessEqual(y + 260, 852)


if __name__ == "__main__":
    unittest.main()
