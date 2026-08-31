"""Pruebas de la aritmética de la contabilidad.

Se lanzan con `python -m unittest discover -s pruebas` y no abren ninguna
ventana: el módulo `calculos` no sabe nada de la interfaz, y esa es justo la
razón de tenerlo separado.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contaxcell import calculos, formato  # noqa: E402
from contaxcell.modelo import (  # noqa: E402
    GASTO, INGRESO,
    Activo, AportacionGratis, Libro, Movimiento, Valoracion,
    es_fecha, nombre_mes, redondea,
)


def libro_de_prueba() -> Libro:
    """Un mes con nómina, tres gastos y una aportación a un fondo."""
    libro = Libro.vacio()
    libro.ajustes.saldo_inicial = 1000.0
    libro.ajustes.objetivo_inversion = 200.0
    libro.activos = [Activo(nombre="Fondo", aportacion_inicial=500.0, valor_mercado=900.0)]
    libro.movimientos = [
        Movimiento(fecha="2026-03-01", descripcion="Nómina", categoria="Sueldo",
                   importe=2000.0, id="m1"),
        Movimiento(fecha="2026-03-05", descripcion="Alquiler",
                   categoria="Vivienda y Suministros", importe=700.0, id="m2"),
        Movimiento(fecha="2026-03-10", descripcion="Súper",
                   categoria="Productos Básicos", importe=120.0, id="m3"),
        Movimiento(fecha="2026-03-20", descripcion="Aportación",
                   categoria="Inversión", importe=300.0, activo="Fondo", id="m4"),
        Movimiento(fecha="2026-04-02", descripcion="Cena", categoria="Comer fuera",
                   importe=45.5, id="m5"),
    ]
    libro.aportaciones_gratis = [
        AportacionGratis(fecha="2026-03-31", activo="Fondo", concepto="Cashback",
                         importe=10.0, id="g1"),
    ]
    libro.historico = [
        Valoracion(fecha="2026-03-31", valor_mercado=830.0, id="v1"),
        Valoracion(fecha="2026-04-30", valor_mercado=900.0, id="v2"),
    ]
    return libro


class PruebasRedondeo(unittest.TestCase):
    def test_medio_centimo_sube(self):
        # El round de Python daría 2.67 aquí, que no es lo que espera nadie
        # mirando una cuenta.
        self.assertEqual(redondea(2.675), 2.68)
        self.assertEqual(redondea(0.125), 0.13)

    def test_valores_imposibles_valen_cero(self):
        self.assertEqual(redondea(None), 0.0)
        self.assertEqual(redondea("hola"), 0.0)
        self.assertEqual(redondea(float("inf")), 0.0)

    def test_no_se_acumula_basura(self):
        total = 0.0
        for _ in range(1000):
            total = redondea(total + 0.1)
        self.assertEqual(total, 100.0)


class PruebasSaldo(unittest.TestCase):
    def setUp(self):
        self.libro = libro_de_prueba()

    def test_saldo_resta_gastos_e_inversion(self):
        # 1000 + 2000 − 700 − 120 − 300 − 45,50
        self.assertEqual(calculos.saldo_banco(self.libro), 1834.5)

    def test_balance_acumulado_termina_en_el_saldo(self):
        filas = calculos.con_balance(self.libro)
        self.assertEqual(len(filas), 5)
        self.assertEqual(filas[0].balance, 3000.0)
        self.assertEqual(filas[-1].balance, calculos.saldo_banco(self.libro))

    def test_balance_va_de_antiguo_a_reciente(self):
        fechas = [f.fecha for f in calculos.con_balance(self.libro)]
        self.assertEqual(fechas, sorted(fechas))

    def test_saldo_hasta_una_fecha(self):
        self.assertEqual(calculos.saldo_hasta(self.libro, "2026-03-31"), 1880.0)

    def test_categoria_borrada_cuenta_como_gasto(self):
        # Si desaparece la categoría, el movimiento sigue restando: nunca
        # puede inflar el saldo por sorpresa.
        self.libro.categorias = [c for c in self.libro.categorias if c.nombre != "Sueldo"]
        self.assertEqual(calculos.saldo_banco(self.libro), -2165.5)


class PruebasTotales(unittest.TestCase):
    def setUp(self):
        self.totales = calculos.totales_del_mes(libro_de_prueba(), "2026-03")

    def test_reparto_por_tipo(self):
        self.assertEqual(self.totales.ingresos, 2000.0)
        self.assertEqual(self.totales.gastos, 820.0)
        self.assertEqual(self.totales.inversion, 300.0)

    def test_el_ahorro_no_descuenta_la_inversion(self):
        # Es la regla de toda la aplicación: invertir no es gastar.
        self.assertEqual(self.totales.ahorro, 1180.0)

    def test_el_flujo_neto_si_la_descuenta(self):
        self.assertEqual(self.totales.flujo_neto, 880.0)

    def test_tasa_de_ahorro(self):
        self.assertAlmostEqual(self.totales.tasa_ahorro, 0.59)

    def test_mes_sin_datos(self):
        vacio = calculos.totales_del_mes(libro_de_prueba(), "2026-01")
        self.assertFalse(vacio.hay_datos)
        self.assertEqual(vacio.tasa_ahorro, 0.0)


class PruebasResumenAnual(unittest.TestCase):
    def setUp(self):
        self.resumen = calculos.resumen_anual(libro_de_prueba(), 2026)

    def test_siempre_doce_meses(self):
        self.assertEqual(len(self.resumen.tramos), 12)
        self.assertEqual(self.resumen.meses_con_datos, 2)

    def test_saldo_a_fin_de_mes(self):
        por_clave = {m.clave: m for m in self.resumen.tramos}
        self.assertEqual(por_clave["2026-02"].saldo_final, 1000.0)
        self.assertEqual(por_clave["2026-03"].saldo_final, 1880.0)
        self.assertEqual(por_clave["2026-04"].saldo_final, 1834.5)

    def test_febrero_cierra_bien_pese_a_tener_28_dias(self):
        # El tope de mes se construye con «-31» a propósito; conviene que
        # alguien avise si eso deja de funcionar.
        febrero = next(m for m in self.resumen.tramos if m.clave == "2026-02")
        self.assertEqual(febrero.saldo_final, 1000.0)

    def test_reparto_de_gastos_ordenado_y_al_cien_por_cien(self):
        filas = [f for f in self.resumen.gasto.filas if f.importe]
        self.assertEqual([f.nombre for f in filas],
                         ["Vivienda y Suministros", "Productos Básicos", "Comer fuera"])
        self.assertAlmostEqual(sum(f.porcentaje for f in filas), 1.0)

    def test_la_inversion_no_aparece_entre_los_gastos(self):
        nombres = [f.nombre for f in self.resumen.gasto.filas]
        self.assertNotIn("Inversión", nombres)

    def test_categoria_desaparecida_sigue_sumando(self):
        libro = libro_de_prueba()
        libro.categorias = [c for c in libro.categorias if c.nombre != "Comer fuera"]
        resumen = calculos.resumen_anual(libro, 2026)
        huerfana = next(f for f in resumen.gasto.filas if f.nombre == "Comer fuera")
        self.assertEqual(huerfana.importe, 45.5)


class PruebasResumenPeriodo(unittest.TestCase):
    """El resumen mirando un mes, un año o varios.

    Lo que hay que vigilar es que las medias sigan siendo por mes aunque los
    tramos sean años: dividir 30.000 € entre tres años daría 10.000 «al mes».
    """

    def varios_anios(self) -> Libro:
        libro = libro_de_prueba()
        libro.movimientos.append(
            Movimiento(fecha="2025-06-01", descripcion="Nómina vieja",
                       categoria="Sueldo", importe=1500.0, id="m0"))
        libro.movimientos.append(
            Movimiento(fecha="2025-06-15", descripcion="Alquiler viejo",
                       categoria="Vivienda y Suministros", importe=600.0, id="m0b"))
        return libro

    def test_meses_entre(self):
        self.assertEqual(calculos.meses_entre("2026-11", "2027-02"),
                         ["2026-11", "2026-12", "2027-01", "2027-02"])

    def test_meses_entre_al_reves_no_da_nada(self):
        self.assertEqual(calculos.meses_entre("2026-05", "2026-01"), [])

    def test_un_mes_suelto_es_un_solo_tramo(self):
        resumen = calculos.resumen_periodo(libro_de_prueba(), "2026-03", "2026-03")

        self.assertEqual(len(resumen.tramos), 1)
        self.assertEqual(resumen.total.ingresos, 2000.0)
        self.assertEqual(resumen.total.gastos, 820.0)
        self.assertEqual(resumen.total.inversion, 300.0)

    def test_el_mes_de_al_lado_no_se_cuela(self):
        resumen = calculos.resumen_periodo(libro_de_prueba(), "2026-03", "2026-03")
        self.assertNotIn("Comer fuera", [f.nombre for f in resumen.gasto.filas
                                         if f.importe])

    def test_varios_anios_van_por_anios(self):
        resumen = calculos.resumen_periodo(self.varios_anios(), "2025-01", "2026-12",
                                           particion=calculos.POR_ANIOS)

        self.assertEqual([t.nombre for t in resumen.tramos], ["2025", "2026"])
        self.assertEqual(resumen.tramos[0].totales.ingresos, 1500.0)
        self.assertEqual(resumen.tramos[1].totales.ingresos, 2000.0)
        self.assertEqual(resumen.total.ingresos, 3500.0)

    def test_las_medias_siguen_siendo_por_mes(self):
        # Tres meses con datos entre los dos años, no dos años.
        indicadores = calculos.indicadores_de(self.varios_anios(), "2025-01", "2026-12",
                                              particion=calculos.POR_ANIOS)
        self.assertEqual(indicadores.meses_con_datos, 3)
        self.assertEqual(indicadores.gasto_medio,
                         calculos.redondea((820.0 + 45.5 + 600.0) / 3))

    def test_el_anio_de_mayor_gasto(self):
        indicadores = calculos.indicadores_de(self.varios_anios(), "2025-01", "2026-12",
                                              particion=calculos.POR_ANIOS)
        self.assertEqual(indicadores.tramo_mayor_gasto, "2026")

    def test_con_varios_anios_el_mes_lleva_el_anio_puesto(self):
        # «enero» a secas no diría de cuál de los dos.
        resumen = calculos.resumen_periodo(self.varios_anios(), "2025-01", "2026-12")
        self.assertEqual(resumen.tramos[0].nombre, "enero 2025")
        self.assertEqual(resumen.tramos[0].corto, "ene 25")

    def test_el_saldo_de_cada_anio_es_el_de_fin_de_anio(self):
        resumen = calculos.resumen_periodo(self.varios_anios(), "2025-01", "2026-12",
                                           particion=calculos.POR_ANIOS)
        self.assertEqual(resumen.tramos[0].saldo_final,
                         calculos.saldo_hasta(self.varios_anios(), "2025-12-31"))

    def test_mayor_gasto_del_periodo(self):
        mayor = calculos.mayor_gasto_entre(libro_de_prueba(), "2026-01", "2026-12")
        self.assertEqual(mayor.descripcion, "Alquiler")

    def test_el_mayor_gasto_no_es_la_inversion(self):
        # La aportación de 300 € sale del banco, pero no es un gasto.
        libro = libro_de_prueba()
        libro.movimientos = [m for m in libro.movimientos if m.categoria != "Sueldo"]
        libro.movimientos.append(Movimiento(fecha="2026-03-25", descripcion="Fondo gordo",
                                            categoria="Inversión", importe=5000.0,
                                            id="mx"))
        mayor = calculos.mayor_gasto_entre(libro, "2026-01", "2026-12")
        self.assertEqual(mayor.descripcion, "Alquiler")

    def test_sin_gastos_no_hay_mayor(self):
        self.assertIsNone(calculos.mayor_gasto_entre(libro_de_prueba(), "2020-01",
                                                     "2020-12"))

    def test_un_mes_partido_en_dias(self):
        resumen = calculos.resumen_periodo(libro_de_prueba(), "2026-03", "2026-03",
                                           calculos.POR_DIAS)

        self.assertEqual(len(resumen.tramos), 31)
        con_datos = [t for t in resumen.tramos if t.hay_datos]
        self.assertEqual([t.clave for t in con_datos],
                         ["2026-03-01", "2026-03-05", "2026-03-10", "2026-03-20"])

    def test_febrero_tiene_los_dias_que_tiene(self):
        corto = calculos.resumen_periodo(libro_de_prueba(), "2026-02", "2026-02",
                                         calculos.POR_DIAS)
        bisiesto = calculos.resumen_periodo(libro_de_prueba(), "2028-02", "2028-02",
                                            calculos.POR_DIAS)
        self.assertEqual(len(corto.tramos), 28)
        self.assertEqual(len(bisiesto.tramos), 29)

    def test_el_dia_lleva_el_dia_de_la_semana(self):
        resumen = calculos.resumen_periodo(libro_de_prueba(), "2026-03", "2026-03",
                                           calculos.POR_DIAS)
        # El 1 de marzo de 2026 cae en domingo.
        self.assertEqual(resumen.tramos[0].nombre, "dom 1")
        self.assertEqual(resumen.tramos[0].corto, "1")

    def test_el_saldo_de_cada_dia(self):
        resumen = calculos.resumen_periodo(libro_de_prueba(), "2026-03", "2026-03",
                                           calculos.POR_DIAS)
        por_clave = {t.clave: t for t in resumen.tramos}
        self.assertEqual(por_clave["2026-03-01"].saldo_final, 3000.0)
        self.assertEqual(por_clave["2026-03-31"].saldo_final, 1880.0)

    def test_los_dias_suman_lo_mismo_que_el_mes(self):
        libro = libro_de_prueba()
        por_dias = calculos.resumen_periodo(libro, "2026-03", "2026-03",
                                            calculos.POR_DIAS)
        self.assertEqual(calculos.redondea(sum(t.totales.gastos
                                               for t in por_dias.tramos)),
                         calculos.totales_del_mes(libro, "2026-03").gastos)

    def test_las_medias_de_un_mes_no_se_dividen_entre_dias(self):
        # Treinta y un tramos, pero un solo mes: la media al mes es el total.
        indicadores = calculos.indicadores_de(libro_de_prueba(), "2026-03", "2026-03",
                                              calculos.POR_DIAS)
        self.assertEqual(indicadores.meses_con_datos, 1)
        self.assertEqual(indicadores.gasto_medio, 820.0)

    def test_el_anio_entero_da_lo_mismo_que_antes(self):
        libro = libro_de_prueba()
        por_periodo = calculos.resumen_periodo(libro, "2026-01", "2026-12")
        anual = calculos.resumen_anual(libro, 2026)

        self.assertEqual(len(por_periodo.tramos), len(anual.tramos))
        self.assertEqual(por_periodo.total.gastos, anual.total.gastos)
        self.assertEqual(por_periodo.meses_con_datos, anual.meses_con_datos)


class PruebasPresupuesto(unittest.TestCase):
    def setUp(self):
        self.presupuesto = calculos.presupuesto_del_mes(libro_de_prueba(), "2026-03")

    def test_solo_lista_categorias_de_gasto(self):
        nombres = [f.nombre for f in self.presupuesto.filas]
        self.assertNotIn("Sueldo", nombres)
        self.assertNotIn("Inversión", nombres)

    def test_disponible_y_consumido(self):
        vivienda = next(f for f in self.presupuesto.filas
                        if f.nombre == "Vivienda y Suministros")
        self.assertEqual(vivienda.presupuesto, 700.0)
        self.assertEqual(vivienda.real, 700.0)
        self.assertEqual(vivienda.disponible, 0.0)
        self.assertEqual(vivienda.consumido, 1.0)

    def test_sin_tope_pero_con_gasto_se_marca_como_pasado(self):
        fila = calculos.FilaPresupuesto(nombre="X", presupuesto=0.0, real=30.0)
        self.assertEqual(fila.consumido, float("inf"))

    def test_sin_tope_ni_gasto_no_consume_nada(self):
        fila = calculos.FilaPresupuesto(nombre="X", presupuesto=0.0, real=0.0)
        self.assertEqual(fila.consumido, 0.0)

    def test_objetivo_de_inversion(self):
        self.assertEqual(self.presupuesto.aportado, 300.0)
        self.assertEqual(self.presupuesto.pendiente, 0.0)

    def test_pendiente_nunca_es_negativo(self):
        presupuesto = calculos.presupuesto_del_mes(libro_de_prueba(), "2026-04")
        self.assertEqual(presupuesto.aportado, 0.0)
        self.assertEqual(presupuesto.pendiente, 200.0)


class PruebasCartera(unittest.TestCase):
    def setUp(self):
        self.cartera = calculos.cartera(libro_de_prueba())

    def test_las_tres_formas_de_aportar(self):
        fondo = self.cartera.activos[0]
        self.assertEqual(fondo.aportacion_inicial, 500.0)
        self.assertEqual(fondo.aportado_banco, 300.0)
        self.assertEqual(fondo.aportado_gratis, 10.0)
        self.assertEqual(fondo.total_aportado, 810.0)

    def test_lo_generado_es_solo_lo_del_mercado(self):
        # 900 de valor menos 810 aportados: ni el cashback ni lo que puso él
        # cuentan como rentabilidad.
        self.assertEqual(self.cartera.generado, 90.0)
        self.assertAlmostEqual(self.cartera.rentabilidad, 90 / 810)

    def test_ganado_sin_poner_dinero(self):
        self.assertEqual(self.cartera.ganado_sin_poner, 100.0)

    def test_aportacion_sin_activo_se_avisa(self):
        libro = libro_de_prueba()
        libro.movimiento("m4").activo = ""
        cartera = calculos.cartera(libro)
        self.assertEqual(cartera.sin_asignar_banco, 300.0)
        self.assertEqual(cartera.activos[0].aportado_banco, 0.0)

    def test_historico_acumula_hasta_cada_fecha(self):
        primero, segundo = self.cartera.historico
        # A 31 de marzo ya estaban dentro los 500 iniciales, los 300 del banco
        # y los 10 de cashback.
        self.assertEqual(primero.aportado, 810.0)
        self.assertEqual(primero.generado, 20.0)
        self.assertEqual(segundo.aportado, 810.0)
        self.assertEqual(segundo.generado, 90.0)

    def test_historico_ordenado_por_fecha(self):
        fechas = [p.fecha for p in self.cartera.historico]
        self.assertEqual(fechas, sorted(fechas))

    def test_cartera_vacia_no_divide_por_cero(self):
        cartera = calculos.cartera(Libro.vacio())
        self.assertEqual(cartera.total_aportado, 0.0)
        self.assertEqual(cartera.rentabilidad, 0.0)


class PruebasIndicadores(unittest.TestCase):
    def setUp(self):
        self.indicadores = calculos.indicadores(libro_de_prueba(), 2026)

    def test_medias_sobre_meses_con_datos(self):
        self.assertEqual(self.indicadores.meses_con_datos, 2)
        self.assertEqual(self.indicadores.gasto_medio, 432.75)

    def test_patrimonio_suma_banco_y_cartera(self):
        self.assertEqual(self.indicadores.patrimonio, 1834.5 + 900.0)

    def test_mes_de_mayor_gasto(self):
        self.assertEqual(self.indicadores.tramo_mayor_gasto, "marzo")

    def test_ano_sin_datos_no_revienta(self):
        indicadores = calculos.indicadores(libro_de_prueba(), 2020)
        self.assertEqual(indicadores.meses_con_datos, 0)
        self.assertEqual(indicadores.gasto_medio, 0.0)
        self.assertEqual(indicadores.meses_de_colchon, 0.0)
        self.assertEqual(indicadores.tramo_mayor_gasto, "")


class PruebasModelo(unittest.TestCase):
    def test_ida_y_vuelta_a_json(self):
        original = libro_de_prueba()
        copia = Libro.desde_json(original.a_json())
        self.assertEqual(calculos.saldo_banco(copia), calculos.saldo_banco(original))
        self.assertEqual(len(copia.movimientos), len(original.movimientos))
        self.assertEqual(copia.activos[0].nombre, "Fondo")

    def test_json_basura_da_un_libro_utilizable(self):
        for basura in (None, [], "hola", {"movimientos": "no es una lista"}):
            libro = Libro.desde_json(basura)
            self.assertTrue(libro.categorias)
            self.assertEqual(libro.movimientos, [])

    def test_se_descartan_los_movimientos_sin_fecha_valida(self):
        libro = Libro.desde_json({"movimientos": [
            {"fecha": "2026-03-01", "importe": 10},
            {"fecha": "no es fecha", "importe": 10},
            {"fecha": "2026-13-45", "importe": 10},
            {"importe": 10},
        ]})
        self.assertEqual(len(libro.movimientos), 1)

    def test_el_importe_se_guarda_siempre_positivo(self):
        libro = Libro.desde_json({"movimientos": [
            {"fecha": "2026-03-01", "importe": -25.5, "categoria": "Otros Gastos"},
        ]})
        self.assertEqual(libro.movimientos[0].importe, 25.5)

    def test_no_se_repiten_las_categorias(self):
        libro = Libro.desde_json({"categorias": [
            {"nombre": "Casa", "tipo": GASTO},
            {"nombre": "Casa", "tipo": INGRESO},
            {"nombre": "", "tipo": GASTO},
        ]})
        self.assertEqual([c.nombre for c in libro.categorias], ["Casa"])
        self.assertEqual(libro.categorias[0].tipo, GASTO)

    def test_tipo_desconocido_pasa_a_gasto(self):
        libro = Libro.desde_json({"categorias": [{"nombre": "Rara", "tipo": "Vaya"}]})
        self.assertEqual(libro.categorias[0].tipo, GASTO)

    def test_fechas(self):
        self.assertTrue(es_fecha("2026-02-28"))
        self.assertFalse(es_fecha("2026-02-30"))
        self.assertFalse(es_fecha("2026-2-8"))
        self.assertEqual(nombre_mes("2026-08"), "agosto 2026")
        self.assertEqual(nombre_mes("2026-08", corto=True), "ago 2026")


class PruebasFormato(unittest.TestCase):
    def test_separadores_a_la_espanola(self):
        self.assertEqual(formato.euros(1234.5), "1.234,50 €")
        self.assertEqual(formato.euros(-1234567.89), "-1.234.567,89 €")
        self.assertEqual(formato.euros(0), "0,00 €")

    def test_el_ojo_tapa_todos_los_importes(self):
        formato.ocultar_importes(True)
        try:
            self.assertEqual(formato.euros(1234.5), formato.TAPADO)
            # Las confirmaciones de borrado sí enseñan la cifra: si no, no se
            # sabría qué se está borrando.
            self.assertEqual(formato.euros(1234.5, siempre_visible=True), "1.234,50 €")
        finally:
            formato.ocultar_importes(False)

    def test_lee_lo_que_escribe_el_usuario(self):
        self.assertEqual(formato.texto_a_numero("12,50"), 12.5)
        self.assertEqual(formato.texto_a_numero("12.50"), 12.5)
        self.assertEqual(formato.texto_a_numero("1.234,56"), 1234.56)
        self.assertEqual(formato.texto_a_numero(" 40 € "), 40.0)
        self.assertEqual(formato.texto_a_numero("-8"), -8.0)
        self.assertIsNone(formato.texto_a_numero("dos euros"))
        self.assertIsNone(formato.texto_a_numero(""))

    def test_fechas_escritas_a_mano(self):
        self.assertEqual(formato.texto_a_fecha("24/08/2026"), "2026-08-24")
        self.assertEqual(formato.texto_a_fecha("4-8-26"), "2026-08-04")
        self.assertEqual(formato.texto_a_fecha("2026-08-24"), "2026-08-24")
        self.assertIsNone(formato.texto_a_fecha("31/02/2026"))
        self.assertIsNone(formato.texto_a_fecha("mañana"))

    def test_ida_y_vuelta_de_fecha(self):
        self.assertEqual(formato.texto_a_fecha(formato.fecha_a_texto("2026-01-09")),
                         "2026-01-09")

    def test_signo_visible_en_lo_generado(self):
        self.assertEqual(formato.euros_con_signo(90), "+90,00 €")
        self.assertEqual(formato.euros_con_signo(-90), "-90,00 €")


if __name__ == "__main__":
    unittest.main()
