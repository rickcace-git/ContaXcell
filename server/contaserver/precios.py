"""Las cotizaciones de los fondos.

Por qué esto vive en el servidor y no en cada aplicación:

1. **El día que el proveedor se rompa, se arregla aquí.** La fuente de
   precios no es oficial y puede cambiar de un día para otro; teniéndola en
   el servidor se toca una máquina, no se reparte un `.exe` nuevo a nadie.
2. **Se pregunta una vez al día por fondo, para todo el grupo.** Si cada
   aplicación preguntara por su cuenta, serían tantas peticiones como amigos.
3. **El histórico se acumula en un sitio.** Quien entre mañana se encuentra
   los precios de todo el año ya guardados.
4. Y si algún día hay que volver a un proveedor con clave, la clave estará
   en `.env` y no dentro de un ejecutable, donde sería pública.

Este módulo no sabe nada de FastAPI. Recibe un almacén y un cliente, y los dos
se pueden cambiar por otra cosa: las pruebas le pasan un cliente de mentira y
corren sin red.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

registro_log = logging.getLogger("contaserver.precios")

# De dónde salen los precios.
#
# Se probó primero con Twelve Data, que es una API oficial y con contrato,
# pero su plan gratuito **solo cubre bolsas de Estados Unidos**: cualquier
# fondo europeo contesta «available starting with the Grow plan», y eso son
# 29 dólares al mes. Para seguir una cartera personal no tiene sentido.
#
# Yahoo no es una API oficial y puede romperse cualquier día, pero no pide
# clave, cubre las bolsas europeas y da el histórico entero. Estando aquí y
# no en cada `.exe`, el día que se rompa se arregla en el servidor y se
# arregla para todos, sin repartir nada.
BASE = "https://query1.finance.yahoo.com"
ESPERA = 15          # segundos antes de rendirse
CANDIDATOS = 8       # cuántas cotizaciones se miran al buscar

# Yahoo rechaza las peticiones sin navegador declarado.
CABECERAS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


class SinClave(Exception):
    """El proveedor configurado necesita una clave y no la hay.

    Con Yahoo no salta nunca, pero se queda para que cambiar de proveedor no
    obligue a tocar la API ni la aplicación.
    """


class ErrorDelProveedor(Exception):
    """El proveedor de precios ha dicho que no."""


@dataclass(frozen=True)
class Cotizacion:
    """Lo que valía un fondo al cerrar un día."""

    fecha: str      # 'AAAA-MM-DD'
    precio: float
    moneda: str = "EUR"

    def a_json(self) -> dict:
        return {"fecha": self.fecha, "precio": self.precio, "moneda": self.moneda}


# --- el proveedor ----------------------------------------------------------

class ClienteYahoo:
    """Habla con Yahoo. Es lo único de aquí que toca la red.

    Cambiar de proveedor es reescribir esta clase y nada más: el servicio, la
    caché, las rutas y la aplicación hablan con `buscar` e `historico`.
    """

    def __init__(self, base: str = BASE):
        self.base = base

    def _json(self, camino: str, parametros: dict) -> dict:
        url = f"{self.base}/{camino}?{urllib.parse.urlencode(parametros)}"
        peticion = urllib.request.Request(url, headers=CABECERAS)
        try:
            with urllib.request.urlopen(peticion, timeout=ESPERA) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise ErrorDelProveedor(f"ha contestado {error.code}") from error
        except (urllib.error.URLError, TimeoutError) as error:
            raise ErrorDelProveedor("no se ha podido llegar al proveedor") from error
        except ValueError as error:
            raise ErrorDelProveedor("ha contestado algo que no es JSON") from error

    def buscar(self, texto: str) -> list[dict]:
        """Las cotizaciones que encajan, cada una con su moneda.

        La moneda es el dato que de verdad importa y el buscador no la trae,
        así que de cada candidato se mira además su ficha. El mismo fondo
        cotiza en libras en Londres, en euros en Milán y en dólares en
        Dublín, y la buena es aquella en la que compraste.
        """
        encontrados = self._citas(texto)

        # Buscando por ISIN solo sale una, y suele ser la de Londres en
        # dólares. Con su nombre se vuelve a buscar y aparecen todas las
        # demás, que es donde está la de euros.
        if len(encontrados) == 1 and _parece_isin(texto):
            por_nombre = self._citas(encontrados[0]["nombre"])
            if len(por_nombre) > 1:
                encontrados = _sin_repetir(encontrados + por_nombre)

        for encontrado in encontrados[:CANDIDATOS]:
            self._completar(encontrado)
        return encontrados[:CANDIDATOS]

    def _citas(self, texto: str) -> list[dict]:
        datos = self._json("v1/finance/search", {"q": texto, "quotesCount": 15})
        encontrados = []
        for cita in datos.get("quotes", []):
            simbolo = str(cita.get("symbol", "")).strip()
            if not simbolo or cita.get("quoteType") not in ("ETF", "EQUITY", "MUTUALFUND"):
                continue
            encontrados.append({
                "simbolo": simbolo,
                "nombre": cita.get("shortname") or cita.get("longname") or "",
                "bolsa": cita.get("exchange", ""),
                "moneda": "",
                "precio": 0.0,
            })
        return encontrados

    def _completar(self, encontrado: dict) -> None:
        """Le pone la moneda y el precio de hoy. Si falla, se deja en blanco:
        una cotización sin moneda es menos útil, pero perder toda la búsqueda
        por una que no contesta sería peor."""
        try:
            meta = self._meta(encontrado["simbolo"])
        except ErrorDelProveedor:
            return
        encontrado["moneda"] = meta.get("currency", "")
        encontrado["precio"] = float(meta.get("regularMarketPrice") or 0.0)
        encontrado["bolsa"] = meta.get("fullExchangeName") or encontrado["bolsa"]

    def _meta(self, simbolo: str) -> dict:
        datos = self._json(f"v8/finance/chart/{urllib.parse.quote(simbolo)}",
                           {"interval": "1d", "range": "5d"})
        return _resultado(datos).get("meta") or {}

    def historico(self, simbolo: str, desde: str) -> list[Cotizacion]:
        """Los cierres diarios de ese fondo desde la fecha que se diga."""
        datos = self._json(f"v8/finance/chart/{urllib.parse.quote(simbolo)}", {
            "interval": "1d",
            "period1": _a_segundos(desde),
            "period2": _a_segundos(date.today().isoformat()) + 86400,
        })
        resultado = _resultado(datos)
        moneda = (resultado.get("meta") or {}).get("currency", "EUR")
        marcas = resultado.get("timestamp") or []
        cierres = (((resultado.get("indicators") or {}).get("quote") or [{}])[0]
                   .get("close") or [])

        cotizaciones = []
        for marca, cierre in zip(marcas, cierres):
            # Los días sin negociación vienen con el cierre a nulo.
            if cierre is None:
                continue
            fecha = datetime.fromtimestamp(marca, timezone.utc).date().isoformat()
            precio = round(float(cierre), 4)
            if precio > 0:
                cotizaciones.append(Cotizacion(fecha, precio, moneda))
        return cotizaciones


_ISIN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}\d$")


def _parece_isin(texto: str) -> bool:
    """Un ISIN son doce caracteres: dos letras de pais y diez mas."""
    return bool(_ISIN.match(texto.strip().upper()))


def _sin_repetir(encontrados: list[dict]) -> list[dict]:
    """Se queda con el primero de cada simbolo, conservando el orden."""
    vistos, limpios = set(), []
    for encontrado in encontrados:
        if encontrado["simbolo"] not in vistos:
            vistos.add(encontrado["simbolo"])
            limpios.append(encontrado)
    return limpios


def _resultado(datos: dict) -> dict:
    """El primer resultado del gráfico, o un error con lo que diga Yahoo."""
    grafico = datos.get("chart") or {}
    if grafico.get("error"):
        raise ErrorDelProveedor(str(grafico["error"].get("description", "error")))
    resultados = grafico.get("result") or []
    if not resultados:
        raise ErrorDelProveedor("no hay datos de esa cotización")
    return resultados[0]


def _a_segundos(fecha: str) -> int:
    """De 'AAAA-MM-DD' a los segundos que cuenta Yahoo."""
    try:
        dia = date.fromisoformat(fecha)
    except ValueError:
        dia = date.today()
    return int(datetime(dia.year, dia.month, dia.day, tzinfo=timezone.utc).timestamp())


# --- el servicio, con su caché ---------------------------------------------

class ServicioPrecios:
    """Sirve precios, preguntando al proveedor lo menos posible.

    La regla es sencilla: de un fondo no se pregunta más de una vez al día.
    Lo demás sale de la base de datos, que es donde se va acumulando el
    histórico del grupo.
    """

    def __init__(self, almacen, cliente=None):
        self.almacen = almacen
        self.cliente = cliente

    def buscar(self, texto: str) -> list[dict]:
        if self.cliente is None:
            raise SinClave("el servidor no tiene configurada la clave de precios")
        return self.cliente.buscar(texto)

    def cotizaciones(self, simbolo: str, desde: str) -> list[Cotizacion]:
        """El histórico de ese fondo, actualizándolo si toca."""
        simbolo = simbolo.strip().upper()
        if not simbolo:
            return []

        if self._toca_preguntar(simbolo):
            self._actualizar(simbolo, desde)
        return self.almacen.leer_precios(simbolo, desde)

    # --- por dentro ---

    def _toca_preguntar(self, simbolo: str) -> bool:
        ultima = self.almacen.ultima_consulta(simbolo)
        return ultima != date.today().isoformat()

    def _actualizar(self, simbolo: str, desde: str) -> None:
        """Trae lo que falte. Si el proveedor falla, no pasa nada: se sirve
        lo que ya hubiera guardado, que es mejor que un error en pantalla."""
        if self.cliente is None:
            registro_log.warning("sin clave de precios: no se actualiza %s", simbolo)
            return

        # Se pide desde el día siguiente al último que tengamos, no desde el
        # principio: así la primera vez cuesta una petición grande y las
        # demás, uno o dos días.
        ultimo = self.almacen.ultimo_precio(simbolo)
        arranque = _dia_siguiente(ultimo) if ultimo else desde

        try:
            cotizaciones = self.cliente.historico(simbolo, arranque)
        except (SinClave, ErrorDelProveedor) as error:
            registro_log.warning("no se han podido traer precios de %s: %s",
                                 simbolo, error)
            return

        if cotizaciones:
            self.almacen.guardar_precios(simbolo, cotizaciones)
        # Se apunta el intento aunque no venga nada: un fin de semana no
        # devuelve cierres, y no hay que preguntar otra vez cada minuto.
        self.almacen.apuntar_consulta(simbolo, date.today().isoformat())


def _dia_siguiente(fecha: str) -> str:
    try:
        return (date.fromisoformat(fecha) + timedelta(days=1)).isoformat()
    except ValueError:
        return fecha
