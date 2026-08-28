"""Pruebas de las cotizaciones en el escritorio.

Lo que se comprueba: que el precio que llega del servidor manda sobre el
valor escrito a mano, que los fines de semana no dejan la cartera en blanco,
y que guardar dos veces lo mismo no duplica nada.

Sin red: el servidor se sustituye por uno de mentira.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from contaxcell import calculos  # noqa: E402
from contaxcell.modelo import Activo, Cotizacion, Libro, Movimiento  # noqa: E402


def libro_con_fondo(simbolo: str = "SWDA:XMIL") -> Libro:
    """Dos compras de 100 € y un fondo con su cotizacion puesta."""
    libro = Libro.vacio()
    libro.activos = [Activo(nombre="MSCI World", simbolo=simbolo,
                            categoria="Indexados", isin="IE00B4L5Y983")]
    libro.movimientos = [
        Movimiento(fecha="2026-07-02", descripcion="Compra", categoria="Inversión",
                   importe=100.0, activo="MSCI World", titulos=0.795628, id="c1"),
        Movimiento(fecha="2026-07-09", descripcion="Compra", categoria="Inversión",
                   importe=100.0, activo="MSCI World", titulos=0.797130, id="c2"),
    ]
    return libro


def cierres(simbolo="SWDA:XMIL"):
    return [
        Cotizacion(simbolo, "2026-08-24", 126.23),
        Cotizacion(simbolo, "2026-08-25", 126.53),
        Cotizacion(simbolo, "2026-08-26", 126.68),
    ]


class PruebasGuardar(unittest.TestCase):
    def test_guarda_los_cierres(self):
        libro = libro_con_fondo()
        nuevos = calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())

        self.assertEqual(nuevos, 3)
        self.assertEqual(len(libro.cotizaciones), 3)

    def test_guardar_dos_veces_lo_mismo_no_duplica(self):
        libro = libro_con_fondo()
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())
        nuevos = calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())

        self.assertEqual(nuevos, 0)
        self.assertEqual(len(libro.cotizaciones), 3)

    def test_un_cierre_corregido_pisa_al_anterior(self):
        libro = libro_con_fondo()
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())
        calculos.guardar_cotizaciones(
            libro, "SWDA:XMIL", [Cotizacion("SWDA:XMIL", "2026-08-26", 127.00)])

        self.assertEqual(len(libro.cotizaciones), 3)
        self.assertEqual(calculos.ultima_cotizacion(libro, "SWDA:XMIL").precio, 127.00)

    def test_los_cierres_de_un_fondo_no_pisan_los_de_otro(self):
        libro = libro_con_fondo()
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())
        calculos.guardar_cotizaciones(
            libro, "VUSA:XAMS", [Cotizacion("VUSA:XAMS", "2026-08-26", 95.0)])

        self.assertEqual(len(calculos.cotizaciones_de(libro, "SWDA:XMIL")), 3)
        self.assertEqual(len(calculos.cotizaciones_de(libro, "VUSA:XAMS")), 1)

    def test_no_se_guardan_cierres_sin_precio(self):
        libro = libro_con_fondo()
        calculos.guardar_cotizaciones(
            libro, "SWDA:XMIL", [Cotizacion("SWDA:XMIL", "2026-08-26", 0.0)])
        self.assertEqual(libro.cotizaciones, [])

    def test_sobreviven_al_guardado_en_disco(self):
        libro = libro_con_fondo()
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())
        vuelto = Libro.desde_json(libro.a_json())

        self.assertEqual(len(vuelto.cotizaciones), 3)
        self.assertEqual(vuelto.activos[0].simbolo, "SWDA:XMIL")


class PruebasUltimaCotizacion(unittest.TestCase):
    def test_coge_la_mas_reciente(self):
        libro = libro_con_fondo()
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())
        self.assertEqual(calculos.ultima_cotizacion(libro, "SWDA:XMIL").fecha,
                         "2026-08-26")

    def test_un_domingo_devuelve_el_viernes(self):
        """Los fines de semana y los festivos no tienen cierre.

        Preguntando «en» esa fecha, la cartera se quedaría en blanco los
        sábados. Por eso se pregunta «hasta».
        """
        libro = libro_con_fondo()
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())
        anterior = calculos.ultima_cotizacion(libro, "SWDA:XMIL", hasta="2026-08-30")
        self.assertEqual(anterior.fecha, "2026-08-26")

    def test_antes_de_la_primera_no_hay_ninguna(self):
        libro = libro_con_fondo()
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())
        self.assertIsNone(
            calculos.ultima_cotizacion(libro, "SWDA:XMIL", hasta="2026-01-01"))

    def test_sin_simbolo_no_hay_ninguna(self):
        self.assertIsNone(calculos.ultima_cotizacion(libro_con_fondo(), ""))


class PruebasLaCotizacionManda(unittest.TestCase):
    """Con cotización puesta, el valor de mercado deja de escribirse a mano."""

    def test_el_valor_sale_de_multiplicar_titulos_por_precio(self):
        libro = libro_con_fondo()
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())

        activo = calculos.cartera(libro).activos[0]

        self.assertTrue(activo.cotizado)
        self.assertAlmostEqual(activo.titulos, 1.592758, places=6)
        self.assertEqual(activo.valor_mercado,
                         calculos.redondea(1.592758 * 126.68))
        self.assertEqual(activo.ultima_valoracion, "2026-08-26")

    def test_pisa_a_lo_que_hubieras_escrito_a_mano(self):
        # Un numero escrito hace tres meses es peor que el cierre de ayer.
        libro = libro_con_fondo()
        libro.activos[0].valor_mercado = 999.0
        libro.activos[0].ultima_valoracion = "2026-05-01"
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())

        activo = calculos.cartera(libro).activos[0]

        self.assertNotEqual(activo.valor_mercado, 999.0)
        self.assertEqual(activo.ultima_valoracion, "2026-08-26")

    def test_sin_cotizacion_todo_sigue_como_antes(self):
        libro = libro_con_fondo(simbolo="")
        libro.activos[0].valor_mercado = 210.0
        libro.activos[0].ultima_valoracion = "2026-08-25"

        activo = calculos.cartera(libro).activos[0]

        self.assertFalse(activo.cotizado)
        self.assertEqual(activo.valor_mercado, 210.0)

    def test_con_simbolo_pero_sin_precios_todavia_no_inventa_nada(self):
        libro = libro_con_fondo()
        activo = calculos.cartera(libro).activos[0]

        self.assertFalse(activo.cotizado)
        self.assertTrue(activo.sin_valorar)

    def test_sin_titulos_no_se_puede_multiplicar(self):
        # Un activo sin participaciones (una cuenta remunerada, oro) se sigue
        # valorando a mano aunque le pongan una cotizacion.
        libro = libro_con_fondo()
        libro.movimientos = []
        libro.activos[0].valor_mercado = 500.0
        libro.activos[0].ultima_valoracion = "2026-08-01"
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())

        activo = calculos.cartera(libro).activos[0]

        self.assertFalse(activo.cotizado)
        self.assertEqual(activo.valor_mercado, 500.0)

    def test_cada_compra_se_valora_con_el_precio_de_la_cotizacion(self):
        libro = libro_con_fondo()
        calculos.guardar_cotizaciones(libro, "SWDA:XMIL", cierres())

        compras = calculos.compras_de(libro, "MSCI World")

        self.assertEqual(len(compras), 2)
        for compra in compras:
            self.assertAlmostEqual(compra.precio_hoy, 126.68, places=2)
        # La del 9 compro mas titulos con los mismos 100 €, asi que va mejor.
        del_9 = next(c for c in compras if c.fecha == "2026-07-09")
        del_2 = next(c for c in compras if c.fecha == "2026-07-02")
        self.assertGreater(del_9.generado, del_2.generado)


class PruebasQuePedir(unittest.TestCase):
    """Qué cotizaciones hay que mantener al día y desde cuándo."""

    def test_los_simbolos_que_hay_que_mantener_al_dia(self):
        libro = libro_con_fondo()
        libro.activos.append(Activo(nombre="Bitcoin"))          # sin cotizacion
        libro.activos.append(Activo(nombre="Otro", simbolo="swda:xmil"))  # repetido

        self.assertEqual(calculos.simbolos_del_libro(libro), ["SWDA:XMIL"])

    def test_el_historico_se_pide_desde_la_primera_compra(self):
        # Antes de comprar, lo que valiera el fondo no cambia nada de lo tuyo:
        # pedir veinte anios de cierres seria gastar cupo para nada.
        libro = libro_con_fondo()
        self.assertEqual(
            calculos.desde_cuando_hacen_falta(libro, "SWDA:XMIL"), "2026-07-02")

    def test_cuenta_tambien_las_aportaciones_gratis(self):
        from contaxcell.modelo import AportacionGratis
        libro = libro_con_fondo()
        libro.aportaciones_gratis = [AportacionGratis(
            fecha="2026-06-15", activo="MSCI World", importe=4.61, titulos=0.0366)]

        self.assertEqual(
            calculos.desde_cuando_hacen_falta(libro, "SWDA:XMIL"), "2026-06-15")

    def test_un_fondo_sin_compras_se_pide_desde_hoy(self):
        from contaxcell.modelo import hoy
        libro = Libro.vacio()
        libro.activos = [Activo(nombre="Nuevo", simbolo="VUSA:XAMS")]
        self.assertEqual(
            calculos.desde_cuando_hacen_falta(libro, "VUSA:XAMS"), hoy())


if __name__ == "__main__":
    unittest.main()
