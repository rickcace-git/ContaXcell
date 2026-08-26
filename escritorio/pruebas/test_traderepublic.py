"""Pruebas del lector de extractos de Trade Republic.

La parte que entiende el texto se prueba con filas escritas a mano, tal como
salen del PDF: asi no hace falta guardar un extracto de verdad en el
repositorio, que llevaria dentro el IBAN y el nombre de una persona.

Si hay un PDF a mano (variable CONTAXCELL_EXTRACTO), se prueba tambien con el
archivo entero.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contaxcell import calculos, traderepublic as tr  # noqa: E402
from contaxcell.modelo import INVERSION, Activo, Libro  # noqa: E402


# Tres filas por compra, tal como las escupe el PDF: la fecha con el principio
# de la descripcion, el importe, y el ano con el final y las participaciones.
def filas_compra(dia: str, anio: str, euros: str, titulos: str,
                 isin: str = "IE00B4L5Y983") -> list[str]:
    return [
        f"{dia}  |  Savings plan execution {isin} iShares III plc - iShares Core MSCI",
        f"Operar  |  {euros} €  |  4.895,14 €",
        f"{anio}  |  World UCITS ETF USD (Acc), quantity: {titulos}",
    ]


def filas_interes(dia: str, anio: str, euros: str) -> list[str]:
    return [dia, f"Interés  |  Interest payment  |  {euros} €  |  5.000,00 €", anio]


def filas_bonificacion(dia: str, anio: str, euros: str) -> list[str]:
    return [dia, f"Bonificación  |  Cash reward allocation  |  {euros} €  |  5.000,00 €",
            anio]


EXTRACTO = (
    filas_compra("02 jul", "2026", "100,00", "0.795628")
    + filas_compra("09 jul", "2026", "100,00", "0.797130")
    + filas_interes("01 jul", "2026", "2,47")
    + filas_bonificacion("01 jul", "2026", "0,05")
)


class PruebasLectura(unittest.TestCase):
    def test_saca_las_compras(self):
        lectura = tr.leer_lineas(EXTRACTO)
        self.assertEqual(len(lectura.compras), 2)
        self.assertEqual(lectura.avisos, [])

    def test_la_compra_trae_lo_que_hace_falta(self):
        compra = tr.leer_lineas(EXTRACTO).compras[0]
        self.assertEqual(compra.fecha, "2026-07-02")
        self.assertEqual(compra.importe, 100.0)
        self.assertEqual(compra.titulos, 0.795628)
        self.assertEqual(compra.isin, "IE00B4L5Y983")

    def test_las_participaciones_no_se_redondean_a_dos_decimales(self):
        # Con dos decimales, 0,795628 seria 0,80 y todo saldria torcido.
        self.assertEqual(tr.leer_lineas(EXTRACTO).compras[0].titulos, 0.795628)

    def test_el_precio_pagado_sale_de_la_division(self):
        compra = tr.leer_lineas(EXTRACTO).compras[0]
        self.assertAlmostEqual(compra.precio, 100.0 / 0.795628, places=6)

    def test_el_nombre_se_acorta_al_indice(self):
        # El banco escribe un parrafo; en la tabla tiene que caber.
        self.assertEqual(tr.leer_lineas(EXTRACTO).compras[0].nombre_activo,
                         "MSCI World")

    def test_saca_intereses_y_bonificaciones(self):
        lectura = tr.leer_lineas(EXTRACTO)
        conceptos = sorted(i.concepto for i in lectura.ingresos)
        self.assertEqual(len(lectura.ingresos), 2)
        self.assertIn("Intereses de Trade Republic", conceptos)
        self.assertIn("Bonificación de Trade Republic", conceptos)

    def test_la_fecha_de_un_ingreso_esta_partida_en_dos_filas(self):
        # El dia va encima y el ano debajo: el banco parte la fecha.
        interes = next(i for i in tr.leer_lineas(EXTRACTO).ingresos
                       if i.concepto.startswith("Intereses"))
        self.assertEqual(interes.fecha, "2026-07-01")
        self.assertEqual(interes.importe, 2.47)

    def test_el_periodo_va_de_la_primera_a_la_ultima(self):
        lectura = tr.leer_lineas(EXTRACTO)
        self.assertEqual(lectura.desde, "2026-07-01")
        self.assertEqual(lectura.hasta, "2026-07-09")

    def test_una_compra_a_medias_se_avisa_y_no_se_inventa(self):
        rotas = ["05 jul  |  Savings plan execution IE00B4L5Y983 iShares Core MSCI",
                 "Operar  |  100,00 €  |  4.895,14 €",
                 "2026  |  World UCITS ETF USD (Acc)"]  # sin quantity
        lectura = tr.leer_lineas(rotas)
        self.assertEqual(lectura.compras, [])
        self.assertEqual(len(lectura.avisos), 1)

    def test_un_texto_que_no_es_un_extracto_no_saca_nada(self):
        lectura = tr.leer_lineas(["Hola", "esto no es un extracto"])
        self.assertEqual(lectura.apuntes, [])

    def test_un_pdf_que_no_lo_es_avisa_con_claridad(self):
        with self.assertRaises(tr.NoEsUnExtracto):
            tr.lineas_del_pdf(b"esto no es un pdf")


class PruebasAplicar(unittest.TestCase):
    def libro(self) -> Libro:
        return Libro.vacio()

    def importar(self, libro, lineas=None):
        return tr.aplicar(libro, tr.leer_lineas(lineas or EXTRACTO),
                          categoria_inversion="Inversión",
                          categoria_ingreso="Otros Ingresos",
                          categoria_activo="Indexados")

    def test_apunta_las_compras_como_aportaciones(self):
        libro = self.libro()
        resultado = self.importar(libro)

        self.assertEqual(resultado.compras, 2)
        self.assertEqual(resultado.invertido, 200.0)
        aportaciones = [m for m in libro.movimientos
                        if libro.tipo_de(m.categoria) == INVERSION]
        self.assertEqual(len(aportaciones), 2)
        self.assertEqual(aportaciones[0].titulos, 0.795628)

    def test_crea_el_activo_con_su_categoria_y_su_codigo(self):
        libro = self.libro()
        self.importar(libro)

        self.assertEqual(len(libro.activos), 1)
        activo = libro.activos[0]
        self.assertEqual(activo.nombre, "MSCI World")
        self.assertEqual(activo.categoria, "Indexados")
        self.assertEqual(activo.isin, "IE00B4L5Y983")

    def test_apunta_los_ingresos(self):
        libro = self.libro()
        resultado = self.importar(libro)
        self.assertEqual(resultado.ingresos, 2)
        self.assertEqual(resultado.ingresado, 2.52)

    def test_importar_dos_veces_no_duplica(self):
        # Es lo primero que hace cualquiera sin darse cuenta.
        libro = self.libro()
        self.importar(libro)
        cuantos = len(libro.movimientos)

        segunda = self.importar(libro)

        self.assertEqual(segunda.compras, 0)
        self.assertEqual(segunda.ingresos, 0)
        self.assertEqual(segunda.repetidos, 4)
        self.assertEqual(len(libro.movimientos), cuantos)

    def test_un_extracto_que_se_solapa_solo_trae_lo_nuevo(self):
        libro = self.libro()
        self.importar(libro)
        mas = EXTRACTO + filas_compra("16 jul", "2026", "100,00", "0.792958")

        resultado = self.importar(libro, mas)

        self.assertEqual(resultado.compras, 1)
        self.assertEqual(resultado.repetidos, 4)

    def test_no_crea_un_activo_nuevo_si_ya_lo_conoce_por_el_codigo(self):
        libro = self.libro()
        libro.activos = [Activo(nombre="Mi fondo de siempre", isin="IE00B4L5Y983")]

        resultado = self.importar(libro)

        self.assertEqual(len(libro.activos), 1)
        self.assertEqual(resultado.activos_nuevos, [])
        self.assertEqual(libro.movimientos[0].activo, "Mi fondo de siempre")

    def test_al_activo_que_ya_estaba_se_le_apunta_el_codigo(self):
        libro = self.libro()
        libro.activos = [Activo(nombre="MSCI World")]
        self.importar(libro)
        self.assertEqual(libro.activos[0].isin, "IE00B4L5Y983")


class PruebasBonificaciones(unittest.TestCase):
    """El cashback y los intereses no son lo mismo.

    Los intereses son dinero que el banco te da y se queda en la cuenta: eso
    es un ingreso. La bonificacion tambien te la dan, pero se reinvierte sola
    a los pocos dias. Contarla como ingreso y ademas la compra como dinero
    salido del banco la contaria dos veces, y encima pareceria que la pusiste
    tu: es una aportacion gratis, la tercera forma de que entre dinero.
    """

    # Como viene en el extracto: la bonificacion el dia 1 y su compra el 3.
    CON_CASHBACK = (
        filas_bonificacion("01 ago", "2026", "4,61")
        + filas_compra("03 ago", "2026", "4,61", "0.036630")
        + filas_compra("03 ago", "2026", "100,00", "0.794249")
        + filas_interes("01 ago", "2026", "9,34")
    )

    def test_la_bonificacion_reinvertida_no_es_un_ingreso(self):
        lectura = tr.leer_lineas(self.CON_CASHBACK)

        self.assertEqual([i.concepto for i in lectura.ingresos],
                         ["Intereses de Trade Republic"])
        self.assertEqual(len(lectura.gratis), 1)
        self.assertEqual(lectura.gratis[0].importe, 4.61)

    def test_la_bonificacion_se_queda_con_los_titulos_que_compro(self):
        gratis = tr.leer_lineas(self.CON_CASHBACK).gratis[0]
        self.assertEqual(gratis.titulos, 0.036630)
        self.assertEqual(gratis.fecha, "2026-08-03")

    def test_la_compra_de_la_bonificacion_no_cuenta_como_aportada(self):
        # Solo quedan los 100 € de verdad.
        compras = tr.leer_lineas(self.CON_CASHBACK).compras
        self.assertEqual([c.importe for c in compras], [100.0])

    def test_una_bonificacion_que_no_se_reinvierte_sigue_siendo_ingreso(self):
        # Te la dan y se queda en la cuenta: eso si es dinero que entra.
        sueltas = (filas_bonificacion("01 ago", "2026", "4,61")
                   + filas_compra("03 ago", "2026", "100,00", "0.794249"))
        lectura = tr.leer_lineas(sueltas)

        self.assertEqual(len(lectura.gratis), 0)
        self.assertEqual(len(lectura.ingresos), 1)
        self.assertEqual(lectura.ingresos[0].importe, 4.61)

    def test_no_empareja_una_compra_de_mucho_despues(self):
        tarde = (filas_bonificacion("01 ago", "2026", "4,61")
                 + filas_compra("28 ago", "2026", "4,61", "0.036630"))
        lectura = tr.leer_lineas(tarde)
        self.assertEqual(len(lectura.gratis), 0)
        self.assertEqual(len(lectura.ingresos), 1)

    def test_al_importar_va_a_la_cartera_y_no_al_banco(self):
        libro = Libro.vacio()
        hecho = tr.aplicar(libro, tr.leer_lineas(self.CON_CASHBACK),
                           "Inversión", "Otros Ingresos", "Indexados")

        self.assertEqual(hecho.gratis, 1)
        self.assertEqual(hecho.regalado, 4.61)
        self.assertEqual(len(libro.aportaciones_gratis), 1)

        activo = calculos.cartera(libro).activos[0]
        self.assertEqual(activo.aportado_banco, 100.0)
        self.assertEqual(activo.aportado_gratis, 4.61)
        self.assertEqual(activo.total_aportado, 104.61)

    def test_los_titulos_del_cashback_cuentan_en_la_cartera(self):
        libro = Libro.vacio()
        tr.aplicar(libro, tr.leer_lineas(self.CON_CASHBACK), "Inversión",
                   "Otros Ingresos", "Indexados")

        activo = calculos.cartera(libro).activos[0]
        self.assertAlmostEqual(activo.titulos, 0.794249 + 0.036630, places=6)

    def test_no_toca_el_saldo_del_banco(self):
        # Te lo regalan y se reinvierte: por la cuenta no pasa nada.
        libro = Libro.vacio()
        libro.ajustes.saldo_inicial = 1000.0
        tr.aplicar(libro, tr.leer_lineas(self.CON_CASHBACK), "Inversión",
                   "Otros Ingresos", "Indexados")

        # 1000 - 100 de la compra + 9,34 de intereses.
        self.assertEqual(calculos.saldo_banco(libro), 909.34)

    def test_importar_dos_veces_no_duplica_la_bonificacion(self):
        libro = Libro.vacio()
        tr.aplicar(libro, tr.leer_lineas(self.CON_CASHBACK), "Inversión",
                   "Otros Ingresos", "Indexados")
        segunda = tr.aplicar(libro, tr.leer_lineas(self.CON_CASHBACK), "Inversión",
                             "Otros Ingresos", "Indexados")

        self.assertEqual(segunda.gratis, 0)
        self.assertEqual(len(libro.aportaciones_gratis), 1)

    def test_se_guarda_y_se_recupera(self):
        libro = Libro.vacio()
        tr.aplicar(libro, tr.leer_lineas(self.CON_CASHBACK), "Inversión",
                   "Otros Ingresos", "Indexados")
        vuelto = Libro.desde_json(libro.a_json())

        self.assertEqual(vuelto.aportaciones_gratis[0].titulos, 0.036630)

    def test_arregla_lo_que_importaron_las_versiones_de_antes(self):
        """Reimportar corrige el cashback mal colocado.

        Las importaciones de antes de saber distinguirlo lo apuntaban como
        dinero salido del banco. Si al reimportar solo se anadiera la
        aportacion gratis, ese regalo quedaria contado dos veces: 804,66 del
        banco mas 4,66 de gratis.
        """
        from contaxcell.modelo import Movimiento
        libro = Libro.vacio()
        libro.activos = [Activo(nombre="MSCI World", isin="IE00B4L5Y983")]
        # Tal como lo dejaba la version vieja: las dos compras del banco.
        for fecha, importe, titulos in (("2026-08-03", 100.0, 0.794249),
                                        ("2026-08-03", 4.61, 0.036630)):
            libro.movimientos.append(Movimiento(
                fecha=fecha, descripcion="Compra del plan de inversión",
                categoria="Inversión", importe=importe, activo="MSCI World",
                titulos=titulos))
        antes = calculos.cartera(libro).activos[0]
        self.assertEqual(antes.aportado_banco, 104.61)
        self.assertEqual(antes.aportado_gratis, 0.0)

        hecho = tr.aplicar(libro, tr.leer_lineas(self.CON_CASHBACK), "Inversión",
                           "Otros Ingresos", "Indexados")

        self.assertEqual(hecho.corregidas, 1)
        despues = calculos.cartera(libro).activos[0]
        self.assertEqual(despues.aportado_banco, 100.0)
        self.assertEqual(despues.aportado_gratis, 4.61)
        # El total no cambia: solo estaba en el sitio equivocado.
        self.assertEqual(despues.total_aportado, 104.61)

    def test_arregla_tambien_si_la_gratis_ya_estaba_apuntada(self):
        """El caso de quien reimporto a medias, y el que salia mal.

        Con una version que ya separaba el cashback pero todavia no limpiaba
        lo anterior, el regalo acababa en los dos sitios: en «aportado del
        banco» y en «aportado gratis». Reimportar tiene que arreglarlo, y
        para eso la limpieza va antes de comprobar si la gratis ya esta: si
        no, se sale por «ya esta» y no se arregla nunca.
        """
        from contaxcell.modelo import AportacionGratis, Movimiento
        libro = Libro.vacio()
        libro.activos = [Activo(nombre="MSCI World", isin="IE00B4L5Y983")]
        libro.movimientos = [
            Movimiento(fecha="2026-08-03", descripcion="Compra del plan de inversión",
                       categoria="Inversión", importe=100.0, activo="MSCI World",
                       titulos=0.794249),
            # La del cashback, mal colocada como dinero del banco.
            Movimiento(fecha="2026-08-03", descripcion="Compra del plan de inversión",
                       categoria="Inversión", importe=4.61, activo="MSCI World",
                       titulos=0.036630),
        ]
        # Y ademas la aportacion gratis, de un reimportado anterior.
        libro.aportaciones_gratis = [AportacionGratis(
            fecha="2026-08-03", activo="MSCI World", importe=4.61,
            concepto="Bonificación de Trade Republic", titulos=0.036630)]

        antes = calculos.cartera(libro).activos[0]
        self.assertEqual(antes.total_aportado, 109.22)   # el regalo, dos veces

        hecho = tr.aplicar(libro, tr.leer_lineas(self.CON_CASHBACK), "Inversión",
                           "Otros Ingresos", "Indexados")

        self.assertEqual(hecho.corregidas, 1)
        despues = calculos.cartera(libro).activos[0]
        self.assertEqual(despues.aportado_banco, 100.0)
        self.assertEqual(despues.aportado_gratis, 4.61)
        self.assertEqual(despues.total_aportado, 104.61)
        # Y no se duplica la gratis ni se pierde ningun titulo.
        self.assertEqual(len(libro.aportaciones_gratis), 1)
        self.assertAlmostEqual(despues.titulos, 0.794249 + 0.036630, places=6)

    def test_una_bonificacion_sin_reinvertir_puede_ir_a_su_propia_categoria(self):
        sueltas = (filas_bonificacion("01 ago", "2026", "4,61")
                   + filas_interes("01 ago", "2026", "9,34"))
        libro = Libro.vacio()
        tr.aplicar(libro, tr.leer_lineas(sueltas), "Inversión",
                   categoria_ingreso="Sueldo",
                   categoria_bonificacion="Otros Ingresos")

        categorias = {m.descripcion: m.categoria for m in libro.movimientos}
        self.assertEqual(categorias["Intereses de Trade Republic"], "Sueldo")
        self.assertEqual(categorias["Bonificación de Trade Republic"], "Otros Ingresos")


class PruebasLoApuntadoAMano(unittest.TestCase):
    """El problema gordo de importar.

    Tu apuntas «400 € a inversion» una vez al mes. Luego importas seis meses
    y entran veinticuatro compras de 100 €, que son ese mismo dinero. Si se
    quedan las dos cosas, la cartera dice que metiste el doble.
    """

    def libro_con_lo_de_a_mano(self, fecha="2026-07-01", importe=400.0,
                               activo="") -> Libro:
        from contaxcell.modelo import Movimiento
        libro = Libro.vacio()
        libro.movimientos = [Movimiento(
            fecha=fecha, descripcion="Aportación del mes", categoria="Inversión",
            importe=importe, activo=activo, id="mano1")]
        return libro

    def test_las_encuentra_aunque_no_cuadren_ni_fecha_ni_importe(self):
        # 400 € del dia 1 contra cuatro compras de 100 € de otros dias.
        libro = self.libro_con_lo_de_a_mano()
        a_mano = tr.aportaciones_a_mano(libro, tr.leer_lineas(EXTRACTO))

        self.assertEqual([m.id for m in a_mano], ["mano1"])

    def test_no_toca_lo_de_otros_meses(self):
        libro = self.libro_con_lo_de_a_mano(fecha="2026-05-01")
        self.assertEqual(tr.aportaciones_a_mano(libro, tr.leer_lineas(EXTRACTO)), [])

    def test_no_toca_lo_que_va_a_otro_activo(self):
        # Si aportas a otro sitio ese mes, eso no lo trae este extracto.
        libro = self.libro_con_lo_de_a_mano(activo="Bitcoin")
        libro.activos = [Activo(nombre="Bitcoin")]
        self.assertEqual(tr.aportaciones_a_mano(libro, tr.leer_lineas(EXTRACTO)), [])

    def test_no_toca_lo_ya_importado_antes(self):
        # Lo importado trae participaciones; lo de a mano, no. Es lo que las
        # distingue.
        libro = Libro.vacio()
        tr.aplicar(libro, tr.leer_lineas(EXTRACTO), "Inversión", "Otros Ingresos")
        self.assertEqual(tr.aportaciones_a_mano(libro, tr.leer_lineas(EXTRACTO)), [])

    def test_no_toca_los_gastos_ni_los_ingresos(self):
        from contaxcell.modelo import Movimiento
        libro = self.libro_con_lo_de_a_mano()
        libro.movimientos.append(Movimiento(
            fecha="2026-07-05", descripcion="Súper", categoria="Productos Básicos",
            importe=400.0, id="gasto1"))
        a_mano = tr.aportaciones_a_mano(libro, tr.leer_lineas(EXTRACTO))
        self.assertEqual([m.id for m in a_mano], ["mano1"])

    def test_sustituirlas_deja_el_dinero_contado_una_sola_vez(self):
        libro = self.libro_con_lo_de_a_mano(importe=200.0)
        lectura = tr.leer_lineas(EXTRACTO)

        resultado = tr.aplicar(libro, lectura, "Inversión", "Otros Ingresos",
                               sustituir=[m.id for m in
                                          tr.aportaciones_a_mano(libro, lectura)])

        self.assertEqual(resultado.sustituidas, 1)
        self.assertEqual(resultado.sustituido, 200.0)
        self.assertIsNone(libro.movimiento("mano1"))
        # Lo invertido en julio son los 200 € del extracto, no 400.
        self.assertEqual(calculos.totales_del_mes(libro, "2026-07").inversion, 200.0)

    def test_no_sustituirlas_cuenta_el_dinero_dos_veces(self):
        # Es la otra opcion y tiene que seguir estando, pero se ve el efecto.
        libro = self.libro_con_lo_de_a_mano(importe=200.0)
        tr.aplicar(libro, tr.leer_lineas(EXTRACTO), "Inversión", "Otros Ingresos")
        self.assertEqual(calculos.totales_del_mes(libro, "2026-07").inversion, 400.0)


class PruebasCuentasDeLasCompras(unittest.TestCase):
    """Lo que hace todo esto util: saber como va cada compra."""

    def cartera_con_dos_compras(self) -> Libro:
        libro = Libro.vacio()
        tr.aplicar(libro, tr.leer_lineas(EXTRACTO), "Inversión", "Otros Ingresos",
                   "Indexados")
        # Las 1,592758 participaciones valen hoy 210 €: 131,84 € cada una.
        libro.activos[0].valor_mercado = 210.0
        return libro

    def test_el_precio_de_hoy_sale_solo(self):
        libro = self.cartera_con_dos_compras()
        activo = calculos.cartera(libro).activos[0]

        self.assertAlmostEqual(activo.titulos, 1.592758, places=6)
        self.assertAlmostEqual(activo.precio_hoy, 210.0 / 1.592758, places=4)

    def test_cada_compra_va_por_su_cuenta(self):
        # La del 9 de julio compro mas participaciones con los mismos 100 €,
        # asi que hoy vale mas. Eso es justo lo que habia que poder ver.
        libro = self.cartera_con_dos_compras()
        compras = calculos.compras_de(libro, "MSCI World")

        self.assertEqual(len(compras), 2)
        del_9 = next(c for c in compras if c.fecha == "2026-07-09")
        del_2 = next(c for c in compras if c.fecha == "2026-07-02")
        self.assertGreater(del_9.titulos, del_2.titulos)
        self.assertGreater(del_9.valor_hoy, del_2.valor_hoy)

    def test_lo_que_vale_cada_compra_suma_lo_que_vale_el_activo(self):
        libro = self.cartera_con_dos_compras()
        compras = calculos.compras_de(libro, "MSCI World")
        self.assertAlmostEqual(sum(c.valor_hoy for c in compras), 210.0, places=2)

    def test_un_activo_recien_importado_no_dice_que_lo_has_perdido_todo(self):
        """Sin valorar no es valer cero.

        Al importar el extracto se crea el activo sin que nadie haya dicho lo
        que vale. Tomando eso por cero, la cartera anunciaba «generado
        -804,66 €»: justo todo lo aportado. Mientras no se diga otra cosa se
        da por hecho que vale lo aportado, y lo generado es cero.
        """
        libro = self.cartera_con_dos_compras()
        libro.activos[0].valor_mercado = 0.0
        libro.activos[0].ultima_valoracion = ""

        activo = calculos.cartera(libro).activos[0]

        self.assertTrue(activo.sin_valorar)
        self.assertEqual(activo.valor_mercado, activo.total_aportado)
        self.assertEqual(activo.generado, 0.0)

    def test_la_cartera_avisa_de_lo_que_falta_por_valorar(self):
        libro = self.cartera_con_dos_compras()
        libro.activos[0].valor_mercado = 0.0
        libro.activos[0].ultima_valoracion = ""

        cartera = calculos.cartera(libro)

        self.assertEqual([a.nombre for a in cartera.sin_valorar], ["MSCI World"])
        self.assertEqual(cartera.aportado_sin_valorar, 200.0)
        self.assertEqual(cartera.generado, 0.0)

    def test_un_cero_apuntado_a_mano_sí_es_valer_cero(self):
        # Con fecha de valoración, el cero es una decisión y se respeta: hay
        # cosas que se van a cero de verdad.
        libro = self.cartera_con_dos_compras()
        libro.activos[0].valor_mercado = 0.0
        libro.activos[0].ultima_valoracion = "2026-08-25"

        activo = calculos.cartera(libro).activos[0]

        self.assertFalse(activo.sin_valorar)
        self.assertEqual(activo.generado, -200.0)

    def test_sin_valorar_no_se_inventa_como_va_cada_compra(self):
        """Para la cartera se supone que vale lo aportado, pero eso es el
        precio medio: usarlo por compra haría que la barata saliera ganando y
        la cara perdiendo por pura aritmética, sin que el mercado se moviera.
        Mejor no decir nada."""
        libro = self.cartera_con_dos_compras()
        libro.activos[0].valor_mercado = 0.0
        libro.activos[0].ultima_valoracion = ""

        compras = calculos.compras_de(libro, "MSCI World")

        self.assertEqual(len(compras), 2)
        self.assertTrue(all(c.precio_hoy == 0.0 for c in compras))
        # El precio que se pagó sí se sabe: eso no es una suposición.
        self.assertTrue(all(c.precio_pagado > 0 for c in compras))

    def test_las_aportaciones_a_mano_no_salen_como_compras(self):
        # Sin participaciones no se puede saber como ha ido esa compra.
        from contaxcell.modelo import Movimiento
        libro = self.cartera_con_dos_compras()
        libro.movimientos.append(Movimiento(
            fecha="2026-07-20", descripcion="A mano", categoria="Inversión",
            importe=50.0, activo="MSCI World"))

        self.assertEqual(len(calculos.compras_de(libro, "MSCI World")), 2)

    def test_la_cartera_se_agrupa_por_categoria(self):
        libro = self.cartera_con_dos_compras()
        libro.activos.append(Activo(nombre="Bitcoin", categoria="Cripto",
                                    aportacion_inicial=100.0, valor_mercado=90.0))

        grupos = calculos.por_categoria(calculos.cartera(libro))

        self.assertEqual([g.categoria for g in grupos], ["Indexados", "Cripto"])
        self.assertEqual(grupos[0].valor_mercado, 210.0)
        self.assertEqual(grupos[1].generado, -10.0)
        self.assertAlmostEqual(grupos[0].peso, 210.0 / 300.0, places=4)

    def test_lo_que_no_tiene_categoria_se_agrupa_aparte(self):
        libro = Libro.vacio()
        libro.activos = [Activo(nombre="Suelto", valor_mercado=50.0)]
        grupos = calculos.por_categoria(calculos.cartera(libro))
        self.assertEqual(grupos[0].categoria, calculos.SIN_CATEGORIA)


@unittest.skipUnless(os.environ.get("CONTAXCELL_EXTRACTO"),
                     "sin extracto de verdad a mano")
class PruebasConUnPdfDeVerdad(unittest.TestCase):
    def test_lee_el_pdf_entero(self):
        lectura = tr.leer(os.environ["CONTAXCELL_EXTRACTO"])
        self.assertTrue(lectura.compras, "no ha sacado ninguna compra")
        self.assertEqual(lectura.avisos, [])
        for compra in lectura.compras:
            self.assertTrue(compra.titulos > 0)
            self.assertTrue(compra.importe > 0)
            self.assertRegex(compra.fecha, r"^\d{4}-\d{2}-\d{2}$")


if __name__ == "__main__":
    unittest.main()
