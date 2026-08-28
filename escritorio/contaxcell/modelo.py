"""Forma de los datos de la contabilidad.

Un `Libro` es todo lo que la aplicación guarda: los ajustes, las categorías,
los movimientos y la cartera de inversión. Se serializa a JSON tal cual, así
que el archivo de datos se puede abrir con el bloc de notas y se entiende.

Las fechas son siempre cadenas 'AAAA-MM-DD'. Guardadas así se ordenan y se
comparan como texto, y nunca hay que pensar en zonas horarias ni en qué
formato de fecha tiene configurado el ordenador.
"""

from __future__ import annotations

import calendar
import random
import string
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

INGRESO = "Ingreso"
GASTO = "Gasto"
INVERSION = "Inversión"
TIPOS = (INGRESO, GASTO, INVERSION)

# --- cada cuánto se repite un pago periódico ---
SEMANAL = "Semanal"
QUINCENAL = "Quincenal"
MENSUAL = "Mensual"
BIMESTRAL = "Bimestral"
TRIMESTRAL = "Trimestral"
SEMESTRAL = "Semestral"
ANUAL = "Anual"
PERIODOS = (SEMANAL, QUINCENAL, MENSUAL, BIMESTRAL, TRIMESTRAL, SEMESTRAL, ANUAL)

# Lo que hay que sumar para llegar al siguiente pago: (días, meses). Siempre
# uno de los dos es cero. Los de semanas van por días para que caigan siempre
# en el mismo día de la semana; los demás por meses, para que caigan siempre
# en el mismo día del mes.
PASO = {
    SEMANAL: (7, 0),
    QUINCENAL: (14, 0),
    MENSUAL: (0, 1),
    BIMESTRAL: (0, 2),
    TRIMESTRAL: (0, 3),
    SEMESTRAL: (0, 6),
    ANUAL: (0, 12),
}

# Cuántas veces se paga al año. Sirve para poner en la misma escala cosas de
# distinto periodo y poder sumarlas. Lo semanal es aproximado a propósito: un
# año tiene 52 semanas y pico, y afinar más no cambia ninguna decisión.
VECES_AL_ANIO = {
    SEMANAL: 52, QUINCENAL: 26, MENSUAL: 12, BIMESTRAL: 6,
    TRIMESTRAL: 4, SEMESTRAL: 2, ANUAL: 1,
}

TEMAS = ("auto", "claro", "oscuro")

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
MESES_CORTOS = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)

# Categorías de activo que se ofrecen al crear uno. No son obligatorias ni
# cerradas: se puede escribir cualquier otra.
CATEGORIAS_ACTIVO = ("Indexados", "Acciones sueltas", "Cripto", "Bonos", "Oro")

CATEGORIAS_INICIALES = (
    ("Sueldo", INGRESO, 0),
    ("Otros Ingresos", INGRESO, 0),
    ("Productos Básicos", GASTO, 150),
    ("Vivienda y Suministros", GASTO, 700),
    ("Transporte", GASTO, 40),
    ("Ocio y Caprichos", GASTO, 80),
    ("Comer fuera", GASTO, 100),
    ("Otros Gastos", GASTO, 50),
    ("Inversión", INVERSION, 0),
)


# --- utilidades ------------------------------------------------------------

