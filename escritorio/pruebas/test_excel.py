"""Pruebas de la importación, la exportación y el guardado en disco.

La prueba que más vale de todas es la de ida y vuelta: importar un libro,
exportarlo y volver a importarlo tiene que dar exactamente lo mismo. Si eso se
cumple, ningún dato se queda por el camino.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from contaxcell import calculos, excel  # noqa: E402
from contaxcell.almacen import Almacen  # noqa: E402
from contaxcell.modelo import (  # noqa: E402
    GASTO, INGRESO, INVERSION, Activo, AportacionGratis, Libro, Movimiento, Valoracion,
)

# Los libros de ejemplo están en la carpeta de arriba, junto a la aplicación
# del móvil. Si alguien se lleva solo la carpeta `escritorio`, estas pruebas
# se saltan en vez de fallar.
LIBROS = [RAIZ.parent / "PlantillaContabilidad.xlsx",
          RAIZ.parent / "ContabilidadRicardo.xlsx"]
DISPONIBLES = [p for p in LIBROS if p.exists()]


def retrato(libro: Libro) -> tuple:
    """Todo lo que define un libro, en algo comparable con ==."""
    cartera = calculos.cartera(libro)
    return (
        libro.ajustes.saldo_inicial,
        libro.ajustes.objetivo_inversion,
        [(c.nombre, c.tipo, c.presupuesto) for c in libro.categorias],
        sorted((m.fecha, m.descripcion, m.categoria, m.importe, m.activo)
               for m in libro.movimientos),
        [(a.nombre, a.aportacion_inicial, a.valor_mercado, a.ultima_valoracion)
         for a in libro.activos],
        sorted((g.fecha, g.activo, g.concepto, g.importe)
               for g in libro.aportaciones_gratis),
        sorted((v.fecha, v.valor_mercado) for v in libro.historico),
        calculos.saldo_banco(libro),
        cartera.total_aportado,
        cartera.generado,
    )


def libro_completo() -> Libro:
    libro = Libro.vacio()
    libro.ajustes.saldo_inicial = 1234.56
    libro.ajustes.objetivo_inversion = 150.0
    libro.categorias[2].presupuesto = 0.0      # un hueco a propósito
    libro.categorias[3].presupuesto = 480.0
    libro.categorias[5].presupuesto = 0.0
    libro.categorias[6].presupuesto = 90.0
    libro.activos = [
        Activo(nombre="Fondo indexado", aportacion_inicial=100.0, valor_mercado=265.0,
               ultima_valoracion="2026-08-31"),
        Activo(nombre="Cuenta remunerada", aportacion_inicial=0.0, valor_mercado=50.0,
               ultima_valoracion="2026-08-31"),
    ]
    libro.movimientos = [
        Movimiento(fecha="2026-08-01", descripcion="Nómina", categoria="Sueldo",
                   importe=1500.0),
        Movimiento(fecha="2026-08-03", descripcion="Alquiler",
                   categoria="Vivienda y Suministros", importe=600.0),
        Movimiento(fecha="2026-08-15", descripcion="Aportación", categoria="Inversión",
                   importe=120.0, activo="Fondo indexado"),
        Movimiento(fecha="2026-08-20", descripcion="Sin activo", categoria="Inversión",
                   importe=30.0),
    ]
    libro.aportaciones_gratis = [
        AportacionGratis(fecha="2026-08-31", activo="Fondo indexado",
                         concepto="Cashback 1%", importe=8.83),
    ]
    libro.historico = [Valoracion(fecha="2026-08-31", valor_mercado=315.0)]
    return libro


class PruebasIdaYVuelta(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp(prefix="contaxcell-pruebas-"))

    def test_libro_construido_a_mano(self):
        original = libro_completo()
        destino = self.carpeta / "vuelta.xlsx"
        excel.exportar(destino, original, 2026)
        recuperado, _ = excel.importar(destino)
        self.assertEqual(retrato(recuperado), retrato(original))

    @unittest.skipUnless(DISPONIBLES, "no hay libros de ejemplo al lado")
    def test_libros_de_ejemplo(self):
        for ruta in DISPONIBLES:
            with self.subTest(libro=ruta.name):
                original, _ = excel.importar(ruta)
                destino = self.carpeta / f"vuelta-{ruta.stem}.xlsx"
                excel.exportar(destino, original, 2026)
                recuperado, _ = excel.importar(destino)
                self.assertEqual(retrato(recuperado), retrato(original))

    def test_conserva_los_huecos_del_presupuesto(self):
        # Una categoría sin tope entre dos que sí lo tienen no puede cortar la
        # lectura: las de abajo perderían el suyo.
        original = libro_completo()
        destino = self.carpeta / "presupuesto.xlsx"
        excel.exportar(destino, original, 2026)
        recuperado, _ = excel.importar(destino)
        self.assertEqual([c.presupuesto for c in recuperado.categorias],
                         [c.presupuesto for c in original.categorias])

    def test_conserva_el_tipo_de_cada_categoria(self):
        original = libro_completo()
        destino = self.carpeta / "tipos.xlsx"
        excel.exportar(destino, original, 2026)
        recuperado, _ = excel.importar(destino)
        tipos = {c.nombre: c.tipo for c in recuperado.categorias}
        self.assertEqual(tipos["Sueldo"], INGRESO)
        self.assertEqual(tipos["Inversión"], INVERSION)
        self.assertEqual(tipos["Transporte"], GASTO)


@unittest.skipUnless(DISPONIBLES, "no hay libros de ejemplo al lado")
class PruebasImportacionReal(unittest.TestCase):
    def test_la_plantilla_se_lee_entera(self):
        ruta = next(p for p in DISPONIBLES if p.name == "PlantillaContabilidad.xlsx")
        libro, avisos = excel.importar(ruta)
        self.assertEqual(libro.ajustes.saldo_inicial, 1000.0)
        self.assertEqual(len(libro.categorias), 9)
        self.assertEqual(libro.categoria("Inversión").tipo, INVERSION)
        self.assertEqual(libro.categoria("Vivienda y Suministros").presupuesto, 700.0)
        self.assertTrue(libro.movimientos)
        self.assertTrue(libro.activos)
        self.assertEqual(avisos, [])

    def test_el_balance_de_la_hoja_cuadra_con_el_calculado(self):
        # La columna G de la plantilla es una fórmula que la aplicación ignora
        # y recalcula. Tienen que dar lo mismo.
        for ruta in DISPONIBLES:
            with self.subTest(libro=ruta.name):
                libro, _ = excel.importar(ruta)
                filas = calculos.con_balance(libro)
                a_mano = libro.ajustes.saldo_inicial
                for fila in filas:
                    signo = 1 if fila.tipo == INGRESO else -1
                    a_mano = round(a_mano + signo * fila.importe, 2)
                self.assertAlmostEqual(filas[-1].balance, a_mano, places=2)


class PruebasImportacionDificil(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp(prefix="contaxcell-pruebas-"))

    def test_archivo_sin_hoja_movimientos(self):
        from openpyxl import Workbook
        cuaderno = Workbook()
        cuaderno.active.title = "Hoja1"
        ruta = self.carpeta / "otro.xlsx"
        cuaderno.save(ruta)

        with self.assertRaises(excel.ErrorDeImportacion) as caso:
            excel.importar(ruta)
        self.assertIn("Movimientos", str(caso.exception))

    def test_archivo_que_no_es_excel(self):
        ruta = self.carpeta / "no-es-excel.xlsx"
        ruta.write_text("esto no es un libro", encoding="utf-8")
        with self.assertRaises(excel.ErrorDeImportacion):
            excel.importar(ruta)

    def test_categoria_que_no_esta_en_el_panel(self):
        from openpyxl import Workbook
        cuaderno = Workbook()
        hoja = cuaderno.active
        hoja.title = "Movimientos"
        hoja["A1"] = "Fecha"
        hoja["A2"] = "2026-05-04"
        hoja["C2"] = "Gimnasio"
        hoja["D2"] = "Deporte"
        hoja["F2"] = 30
        hoja["J6"] = "Sueldo"
        hoja["K6"] = "Ingreso"
        ruta = self.carpeta / "categoria-suelta.xlsx"
        cuaderno.save(ruta)

        libro, avisos = excel.importar(ruta)
        self.assertEqual(libro.categoria("Deporte").tipo, GASTO)
        self.assertTrue(any("Deporte" in a for a in avisos))

    def test_fechas_en_varios_formatos(self):
        self.assertEqual(excel._a_fecha("24/08/2026"), "2026-08-24")
        self.assertEqual(excel._a_fecha("4-8-26"), "2026-08-04")
        self.assertEqual(excel._a_fecha("2026-08-24"), "2026-08-24")
        self.assertEqual(excel._a_fecha("mañana"), "")
        self.assertEqual(excel._a_fecha(None), "")

    def test_importes_con_simbolos(self):
        self.assertEqual(excel._a_numero("1234,56"), 1234.56)
        self.assertEqual(excel._a_numero(" 40 € "), 40.0)
        self.assertEqual(excel._a_numero(None), 0.0)
        self.assertEqual(excel._a_numero("nada"), 0.0)


class PruebasAlmacen(unittest.TestCase):
    def setUp(self):
        self.carpeta = Path(tempfile.mkdtemp(prefix="contaxcell-almacen-"))
        self.almacen = Almacen(self.carpeta)

    def test_primer_arranque_crea_el_archivo(self):
        libro = self.almacen.cargar()
        self.assertTrue(self.almacen.ruta.exists())
        self.assertTrue(libro.categorias)
        self.assertEqual(self.almacen.aviso_de_arranque, "")

    def test_guarda_y_recupera(self):
        self.almacen.cargar()
        self.almacen.libro.movimientos.append(
            Movimiento(fecha="2026-06-01", categoria="Sueldo", importe=10.0))
        self.almacen.guardar()

        otro = Almacen(self.carpeta)
        otro.cargar()
        self.assertEqual(len(otro.libro.movimientos), 1)

    def test_no_deja_archivos_temporales(self):
        self.almacen.cargar()
        self.almacen.guardar()
        self.assertEqual(list(self.carpeta.glob("*.tmp")), [])

    def test_archivo_ilegible_se_aparta_y_avisa(self):
        self.almacen.ruta.write_text("{esto no es json", encoding="utf-8")
        libro = self.almacen.cargar()
        self.assertTrue(libro.categorias)
        self.assertIn("dañado", self.almacen.aviso_de_arranque)
        # Lo importante: el original no se ha perdido.
        self.assertTrue(list(self.carpeta.glob("datos-ilegible-*.json")))

    def test_copias_de_seguridad(self):
        self.almacen.cargar()
        primera = self.almacen.copia_de_seguridad("prueba")
        self.assertIsNotNone(primera)
        self.assertTrue(primera.exists())
        self.assertEqual(len(self.almacen.listar_copias()), 1)

    def test_solo_se_guardan_las_ultimas_copias(self):
        from contaxcell import almacen as modulo
        self.almacen.cargar()
        for numero in range(modulo.COPIAS_QUE_GUARDAMOS + 5):
            # El nombre lleva la hora al segundo, así que se fuerza que sean
            # distintas para que la prueba no dependa de lo rápido que vaya.
            destino = self.almacen.ruta_copias / f"2026-01-01_00-00-{numero:02d}-prueba.json"
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text("{}", encoding="utf-8")
        self.almacen._limpiar_copias()
        self.assertEqual(len(self.almacen.listar_copias()), modulo.COPIAS_QUE_GUARDAMOS)

    def test_restaurar_guarda_antes_lo_que_habia(self):
        self.almacen.cargar()
        self.almacen.libro.movimientos.append(
            Movimiento(fecha="2026-06-01", categoria="Sueldo", importe=99.0))
        self.almacen.guardar()

        otro_libro = Libro.vacio()
        origen = self.carpeta / "traido.json"
        origen.write_text(json.dumps(otro_libro.a_json()), encoding="utf-8")

        self.almacen.restaurar(origen)
        self.assertEqual(self.almacen.libro.movimientos, [])
        self.assertTrue(any("antes-de-restaurar" in c.name
                            for c in self.almacen.listar_copias()))


if __name__ == "__main__":
    unittest.main()
