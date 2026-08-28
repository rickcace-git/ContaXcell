"""Pruebas de las cotizaciones, sin red.

El proveedor se sustituye por uno de mentira que apunta cuantas veces le
preguntan. Eso es justo lo que hay que vigilar: la gracia de tener esto en el
servidor es preguntar una vez al dia por fondo para todo el grupo, y no una
vez por cada amigo cada vez que abre la aplicacion.
"""

from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from contaserver import precios
from contaserver.almacen import AlmacenSQLite
from contaserver.aplicacion import crear_aplicacion

SECRETO_DE_PRUEBA = b"secreto-solo-para-las-pruebas"
HOY = date.today().isoformat()


class ProveedorDeMentira:
    """Hace de proveedor de precios sin salir a internet."""

    def __init__(self, cotizaciones=None, revienta=False):
        self.cotizaciones = cotizaciones or []
        self.revienta = revienta
        self.veces_historico = 0
        self.veces_buscar = 0
        self.pedidos_desde = []

    def buscar(self, texto):
        self.veces_buscar += 1
        if self.revienta:
            raise precios.ErrorDelProveedor("se ha caído")
        return [{"simbolo": "SWDA:XMIL", "nombre": "iShares Core MSCI World",
                 "bolsa": "MIL", "moneda": "EUR", "pais": "Italy"}]

    def historico(self, simbolo, desde):
        self.veces_historico += 1
        self.pedidos_desde.append(desde)
        if self.revienta:
            raise precios.ErrorDelProveedor("se ha caído")
        return [c for c in self.cotizaciones if c.fecha >= desde]


def unas_cotizaciones():
    return [
        precios.Cotizacion("2026-08-24", 126.23),
        precios.Cotizacion("2026-08-25", 126.53),
        precios.Cotizacion("2026-08-26", 126.68),
    ]


class PruebasServicio(unittest.TestCase):
    """El servicio y su caché, sin pasar por la API."""

    def montar(self, proveedor=None):
        almacen = AlmacenSQLite()
        proveedor = proveedor or ProveedorDeMentira(unas_cotizaciones())
        return precios.ServicioPrecios(almacen, proveedor), proveedor, almacen

    def test_la_primera_vez_pregunta_y_guarda(self):
        servicio, proveedor, _ = self.montar()
        encontradas = servicio.cotizaciones("SWDA:XMIL", "2026-01-01")

        self.assertEqual(proveedor.veces_historico, 1)
        self.assertEqual(len(encontradas), 3)
        self.assertEqual(encontradas[-1].precio, 126.68)

    def test_la_segunda_vez_del_mismo_dia_no_pregunta(self):
        # Es la razon de tener esto en el servidor: el cupo es limitado.
        servicio, proveedor, _ = self.montar()
        servicio.cotizaciones("SWDA:XMIL", "2026-01-01")
        servicio.cotizaciones("SWDA:XMIL", "2026-01-01")
        servicio.cotizaciones("SWDA:XMIL", "2026-01-01")

        self.assertEqual(proveedor.veces_historico, 1)

    def test_al_dia_siguiente_solo_pide_lo_que_falta(self):
        # La primera vez cuesta una peticion grande; las demas, un dia.
        servicio, proveedor, almacen = self.montar()
        servicio.cotizaciones("SWDA:XMIL", "2026-01-01")
        almacen.apuntar_consulta("SWDA:XMIL", "2020-01-01")   # como si fuera ayer

        servicio.cotizaciones("SWDA:XMIL", "2026-01-01")

        self.assertEqual(proveedor.pedidos_desde, ["2026-01-01", "2026-08-27"])

    def test_si_el_proveedor_se_cae_sirve_lo_que_ya_tenia(self):
        # Para una cartera, un precio de ayer vale mucho mas que un error.
        servicio, _, almacen = self.montar()
        servicio.cotizaciones("SWDA:XMIL", "2026-01-01")

        roto = ProveedorDeMentira(revienta=True)
        servicio_roto = precios.ServicioPrecios(almacen, roto)
        almacen.apuntar_consulta("SWDA:XMIL", "2020-01-01")
        encontradas = servicio_roto.cotizaciones("SWDA:XMIL", "2026-01-01")

        self.assertEqual(len(encontradas), 3)

    def test_un_fin_de_semana_no_hace_preguntar_a_cada_rato(self):
        # Sabado: no hay cierres nuevos, pero no hay que insistir.
        servicio, proveedor, _ = self.montar(ProveedorDeMentira([]))
        servicio.cotizaciones("SWDA:XMIL", "2026-01-01")
        servicio.cotizaciones("SWDA:XMIL", "2026-01-01")

        self.assertEqual(proveedor.veces_historico, 1)

    def test_sin_proveedor_no_revienta_pero_no_actualiza(self):
        almacen = AlmacenSQLite()
        servicio = precios.ServicioPrecios(almacen, cliente=None)
        self.assertEqual(servicio.cotizaciones("SWDA:XMIL", "2026-01-01"), [])

    def test_el_simbolo_no_distingue_mayusculas(self):
        servicio, _, _ = self.montar()
        servicio.cotizaciones("swda:xmil", "2026-01-01")
        self.assertEqual(len(servicio.cotizaciones("SWDA:XMIL", "2026-01-01")), 3)

    def test_recorta_por_la_fecha_que_se_pide(self):
        servicio, _, _ = self.montar()
        servicio.cotizaciones("SWDA:XMIL", "2026-01-01")
        recientes = servicio.cotizaciones("SWDA:XMIL", "2026-08-26")
        self.assertEqual([c.fecha for c in recientes], ["2026-08-26"])


