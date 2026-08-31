"""Pruebas de las cuentas con la gente.

Lo importante aquí no es sumar, que es fácil, sino que las deudas se queden
en su sitio:

- que apuntar que Fulanito te debe veinte no te haga creer que tienes veinte
  euros más en el banco,
- que devolver a trozos no deje nunca un pendiente negativo,
- y que la cuenta con cada persona compense los dos sentidos, que es como se
  salda de verdad.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contaxcell import calculos  # noqa: E402
from contaxcell.modelo import DEBO, ME_DEBEN, Deuda, Libro, Movimiento  # noqa: E402


def libro_con(*deudas: Deuda) -> Libro:
    libro = Libro.vacio()
    libro.ajustes.saldo_inicial = 1000.0
    libro.deudas = list(deudas)
    return libro


def cena(**cambios) -> Deuda:
    datos = dict(quien="Fulanito", sentido=ME_DEBEN, importe=20.0,
                 fecha="2026-03-10", concepto="La cena del sábado", id="d1")
    datos.update(cambios)
    return Deuda(**datos)


class PruebasPendiente(unittest.TestCase):
    def test_recien_creada_se_debe_entera(self):
        self.assertEqual(calculos.pendiente_de(cena()), 20.0)
        self.assertFalse(calculos.esta_saldada(cena()))

    def test_devuelto_a_medias(self):
        self.assertEqual(calculos.pendiente_de(cena(devuelto=8.0)), 12.0)

    def test_devuelta_entera_esta_saldada(self):
        self.assertTrue(calculos.esta_saldada(cena(devuelto=20.0)))

    def test_el_pendiente_nunca_es_negativo(self):
        # Un pendiente negativo se leería como que ahora te deben a ti.
        self.assertEqual(calculos.pendiente_de(cena(devuelto=50.0)), 0.0)


class PruebasAnotarPago(unittest.TestCase):
    def test_un_trozo(self):
        deuda = cena()
        apuntado = calculos.anotar_pago(deuda, 8.0)

        self.assertEqual(apuntado, 8.0)
        self.assertEqual(deuda.devuelto, 8.0)
        self.assertEqual(calculos.pendiente_de(deuda), 12.0)

    def test_dos_trozos_la_saldan(self):
        deuda = cena()
        calculos.anotar_pago(deuda, 8.0)
        calculos.anotar_pago(deuda, 12.0)

        self.assertTrue(calculos.esta_saldada(deuda))

    def test_no_se_pasa_de_lo_que_queda(self):
        deuda = cena()
        apuntado = calculos.anotar_pago(deuda, 50.0)

        self.assertEqual(apuntado, 20.0)
        self.assertEqual(deuda.devuelto, 20.0)

    def test_hasta_el_final(self):
        deuda = cena(devuelto=8.0)
        self.assertEqual(calculos.anotar_pago(deuda, 0, hasta_el_final=True), 12.0)
        self.assertTrue(calculos.esta_saldada(deuda))

    def test_los_centimos_no_se_van(self):
        deuda = cena(importe=0.3)
        calculos.anotar_pago(deuda, 0.1)
        calculos.anotar_pago(deuda, 0.1)
        self.assertEqual(calculos.pendiente_de(deuda), 0.1)


class PruebasResumen(unittest.TestCase):
    def test_separa_los_dos_sentidos(self):
        libro = libro_con(cena(),
                          cena(id="d2", quien="Menganito", sentido=DEBO, importe=50.0))
        resumen = calculos.resumen_deudas(libro)

        self.assertEqual(resumen.te_deben, 20.0)
        self.assertEqual(resumen.debes, 50.0)
        self.assertEqual(resumen.neto, -30.0)

    def test_lo_saldado_no_suma(self):
        libro = libro_con(cena(devuelto=20.0), cena(id="d2", importe=15.0))
        resumen = calculos.resumen_deudas(libro)

        self.assertEqual(resumen.te_deben, 15.0)
        self.assertEqual(resumen.abiertas, 1)
        self.assertEqual(resumen.saldadas, 1)

    def test_solo_cuenta_lo_que_falta(self):
        libro = libro_con(cena(importe=100.0, devuelto=40.0))
        self.assertEqual(calculos.resumen_deudas(libro).te_deben, 60.0)

    def test_cuenta_las_personas_una_sola_vez(self):
        libro = libro_con(cena(), cena(id="d2", concepto="El taxi", importe=10.0),
                          cena(id="d3", quien="Menganito", importe=5.0))
        self.assertEqual(calculos.resumen_deudas(libro).personas, 2)

    def test_sin_deudas_esta_todo_en_paz(self):
        resumen = calculos.resumen_deudas(libro_con())
        self.assertEqual((resumen.te_deben, resumen.debes, resumen.neto), (0.0, 0.0, 0.0))


class PruebasPorPersona(unittest.TestCase):
    def test_junta_lo_de_cada_uno(self):
        libro = libro_con(cena(), cena(id="d2", concepto="El taxi", importe=10.0))
        saldos = calculos.deudas_por_persona(libro)

        self.assertEqual(len(saldos), 1)
        self.assertEqual(saldos[0].quien, "Fulanito")
        self.assertEqual(saldos[0].te_deben, 30.0)
        self.assertEqual(saldos[0].cuantas, 2)

    def test_compensa_los_dos_sentidos(self):
        # Si le debes 20 y te debe 50, no hay dos pagos: hay uno de 30.
        libro = libro_con(cena(importe=50.0),
                          cena(id="d2", sentido=DEBO, importe=20.0))
        saldos = calculos.deudas_por_persona(libro)

        self.assertEqual(len(saldos), 1)
        self.assertEqual(saldos[0].neto, 30.0)

    def test_el_mismo_nombre_en_mayusculas_es_la_misma_persona(self):
        libro = libro_con(cena(quien="Fulanito"),
                          cena(id="d2", quien="fulanito", importe=5.0))
        saldos = calculos.deudas_por_persona(libro)

        self.assertEqual(len(saldos), 1)
        self.assertEqual(saldos[0].quien, "Fulanito")
        self.assertEqual(saldos[0].te_deben, 25.0)

    def test_primero_el_que_mas_te_debe(self):
        libro = libro_con(cena(quien="Ana", importe=10.0),
                          cena(id="d2", quien="Berta", importe=90.0),
                          cena(id="d3", quien="Carlos", sentido=DEBO, importe=40.0))
        self.assertEqual([s.quien for s in calculos.deudas_por_persona(libro)],
                         ["Berta", "Ana", "Carlos"])

    def test_lo_saldado_no_sale(self):
        libro = libro_con(cena(devuelto=20.0))
        self.assertEqual(calculos.deudas_por_persona(libro), [])


class PruebasNoTocanElBanco(unittest.TestCase):
    """La regla de esta pestaña: una deuda es una libreta, no dinero.

    Que te deban veinte euros no es tenerlos. El saldo solo lo mueven los
    movimientos, y por eso saldar una deuda ofrece apuntar uno en vez de
    inventárselo.
    """

    def test_apuntar_deudas_no_cambia_el_saldo(self):
        libro = libro_con()
        antes = calculos.saldo_banco(libro)
        libro.deudas = [cena(importe=500.0),
                        cena(id="d2", sentido=DEBO, importe=300.0)]

        self.assertEqual(calculos.saldo_banco(libro), antes)

    def test_ni_el_ahorro_del_mes(self):
        libro = libro_con(cena(importe=500.0))
        libro.movimientos = [Movimiento(fecha="2026-03-01", categoria="Sueldo",
                                        importe=1000.0)]
        totales = calculos.totales_del_mes(libro, "2026-03")

        self.assertEqual(totales.ingresos, 1000.0)
        self.assertEqual(totales.ahorro, 1000.0)

    def test_el_movimiento_de_un_cobro_si_lo_mueve(self):
        # Lo que sí cuenta es el movimiento que se apunta al cobrar, y ese es
        # un movimiento normal y corriente.
        libro = libro_con(cena())
        libro.movimientos = [Movimiento(fecha="2026-03-20", categoria="Otros Ingresos",
                                        importe=20.0, origen="d1")]
        self.assertEqual(calculos.saldo_banco(libro), 1020.0)


class PruebasGuardado(unittest.TestCase):
    def test_ida_y_vuelta(self):
        libro = libro_con(cena(nota="Pagué yo la cuenta entera.\nDijo que el viernes."))
        vuelta = Libro.desde_json(libro.a_json())

        self.assertEqual(len(vuelta.deudas), 1)
        guardada = vuelta.deudas[0]
        self.assertEqual(guardada.quien, "Fulanito")
        self.assertEqual(guardada.importe, 20.0)
        self.assertEqual(guardada.nota.splitlines()[1], "Dijo que el viernes.")

    def test_se_descarta_lo_que_no_se_puede_arreglar(self):
        crudo = {"deudas": [
            {"quien": "", "fecha": "2026-03-10"},
            {"quien": "Sin fecha", "fecha": ""},
            {"quien": "Buena", "fecha": "2026-03-10"},
        ]}
        self.assertEqual([d.quien for d in Libro.desde_json(crudo).deudas], ["Buena"])

    def test_un_sentido_inventado_cae_en_me_deben(self):
        crudo = {"deudas": [{"quien": "Fulanito", "fecha": "2026-03-10",
                             "sentido": "Ni idea"}]}
        self.assertEqual(Libro.desde_json(crudo).deudas[0].sentido, ME_DEBEN)

    def test_devuelto_de_mas_se_recorta(self):
        crudo = {"deudas": [{"quien": "Fulanito", "fecha": "2026-03-10",
                             "importe": 20, "devuelto": 999}]}
        self.assertEqual(Libro.desde_json(crudo).deudas[0].devuelto, 20.0)

    def test_los_importes_negativos_se_enderezan(self):
        crudo = {"deudas": [{"quien": "Fulanito", "fecha": "2026-03-10",
                             "importe": -20}]}
        self.assertEqual(Libro.desde_json(crudo).deudas[0].importe, 20.0)

    def test_un_libro_viejo_sin_deudas_carga_igual(self):
        self.assertEqual(Libro.desde_json({"movimientos": []}).deudas, [])


if __name__ == "__main__":
    unittest.main()