def redondea(valor) -> float:
    """Dos decimales redondeando 0,005 hacia arriba, como en el banco.

    El `round` de Python redondea al par más cercano (round(2.675, 2) da 2.67),
    que para dinero despista. Decimal con ROUND_HALF_UP hace lo que espera
    cualquiera que mire la cifra.
    """
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 0.0
    if numero != numero or numero in (float("inf"), float("-inf")):
        return 0.0
    return float(Decimal(str(numero)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def redondea_titulos(valor) -> float:
    """Seis decimales, que es lo que hace falta para las participaciones.

    Los títulos no son dinero: un fondo indexado se compra por fracciones, y
    con dos decimales una compra de 0,795628 participaciones se quedaría en
    0,80 y todas las cuentas saldrían torcidas.
    """
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 0.0
    if numero != numero or numero in (float("inf"), float("-inf")):
        return 0.0
    return float(Decimal(str(numero)).quantize(Decimal("0.000001"),
                                               rounding=ROUND_HALF_UP))


def es_fecha(texto) -> bool:
    if not isinstance(texto, str) or len(texto) != 10:
        return False
    if texto[4] != "-" or texto[7] != "-":
        return False
    try:
        date.fromisoformat(texto)
    except ValueError:
        return False
    return True


def hoy() -> str:
    return date.today().isoformat()


def mes_de(fecha: str) -> str:
    return fecha[:7] if es_fecha(fecha) else ""


def anio_de(fecha: str) -> int:
    return int(fecha[:4]) if es_fecha(fecha) else 0


def suma_dias(fecha: str, dias: int) -> str:
    """La fecha que cae `dias` días después. Cadena vacía si no es una fecha."""
    if not es_fecha(fecha):
        return ""
    return (date.fromisoformat(fecha) + timedelta(days=dias)).isoformat()


def suma_meses(fecha: str, meses: int) -> str:
    """La fecha que cae `meses` meses después, sin salirse del mes.

    Sumarle un mes al 31 de enero no puede dar el 31 de febrero: se queda en
    el último día que existe. Importa contar siempre desde la fecha original
    y no desde el pago anterior, porque así un recibo del día 31 vuelve al 31
    en marzo aunque en febrero se quedara en el 28.
    """
    if not es_fecha(fecha):
        return ""
    anio, mes, dia = int(fecha[:4]), int(fecha[5:7]), int(fecha[8:10])
    total = anio * 12 + (mes - 1) + meses
    anio_nuevo, mes_nuevo = divmod(total, 12)
    mes_nuevo += 1
    if not 1 <= anio_nuevo <= 9999:
        return ""
    ultimo_dia = calendar.monthrange(anio_nuevo, mes_nuevo)[1]
    return f"{anio_nuevo:04d}-{mes_nuevo:02d}-{min(dia, ultimo_dia):02d}"


def clave_mes(anio: int, indice_mes: int) -> str:
    """'2026-03' a partir del año y el número de mes empezando en cero."""
    return f"{anio:04d}-{indice_mes + 1:02d}"


def nombre_mes(clave: str, corto: bool = False) -> str:
    partes = str(clave or "").split("-")
    if len(partes) < 2 or not partes[1].isdigit():
        return str(clave or "")
    indice = int(partes[1]) - 1
    if not 0 <= indice < 12:
        return str(clave or "")
    lista = MESES_CORTOS if corto else MESES
    return f"{lista[indice]} {partes[0]}"


def nuevo_id() -> str:
    """Identificador corto y único dentro del archivo. No se enseña nunca."""
    alfabeto = string.ascii_lowercase + string.digits
    return "".join(random.choices(alfabeto, k=10))


def _texto(valor) -> str:
    return "" if valor is None else str(valor).strip()


# --- piezas ----------------------------------------------------------------

@dataclass
class Categoria:
    nombre: str
    tipo: str = GASTO
    presupuesto: float = 0.0

    @classmethod
    def desde_json(cls, d: dict) -> "Categoria":
        return cls(
            nombre=_texto(d.get("nombre")),
            tipo=d.get("tipo") if d.get("tipo") in TIPOS else GASTO,
            presupuesto=redondea(d.get("presupuesto")),
        )


@dataclass
class Activo:
    nombre: str
    aportacion_inicial: float = 0.0
    valor_mercado: float = 0.0
    ultima_valoracion: str = ""
    # Para agrupar la cartera: «Indexados», «Acciones sueltas», «Cripto».
    categoria: str = ""
    # El código con el que lo llama el banco. No se enseña en ningún sitio:
    # sirve para reconocer el activo al importar un extracto y no crear uno
    # nuevo cada vez que el nombre venga escrito de otra manera.
    isin: str = ""
    # La cotización de la que se saca el precio, como «SWDA:XMIL». Lleva el
    # mercado porque el mismo fondo cotiza en varias bolsas y en varias
    # monedas: el MSCI World va en libras en Londres, en euros en Milán y en
    # dólares en Dublín. La buena es aquella en la que compraste.
    simbolo: str = ""

    @classmethod
    def desde_json(cls, d: dict) -> "Activo":
        fecha = d.get("ultima_valoracion", "")
        return cls(
            nombre=_texto(d.get("nombre")),
            aportacion_inicial=redondea(d.get("aportacion_inicial")),
            valor_mercado=redondea(d.get("valor_mercado")),
            ultima_valoracion=fecha if es_fecha(fecha) else "",
            categoria=_texto(d.get("categoria")),
            isin=_texto(d.get("isin")).upper(),
            simbolo=_texto(d.get("simbolo")).upper(),
        )


@dataclass
class Movimiento:
    fecha: str
    descripcion: str = ""
    categoria: str = ""
    importe: float = 0.0
    activo: str = ""
    # Si lo apuntó solo un pago periódico, el id de ese periódico. A partir
    # de aquí es un movimiento como cualquier otro: se edita y se borra igual.
    origen: str = ""
    # Participaciones que compró esta aportación. Solo lo traen las compras
    # importadas del banco: a mano casi nunca se sabe, y se queda en cero.
    titulos: float = 0.0
    id: str = field(default_factory=nuevo_id)

    @classmethod
    def desde_json(cls, d: dict) -> "Movimiento":
        return cls(
            id=_texto(d.get("id")) or nuevo_id(),
            fecha=d.get("fecha", ""),
            descripcion=_texto(d.get("descripcion")),
            categoria=_texto(d.get("categoria")),
            # El signo lo decide la categoría, nunca el número: guardarlo
            # siempre positivo evita restas dobles al cambiar de categoría.
            importe=abs(redondea(d.get("importe"))),
            activo=_texto(d.get("activo")),
            origen=_texto(d.get("origen")),
            titulos=redondea_titulos(d.get("titulos")),
        )


@dataclass
class AportacionGratis:
    """Dinero que entra en la cartera sin salir de la cuenta: cashback,
    promociones, redondeos. No es un ingreso ni un gasto."""

    fecha: str
    activo: str = ""
    concepto: str = ""
    importe: float = 0.0
    # Si el regalo se reinvirtió, las participaciones que compró. Cuentan
    # igual que las de una compra: son títulos que tienes.
    titulos: float = 0.0
    id: str = field(default_factory=nuevo_id)

    @classmethod
    def desde_json(cls, d: dict) -> "AportacionGratis":
        return cls(
            id=_texto(d.get("id")) or nuevo_id(),
            fecha=d.get("fecha", ""),
            activo=_texto(d.get("activo")),
            concepto=_texto(d.get("concepto")),
            importe=redondea(d.get("importe")),
            titulos=redondea_titulos(d.get("titulos")),
        )


@dataclass
class Cotizacion:
    """Lo que valía una participación al cerrar un día.

    Vienen del servidor, que es quien tiene la clave del proveedor. Se
    guardan aquí para que la cartera siga saliendo bien sin conexión: sin
    esto, abrir la aplicación en el tren dejaría la pantalla a medias.
    """

    simbolo: str
    fecha: str
    precio: float = 0.0
    moneda: str = "EUR"

    @classmethod
    def desde_json(cls, d: dict) -> "Cotizacion":
        fecha = d.get("fecha", "")
        return cls(
            simbolo=_texto(d.get("simbolo")).upper(),
            fecha=fecha if es_fecha(fecha) else "",
            precio=redondea(d.get("precio")),
            moneda=_texto(d.get("moneda")) or "EUR",
        )


@dataclass
class Valoracion:
    """Cuánto valía la cartera entera en una fecha concreta."""

    fecha: str
    valor_mercado: float = 0.0
    id: str = field(default_factory=nuevo_id)

    @classmethod
    def desde_json(cls, d: dict) -> "Valoracion":
        return cls(
            id=_texto(d.get("id")) or nuevo_id(),
            fecha=d.get("fecha", ""),
            valor_mercado=redondea(d.get("valor_mercado")),
        )


@dataclass
class Periodico:
    """Un pago que se repite solo: la suscripción, el alquiler, el gimnasio,
    la nómina o la aportación de todos los meses a la cartera.

    No es un movimiento: es la receta para fabricarlos. Cuando vence uno, la
    aplicación apunta un movimiento normal y corriente, y desde ese momento
    ya no se distingue de lo apuntado a mano.

    El día lo manda `desde`, la fecha del primer pago: si es mensual y cae en
    día 5, es el 5 de cada mes; si es anual, ese mismo día de ese mismo mes;
    si es semanal, ese día de la semana. Un solo dato en vez de tres, así no
    puede haber contradicciones.
    """

    nombre: str
    categoria: str = ""
    importe: float = 0.0
    periodo: str = MENSUAL
    desde: str = ""
    # Fecha del último pago, para lo que se acaba solo: las doce cuotas de un
    # préstamo, un seguro que no se renueva. Vacío es que no tiene fin.
    hasta: str = ""
    # El activo de la cartera al que va, si la categoría es de inversión.
    # Ojo: `activo` es de la cartera y `encendido` es lo que se apaga.
    activo: str = ""
    encendido: bool = True
    # Hasta qué vencimiento se apuntó ya. Es lo que impide que un movimiento
    # borrado a mano vuelva a aparecer solo al abrir la aplicación: el
    # periódico ya pasó por esa fecha y no vuelve atrás.
    apuntado_hasta: str = ""
    id: str = field(default_factory=nuevo_id)

    @classmethod
    def desde_json(cls, d: dict) -> "Periodico":
        desde = d.get("desde", "")
        hasta = d.get("hasta", "")
        apuntado = d.get("apuntado_hasta", "")
        # Una fecha de fin anterior al primer pago no describe nada: se
        # descarta y se queda como si no tuviera fin.
        if not es_fecha(hasta) or (es_fecha(desde) and hasta < desde):
            hasta = ""
        return cls(
            id=_texto(d.get("id")) or nuevo_id(),
            nombre=_texto(d.get("nombre")),
            categoria=_texto(d.get("categoria")),
            importe=abs(redondea(d.get("importe"))),
            periodo=d.get("periodo") if d.get("periodo") in PERIODOS else MENSUAL,
            desde=desde if es_fecha(desde) else "",
            hasta=hasta,
            activo=_texto(d.get("activo")),
            encendido=bool(d.get("encendido", True)),
            apuntado_hasta=apuntado if es_fecha(apuntado) else "",
        )


@dataclass
class Ajustes:
    saldo_inicial: float = 0.0
    objetivo_inversion: float = 0.0
    ocultar_importes: bool = False
    tema: str = "auto"
    # El dia en que se miraron los precios por ultima vez. Va en el libro y
    # no en la sesion para que se sincronice: si ya los trajo el portatil, el
    # ordenador de casa no tiene que volver a pedirlos.
    precios_al_dia: str = ""

    @classmethod
    def desde_json(cls, d: dict) -> "Ajustes":
        return cls(
            saldo_inicial=redondea(d.get("saldo_inicial")),
            objetivo_inversion=redondea(d.get("objetivo_inversion")),
            ocultar_importes=bool(d.get("ocultar_importes")),
            tema=d.get("tema") if d.get("tema") in TEMAS else "auto",
            precios_al_dia=(d.get("precios_al_dia", "")
                            if es_fecha(d.get("precios_al_dia", "")) else ""),
        )


# --- el libro entero -------------------------------------------------------

@dataclass
class Libro:
    version: int = 1
    ajustes: Ajustes = field(default_factory=Ajustes)
    categorias: list[Categoria] = field(default_factory=list)
    activos: list[Activo] = field(default_factory=list)
    movimientos: list[Movimiento] = field(default_factory=list)
    aportaciones_gratis: list[AportacionGratis] = field(default_factory=list)
    historico: list[Valoracion] = field(default_factory=list)
    periodicos: list[Periodico] = field(default_factory=list)
    cotizaciones: list[Cotizacion] = field(default_factory=list)

    # --- construcción ---

    @classmethod
    def vacio(cls) -> "Libro":
        return cls(categorias=[
            Categoria(nombre=n, tipo=t, presupuesto=float(p))
            for n, t, p in CATEGORIAS_INICIALES
        ])

    @classmethod
    def desde_json(cls, crudo) -> "Libro":
        """Reconstruye un libro de un diccionario cualquiera.

        Descarta lo que no encaje en vez de fallar: un archivo a medias es
        mejor que un arranque con error. A partir de aquí el resto del código
        puede dar por buena la forma de los datos.
        """
        if not isinstance(crudo, dict):
            return cls.vacio()

        libro = cls()
        libro.ajustes = Ajustes.desde_json(crudo.get("ajustes") or {})

        libro.categorias = _sin_repetidos(
            (Categoria.desde_json(c) for c in _lista(crudo.get("categorias"))),
            clave=lambda c: c.nombre,
        )
        if not libro.categorias:
            libro.categorias = cls.vacio().categorias

        libro.activos = _sin_repetidos(
            (Activo.desde_json(a) for a in _lista(crudo.get("activos"))),
            clave=lambda a: a.nombre,
        )

        libro.movimientos = [
            m for m in (Movimiento.desde_json(x) for x in _lista(crudo.get("movimientos")))
            if es_fecha(m.fecha)
        ]
        libro.aportaciones_gratis = [
            a for a in (AportacionGratis.desde_json(x) for x in _lista(crudo.get("aportaciones_gratis")))
            if es_fecha(a.fecha)
        ]
        libro.historico = [
            v for v in (Valoracion.desde_json(x) for x in _lista(crudo.get("historico")))
            if es_fecha(v.fecha)
        ]
        libro.cotizaciones = [
            c for c in (Cotizacion.desde_json(x)
                        for x in _lista(crudo.get("cotizaciones")))
            if c.simbolo and c.fecha and c.precio > 0
        ]
        # Sin nombre o sin fecha de primer pago no se puede fabricar nada,
        # así que esos se descartan igual que los movimientos sin fecha.
        libro.periodicos = [
            p for p in (Periodico.desde_json(x) for x in _lista(crudo.get("periodicos")))
            if p.nombre and es_fecha(p.desde)
        ]
        return libro

    def a_json(self) -> dict:
        return {
            "version": self.version,
            "ajustes": vars(self.ajustes).copy(),
            "categorias": [vars(c).copy() for c in self.categorias],
            "activos": [vars(a).copy() for a in self.activos],
            "movimientos": [vars(m).copy() for m in self.movimientos],
            "aportaciones_gratis": [vars(a).copy() for a in self.aportaciones_gratis],
            "historico": [vars(v).copy() for v in self.historico],
            "periodicos": [vars(p).copy() for p in self.periodicos],
            "cotizaciones": [vars(c).copy() for c in self.cotizaciones],
        }

    # --- consultas de conveniencia ---

    def categoria(self, nombre: str) -> Categoria | None:
        for c in self.categorias:
            if c.nombre == nombre:
                return c
        return None

    def tipo_de(self, nombre_categoria: str) -> str:
        """El tipo lo manda la categoría, igual que en la plantilla de Excel.

        Si la categoría ya no existe caemos en Gasto, que es lo que menos
        distorsiona: nunca infla el saldo por sorpresa.
        """
        categoria = self.categoria(nombre_categoria)
        return categoria.tipo if categoria else GASTO

    def movimiento(self, ident: str) -> Movimiento | None:
        for m in self.movimientos:
            if m.id == ident:
                return m
        return None

    def activo(self, nombre: str) -> Activo | None:
        for a in self.activos:
            if a.nombre == nombre:
                return a
        return None

    def activo_por_isin(self, isin: str) -> Activo | None:
        """El activo con ese código del banco, si ya lo conocemos.

        Es lo que evita que importar el extracto dos veces cree dos fondos
        distintos porque el nombre venía escrito de otra manera.
        """
        codigo = _texto(isin).upper()
        if not codigo:
            return None
        for a in self.activos:
            if a.isin == codigo:
                return a
        return None

    def periodico(self, ident: str) -> Periodico | None:
        for p in self.periodicos:
            if p.id == ident:
                return p
        return None


def _lista(valor) -> list:
    return valor if isinstance(valor, list) else []


def _sin_repetidos(elementos, clave):
    """Se queda con el primero de cada nombre y descarta los que no lo tienen."""
    vistos: set[str] = set()
    resultado = []
    for elemento in elementos:
        nombre = clave(elemento)
        if not nombre or nombre in vistos:
            continue
        vistos.add(nombre)
        resultado.append(elemento)
    return resultado