class PruebasCuantasPeticiones(unittest.TestCase):
    """Lo que de verdad importa: cuantas veces se sale a internet.

    Es la razon entera de que esto viva en el servidor. Si cada aplicacion
    preguntara por su cuenta, ocho amigos serian ocho peticiones por fondo y
    por dia, y cada vez que alguno abriera la ventana otra mas.
    """

    def montar(self):
        proveedor = ProveedorDeMentira(unas_cotizaciones())
        # El limite de registros normal son cinco por hora, y aqui hacen
        # falta ocho amigos. Se sube solo para esta prueba.
        app = crear_aplicacion(almacen=AlmacenSQLite(), secreto=SECRETO_DE_PRUEBA,
                               cliente_precios=proveedor,
                               limite_registro=(50, 3600))
        cliente = TestClient(app)
        return cliente, proveedor

    def fichas_de(self, cliente, cuantos: int) -> list:
        fichas = []
        for numero in range(cuantos):
            respuesta = cliente.post(
                "/api/cuentas/registro",
                json={"usuario": f"amigo{numero}", "contrasena": "contrasena1"})
            fichas.append({"Authorization": f"Bearer {respuesta.json()['token']}"})
        return fichas

    def test_ocho_amigos_gastan_una_sola_peticion(self):
        cliente, proveedor = self.montar()
        for ficha in self.fichas_de(cliente, 8):
            respuesta = cliente.get("/api/precios?simbolo=SWDA.MI&desde=2026-01-01",
                                    headers=ficha)
            self.assertEqual(respuesta.status_code, 200)
            self.assertEqual(len(respuesta.json()["cotizaciones"]), 3)

        # Ocho amigos, un solo viaje a internet.
        self.assertEqual(proveedor.veces_historico, 1)

    def test_abrir_la_ventana_diez_veces_tampoco_gasta_mas(self):
        cliente, proveedor = self.montar()
        ficha = self.fichas_de(cliente, 1)[0]
        for _ in range(10):
            cliente.get("/api/precios?simbolo=SWDA.MI&desde=2026-01-01", headers=ficha)

        self.assertEqual(proveedor.veces_historico, 1)

    def test_cada_fondo_cuenta_por_separado(self):
        # Tres fondos son tres peticiones al dia. No tres por amigo.
        cliente, proveedor = self.montar()
        fichas = self.fichas_de(cliente, 8)
        for ficha in fichas:
            for simbolo in ("SWDA.MI", "EUNL.DE", "VUSA.AS"):
                cliente.get(f"/api/precios?simbolo={simbolo}&desde=2026-01-01",
                            headers=ficha)

        self.assertEqual(proveedor.veces_historico, 3)


