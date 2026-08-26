"""Pruebas de los pagos periódicos.

Lo que se comprueba aquí no es que sume bien, que eso es fácil, sino las tres
cosas que se rompen solas si no se vigilan:

- que un recibo del día 31 no se quede en el 28 para siempre después de pasar
  por febrero,
- que apuntar dos veces no duplique nada,
- y que borrar a mano un movimiento que salió solo no lo resucite al abrir.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contaxcell import calculos  # noqa: E402
from contaxcell.modelo import (  # noqa: E402
    ANUAL, GASTO, INVERSION, MENSUAL, SEMANAL, TRIMESTRAL,
    Libro, Periodico, suma_dias, suma_meses,
)


def libro_con(*periodicos: Periodico) -> Libro:
    libro = Libro.vacio()
    libro.ajustes.saldo_inicial = 1000.0
    libro.periodicos = list(periodicos)
    return libro


def alquiler(**cambios) -> Periodico:
    datos = dict(nombre="Alquiler", categoria="Vivienda y Suministros",
                 importe=700.0, periodo=MENSUAL, desde="2026-01-05", id="p1")
    datos.update(cambios)
    return Periodico(**datos)


class PruebasFechas(unittest.TestCase):
    def test_suma_dias(self):
        self.assertEqual(suma_dias("2026-01-05", 7), "2026-01-12")
        self.assertEqual(suma_dias("2026-12-28", 7), "2027-01-04")

    def test_suma_meses_cambia_de_anio(self):
        self.assertEqual(suma_meses("2026-11-15", 2), "2027-01-15")
        self.assertEqual(suma_meses("2026-03-10", 12), "2027-03-10")

    def test_el_dia_31_no_se_sale_del_mes(self):
        # Sumar un mes al 31 de enero no puede dar el 31 de febrero.
        self.assertEqual(suma_meses("2026-01-31", 1), "2026-02-28")

    def test_febrero_bisiesto(self):
        self.assertEqual(suma_meses("2028-01-31", 1), "2028-02-29")

    def test_fecha_invalida_no_revienta(self):
        self.assertEqual(suma_meses("", 1), "")
        self.assertEqual(suma_dias("no es una fecha", 1), "")


class PruebasVencimientos(unittest.TestCase):
    def test_mensual(self):
        fechas = calculos.vencimientos(alquiler(), "2026-04-30")
        self.assertEqual(fechas, ["2026-01-05", "2026-02-05", "2026-03-05", "2026-04-05"])

    def test_no_pasa_del_tope(self):
        # El de mayo cae fuera: la fecha tope es el 30 de abril.
        self.assertNotIn("2026-05-05", calculos.vencimientos(alquiler(), "2026-04-30"))

    def test_semanal_cae_siempre_el_mismo_dia(self):
        gimnasio = alquiler(periodo=SEMANAL, desde="2026-01-05")
        fechas = calculos.vencimientos(gimnasio, "2026-02-01")
        self.assertEqual(fechas[:4], ["2026-01-05", "2026-01-12",
                                      "2026-01-19", "2026-01-26"])

    def test_trimestral(self):
        seguro = alquiler(periodo=TRIMESTRAL, desde="2026-01-15")
        self.assertEqual(calculos.vencimientos(seguro, "2026-12-31"),
                         ["2026-01-15", "2026-04-15", "2026-07-15", "2026-10-15"])

    def test_anual(self):
        seguro = alquiler(periodo=ANUAL, desde="2024-06-01")
        self.assertEqual(calculos.vencimientos(seguro, "2026-12-31"),
                         ["2024-06-01", "2025-06-01", "2026-06-01"])

    def test_el_31_vuelve_al_31_despues_de_febrero(self):
        # Lo importante: la cuenta se hace desde el primer pago, no desde el
        # anterior. Si se encadenara, después de febrero se quedaría en el 28
        # para el resto de su vida.
        recibo = alquiler(desde="2026-01-31")
        fechas = calculos.vencimientos(recibo, "2026-04-30")
        self.assertEqual(fechas, ["2026-01-31", "2026-02-28",
                                  "2026-03-31", "2026-04-30"])

    def test_recorte_por_abajo(self):
        fechas = calculos.vencimientos(alquiler(), "2026-04-30", desde="2026-03-01")
        self.assertEqual(fechas, ["2026-03-05", "2026-04-05"])

    def test_antes_del_primer_pago_no_hay_nada(self):
        self.assertEqual(calculos.vencimientos(alquiler(), "2025-12-31"), [])

    def test_sin_fecha_de_inicio_no_hay_nada(self):
        self.assertEqual(calculos.vencimientos(alquiler(desde=""), "2026-12-31"), [])

    def test_proximo_vencimiento(self):
        self.assertEqual(calculos.proximo_vencimiento(alquiler(), "2026-03-06"),
                         "2026-04-05")

    def test_proximo_vencimiento_el_mismo_dia_cuenta(self):
        self.assertEqual(calculos.proximo_vencimiento(alquiler(), "2026-03-05"),
                         "2026-03-05")


class PruebasApuntar(unittest.TestCase):
    def test_crea_los_movimientos(self):
        libro = libro_con(alquiler())
        creados = calculos.apuntar_pendientes(libro, "2026-03-31")

        self.assertEqual(len(creados), 3)
        self.assertEqual([m.fecha for m in creados],
                         ["2026-01-05", "2026-02-05", "2026-03-05"])
        self.assertEqual(libro.movimientos, creados)

    def test_el_movimiento_hereda_lo_del_periodico(self):
        libro = libro_con(alquiler())
        creado = calculos.apuntar_pendientes(libro, "2026-01-31")[0]

        self.assertEqual(creado.descripcion, "Alquiler")
        self.assertEqual(creado.categoria, "Vivienda y Suministros")
        self.assertEqual(creado.importe, 700.0)
        self.assertEqual(creado.origen, "p1")

    def test_apuntar_dos_veces_no_duplica(self):
        libro = libro_con(alquiler())
        calculos.apuntar_pendientes(libro, "2026-03-31")
        segunda = calculos.apuntar_pendientes(libro, "2026-03-31")

        self.assertEqual(segunda, [])
        self.assertEqual(len(libro.movimientos), 3)

    def test_sigue_por_donde_iba(self):
        libro = libro_con(alquiler())
        calculos.apuntar_pendientes(libro, "2026-02-28")
        nuevos = calculos.apuntar_pendientes(libro, "2026-04-30")

        self.assertEqual([m.fecha for m in nuevos], ["2026-03-05", "2026-04-05"])

    def test_lo_borrado_a_mano_no_resucita(self):
        # Es lo que haría insoportable la pestaña: borras el recibo que no
        # tocaba, cierras, abres, y vuelve a estar ahí.
        libro = libro_con(alquiler())
        calculos.apuntar_pendientes(libro, "2026-03-31")
        libro.movimientos = [m for m in libro.movimientos if m.fecha != "2026-02-05"]

        self.assertEqual(calculos.apuntar_pendientes(libro, "2026-03-31"), [])
        self.assertEqual(len(libro.movimientos), 2)

    def test_nunca_apunta_por_delante(self):
        libro = libro_con(alquiler())
        calculos.apuntar_pendientes(libro, "2026-02-10")

        self.assertTrue(all(m.fecha <= "2026-02-10" for m in libro.movimientos))

    def test_apagado_no_apunta(self):
        libro = libro_con(alquiler(encendido=False))
        self.assertEqual(calculos.apuntar_pendientes(libro, "2026-12-31"), [])

    def test_deja_la_marca_de_por_donde_va(self):
        libro = libro_con(alquiler())
        calculos.apuntar_pendientes(libro, "2026-03-31")
        self.assertEqual(libro.periodicos[0].apuntado_hasta, "2026-03-05")

    def test_la_categoria_manda_el_tipo(self):
        # Una aportación periódica a la cartera sale del banco, pero no es un
        # gasto: el ahorro no tiene que bajar por su culpa.
        libro = libro_con(alquiler(nombre="Aportación", categoria="Inversión",
                                   importe=200.0))
        calculos.apuntar_pendientes(libro, "2026-01-31")
        totales = calculos.totales_del_mes(libro, "2026-01")

        self.assertEqual(totales.inversion, 200.0)
        self.assertEqual(totales.gastos, 0.0)
        self.assertEqual(calculos.saldo_banco(libro), 800.0)


class PruebasFechaDeFin(unittest.TestCase):
    """Lo que se acaba solo: las doce cuotas de un préstamo, un seguro que no
    se renueva. Al llegar a su fecha para, sin tener que acordarse."""

    def prestamo(self, **cambios) -> Periodico:
        # Doce cuotas: de enero a diciembre de 2026, y se acabó.
        return alquiler(nombre="Préstamo del coche", importe=180.0,
                        desde="2026-01-10", hasta="2026-12-10", **cambios)

    def test_no_pasa_de_la_fecha_de_fin(self):
        fechas = calculos.vencimientos(self.prestamo(), "2027-12-31")

        self.assertEqual(len(fechas), 12)
        self.assertEqual(fechas[0], "2026-01-10")
        self.assertEqual(fechas[-1], "2026-12-10")

    def test_el_ultimo_pago_se_paga(self):
        # La fecha de fin es el día de la última cuota, no el día después.
        self.assertIn("2026-12-10", calculos.vencimientos(self.prestamo(), "2027-12-31"))

    def test_deja_de_apuntar_solo(self):
        libro = libro_con(self.prestamo())
        calculos.apuntar_pendientes(libro, "2027-06-30")
        despues = calculos.apuntar_pendientes(libro, "2028-12-31")

        self.assertEqual(despues, [])
        self.assertEqual(len(libro.movimientos), 12)
        self.assertEqual(calculos.redondea(sum(m.importe for m in libro.movimientos)),
                         2160.0)

    def test_sin_fecha_de_fin_no_se_acaba(self):
        self.assertEqual(len(calculos.vencimientos(alquiler(), "2027-12-31")), 24)

    def test_no_hay_proximo_pago_una_vez_terminado(self):
        self.assertEqual(calculos.proximo_vencimiento(self.prestamo(), "2027-01-01"), "")

    def test_el_proximo_pago_mientras_dura(self):
        self.assertEqual(calculos.proximo_vencimiento(self.prestamo(), "2026-06-11"),
                         "2026-07-10")

    def test_esta_vigente_mientras_no_llegue_la_fecha(self):
        prestamo = self.prestamo()
        self.assertTrue(calculos.esta_vigente(prestamo, "2026-06-01"))
        # El propio día del último pago todavía cuenta.
        self.assertTrue(calculos.esta_vigente(prestamo, "2026-12-10"))
        self.assertFalse(calculos.esta_vigente(prestamo, "2026-12-11"))

    def test_apagado_no_esta_vigente_aunque_no_haya_terminado(self):
        self.assertFalse(calculos.esta_vigente(self.prestamo(encendido=False),
                                               "2026-06-01"))

    def test_lo_terminado_no_suma_en_el_mes(self):
        libro = libro_con(alquiler(), self.prestamo())

        durante = calculos.resumen_periodicos(libro, "2026-06-01")
        self.assertEqual(durante.gasto, 880.0)
        self.assertEqual(durante.encendidos, 2)
        self.assertEqual(durante.terminados, 0)

        despues = calculos.resumen_periodicos(libro, "2027-06-01")
        self.assertEqual(despues.gasto, 700.0)
        self.assertEqual(despues.encendidos, 1)
        self.assertEqual(despues.terminados, 1)
        self.assertEqual(despues.total, 2)

    def test_terminado_y_apagado_se_cuentan_por_separado(self):
        libro = libro_con(alquiler(), self.prestamo(),
                          alquiler(id="p3", nombre="Netflix", importe=13.99,
                                   encendido=False))
        resumen = calculos.resumen_periodicos(libro, "2027-06-01")

        self.assertEqual((resumen.encendidos, resumen.terminados, resumen.apagados),
                         (1, 1, 1))

    def test_se_guarda_y_se_recupera(self):
        vuelto = Libro.desde_json(libro_con(self.prestamo()).a_json())
        self.assertEqual(vuelto.periodicos[0].hasta, "2026-12-10")

    def test_una_fecha_de_fin_imposible_se_descarta(self):
        # Antes del primer pago no describe nada: mejor sin fin que sin poder
        # apuntar nunca.
        libro = Libro.desde_json({"periodicos": [
            {"nombre": "Raro", "desde": "2026-06-01", "hasta": "2026-01-01"},
        ]})
        self.assertEqual(libro.periodicos[0].hasta, "")

    def test_una_fecha_de_fin_que_no_es_fecha_se_descarta(self):
        libro = Libro.desde_json({"periodicos": [
            {"nombre": "Raro", "desde": "2026-06-01", "hasta": "cuando sea"},
        ]})
        self.assertEqual(libro.periodicos[0].hasta, "")


class PruebasApagarYEncender(unittest.TestCase):
    """Lo que pasa al apagar uno y volver a encenderlo meses después."""

    def test_al_reencender_no_se_recuperan_los_meses_apagados(self):
        # Te das de baja del gimnasio en marzo y vuelves en agosto: los meses
        # de en medio no los pagaste, así que no se apuntan.
        libro = libro_con(alquiler(nombre="Gimnasio", importe=34.99))
        calculos.apuntar_pendientes(libro, "2026-03-31")
        gimnasio = libro.periodicos[0]

        gimnasio.encendido = False
        calculos.saltar_lo_pasado(gimnasio, "2026-08-26")
        gimnasio.encendido = True
        nuevos = calculos.apuntar_pendientes(libro, "2026-08-26")

        self.assertEqual(nuevos, [])
        self.assertEqual(len(libro.movimientos), 3)

    def test_al_reencender_sigue_apuntando_a_partir_de_hoy(self):
        libro = libro_con(alquiler(nombre="Gimnasio", importe=34.99))
        gimnasio = libro.periodicos[0]
        calculos.saltar_lo_pasado(gimnasio, "2026-08-26")
        nuevos = calculos.apuntar_pendientes(libro, "2026-09-30")

        self.assertEqual([m.fecha for m in nuevos], ["2026-09-05"])

    def test_apagar_y_encender_el_mismo_dia_no_repite(self):
        # La marca solo puede ir hacia delante: si retrocediera, el pago de
        # hoy se apuntaría dos veces.
        libro = libro_con(alquiler())
        calculos.apuntar_pendientes(libro, "2026-03-05")
        self.assertEqual(libro.periodicos[0].apuntado_hasta, "2026-03-05")

        calculos.saltar_lo_pasado(libro.periodicos[0], "2026-03-05")

        self.assertEqual(libro.periodicos[0].apuntado_hasta, "2026-03-05")
        self.assertEqual(calculos.apuntar_pendientes(libro, "2026-03-05"), [])

    def test_saltar_lo_pasado_sin_nada_pasado_no_toca_nada(self):
        recien = alquiler(desde="2026-09-05")
        calculos.saltar_lo_pasado(recien, "2026-08-26")
        self.assertEqual(recien.apuntado_hasta, "")


class PruebasResumen(unittest.TestCase):
    def test_coste_mensual_de_un_anual(self):
        seguro = alquiler(periodo=ANUAL, importe=240.0)
        self.assertEqual(calculos.coste_mensual(seguro), 20.0)

    def test_coste_mensual_de_un_trimestral(self):
        self.assertEqual(calculos.coste_mensual(alquiler(periodo=TRIMESTRAL,
                                                         importe=150.0)), 50.0)

    def test_coste_mensual_de_un_mensual_es_el_importe(self):
        self.assertEqual(calculos.coste_mensual(alquiler()), 700.0)

    def test_los_apagados_no_suman(self):
        libro = libro_con(alquiler(), alquiler(id="p2", nombre="Gimnasio",
                                               categoria="Ocio y Caprichos",
                                               importe=40.0, encendido=False))
        resumen = calculos.resumen_periodicos(libro)

        self.assertEqual(resumen.gasto, 700.0)
        self.assertEqual(resumen.encendidos, 1)
        self.assertEqual(resumen.apagados, 1)
        self.assertEqual(resumen.total, 2)

    def test_separa_gasto_de_inversion(self):
        libro = libro_con(alquiler(),
                          alquiler(id="p2", nombre="Aportación",
                                   categoria="Inversión", importe=200.0),
                          alquiler(id="p3", nombre="Nómina", categoria="Sueldo",
                                   importe=2000.0))
        resumen = calculos.resumen_periodicos(libro)

        self.assertEqual(resumen.gasto, 700.0)
        self.assertEqual(resumen.inversion, 200.0)
        self.assertEqual(resumen.ingreso, 2000.0)

    def test_cuenta_los_que_apuntó_cada_uno(self):
        libro = libro_con(alquiler())
        calculos.apuntar_pendientes(libro, "2026-03-31")
        self.assertEqual(calculos.apuntados_por(libro, libro.periodicos[0]), 3)


class PruebasGuardado(unittest.TestCase):
    def test_ida_y_vuelta_por_json(self):
        libro = libro_con(alquiler(activo="Fondo", apuntado_hasta="2026-02-05"))
        vuelto = Libro.desde_json(libro.a_json())

        self.assertEqual(len(vuelto.periodicos), 1)
        guardado = vuelto.periodicos[0]
        self.assertEqual(guardado.nombre, "Alquiler")
        self.assertEqual(guardado.importe, 700.0)
        self.assertEqual(guardado.periodo, MENSUAL)
        self.assertEqual(guardado.desde, "2026-01-05")
        self.assertEqual(guardado.apuntado_hasta, "2026-02-05")
        self.assertEqual(guardado.activo, "Fondo")
        self.assertTrue(guardado.encendido)

    def test_el_origen_del_movimiento_sobrevive(self):
        libro = libro_con(alquiler())
        calculos.apuntar_pendientes(libro, "2026-01-31")
        vuelto = Libro.desde_json(libro.a_json())

        self.assertEqual(vuelto.movimientos[0].origen, "p1")

    def test_se_descarta_lo_que_no_sirve(self):
        # Sin fecha de primer pago no se puede fabricar nada, así que fuera:
        # igual que los movimientos sin fecha.
        crudo = {"periodicos": [
            {"nombre": "Sin fecha", "desde": ""},
            {"nombre": "", "desde": "2026-01-05"},
            {"nombre": "Bueno", "desde": "2026-01-05"},
        ]}
        libro = Libro.desde_json(crudo)

        self.assertEqual([p.nombre for p in libro.periodicos], ["Bueno"])

    def test_un_periodo_inventado_cae_en_mensual(self):
        libro = Libro.desde_json({"periodicos": [
            {"nombre": "Raro", "desde": "2026-01-05", "periodo": "Cada luna llena"},
        ]})
        self.assertEqual(libro.periodicos[0].periodo, MENSUAL)

    def test_un_libro_viejo_sin_periodicos_carga_igual(self):
        libro = Libro.desde_json({"movimientos": []})
        self.assertEqual(libro.periodicos, [])


class PruebasTipos(unittest.TestCase):
    def test_los_tipos_siguen_siendo_los_de_siempre(self):
        # Por si alguien añade un periodo y se olvida de la tabla de pasos.
        from contaxcell.modelo import PASO, PERIODOS, VECES_AL_ANIO
        self.assertEqual(set(PASO), set(PERIODOS))
        self.assertEqual(set(VECES_AL_ANIO), set(PERIODOS))
        self.assertIn(GASTO, (GASTO, INVERSION))


if __name__ == "__main__":
    unittest.main()