class PruebasAlmacen(unittest.TestCase):
    def test_guardar_dos_veces_el_mismo_dia_pisa_en_vez_de_duplicar(self):
        # Un cierre puede corregirse el mismo dia.
        almacen = AlmacenSQLite()
        almacen.guardar_precios("SWDA", [precios.Cotizacion("2026-08-26", 126.68)])
        almacen.guardar_precios("SWDA", [precios.Cotizacion("2026-08-26", 126.90)])

        guardadas = almacen.leer_precios("SWDA", "2026-01-01")
        self.assertEqual(len(guardadas), 1)
        self.assertEqual(guardadas[0].precio, 126.90)

    def test_el_ultimo_precio_es_la_fecha_mas_alta(self):
        almacen = AlmacenSQLite()
        almacen.guardar_precios("SWDA", unas_cotizaciones())
        self.assertEqual(almacen.ultimo_precio("SWDA"), "2026-08-26")

    def test_sin_precios_no_hay_ultimo(self):
        self.assertEqual(AlmacenSQLite().ultimo_precio("LO_QUE_SEA"), "")

    def test_los_precios_de_un_fondo_no_se_mezclan_con_los_de_otro(self):
        almacen = AlmacenSQLite()
        almacen.guardar_precios("SWDA", unas_cotizaciones())
        almacen.guardar_precios("VUSA", [precios.Cotizacion("2026-08-26", 95.0)])

        self.assertEqual(len(almacen.leer_precios("SWDA", "2026-01-01")), 3)
        self.assertEqual(len(almacen.leer_precios("VUSA", "2026-01-01")), 1)


class PruebasApi(unittest.TestCase):
    """Las dos rutas nuevas, con el TestClient."""

    def cliente(self, proveedor=None):
        proveedor = proveedor or ProveedorDeMentira(unas_cotizaciones())
        app = crear_aplicacion(almacen=AlmacenSQLite(), secreto=SECRETO_DE_PRUEBA,
                               cliente_precios=proveedor)
        cliente = TestClient(app)
        respuesta = cliente.post("/api/cuentas/registro",
                                 json={"usuario": "ana", "contrasena": "contrasena1"})
        self.ficha = {"Authorization": f"Bearer {respuesta.json()['token']}"}
        return cliente, proveedor

    def test_los_precios_piden_ficha(self):
        # El servidor es de un grupo cerrado, no un puente para cualquiera.
        cliente, _ = self.cliente()
        for url in ("/api/precios?simbolo=SWDA&desde=2026-01-01",
                    "/api/precios/buscar?q=msci"):
            self.assertEqual(cliente.get(url).status_code, 401, url)

    def test_devuelve_las_cotizaciones(self):
        cliente, _ = self.cliente()
        respuesta = cliente.get("/api/precios?simbolo=SWDA:XMIL&desde=2026-01-01",
                                headers=self.ficha)

        self.assertEqual(respuesta.status_code, 200)
        cuerpo = respuesta.json()
        self.assertEqual(cuerpo["simbolo"], "SWDA:XMIL")
        self.assertEqual(len(cuerpo["cotizaciones"]), 3)
        self.assertEqual(cuerpo["cotizaciones"][-1],
                         {"fecha": "2026-08-26", "precio": 126.68, "moneda": "EUR"})

    def test_buscar_devuelve_las_cotizaciones_posibles(self):
        cliente, _ = self.cliente()
        respuesta = cliente.get("/api/precios/buscar?q=msci world", headers=self.ficha)

        self.assertEqual(respuesta.status_code, 200)
        primero = respuesta.json()["encontrados"][0]
        self.assertEqual(primero["simbolo"], "SWDA:XMIL")
        self.assertEqual(primero["moneda"], "EUR")

    def test_buscar_con_dos_letras_de_nada_no_gasta_una_peticion(self):
        cliente, proveedor = self.cliente()
        respuesta = cliente.get("/api/precios/buscar?q=a", headers=self.ficha)

        self.assertEqual(respuesta.status_code, 422)
        self.assertEqual(proveedor.veces_buscar, 0)

    def test_una_fecha_mal_escrita_se_rechaza_con_explicacion(self):
        cliente, _ = self.cliente()
        respuesta = cliente.get("/api/precios?simbolo=SWDA&desde=el+mes+pasado",
                                headers=self.ficha)
        self.assertEqual(respuesta.status_code, 422)
        self.assertIn("AAAA-MM-DD", respuesta.json()["detail"])

    def test_sin_simbolo_se_rechaza(self):
        cliente, _ = self.cliente()
        respuesta = cliente.get("/api/precios?desde=2026-01-01", headers=self.ficha)
        self.assertEqual(respuesta.status_code, 422)

    def test_sin_clave_el_buscador_lo_dice_claro(self):
        app = crear_aplicacion(almacen=AlmacenSQLite(), secreto=SECRETO_DE_PRUEBA,
                               cliente_precios=None)
        cliente = TestClient(app)
        token = cliente.post("/api/cuentas/registro",
                             json={"usuario": "ana", "contrasena": "contrasena1"}
                             ).json()["token"]
        respuesta = cliente.get("/api/precios/buscar?q=msci",
                                headers={"Authorization": f"Bearer {token}"})

        self.assertEqual(respuesta.status_code, 503)
        self.assertIn(".env", respuesta.json()["detail"])

    def test_si_el_proveedor_se_cae_buscar_avisa_sin_reventar(self):
        cliente, _ = self.cliente(ProveedorDeMentira(revienta=True))
        respuesta = cliente.get("/api/precios/buscar?q=msci", headers=self.ficha)
        self.assertEqual(respuesta.status_code, 502)

    def test_si_el_proveedor_se_cae_los_precios_no_fallan(self):
        # Sin nada guardado devuelve una lista vacia, no un error.
        cliente, _ = self.cliente(ProveedorDeMentira(revienta=True))
        respuesta = cliente.get("/api/precios?simbolo=SWDA&desde=2026-01-01",
                                headers=self.ficha)

        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.json()["cotizaciones"], [])


class PruebasClienteDeVerdad(unittest.TestCase):
    """Del cliente que sale a internet solo se prueba lo que no necesita red."""

    def test_una_respuesta_con_error_se_cuenta_como_error(self):
        with self.assertRaises(precios.ErrorDelProveedor):
            precios._resultado({"chart": {"error": {"description": "no existe"}}})

    def test_una_respuesta_vacia_tambien(self):
        with self.assertRaises(precios.ErrorDelProveedor):
            precios._resultado({"chart": {"result": []}})

    def test_la_fecha_se_convierte_a_los_segundos_que_pide_yahoo(self):
        # Se comprueba la ida y la vuelta en vez de un numero escrito a mano.
        from datetime import datetime, timezone
        segundos = precios._a_segundos("2026-07-01")
        vuelta = datetime.fromtimestamp(segundos, timezone.utc).date()
        self.assertEqual(vuelta.isoformat(), "2026-07-01")

    def test_una_fecha_imposible_no_revienta(self):
        self.assertIsInstance(precios._a_segundos("el mes pasado"), int)

    def test_el_dia_siguiente(self):
        self.assertEqual(precios._dia_siguiente("2026-08-26"), "2026-08-27")
        self.assertEqual(precios._dia_siguiente("2026-12-31"), "2027-01-01")


if __name__ == "__main__":
    unittest.main()
