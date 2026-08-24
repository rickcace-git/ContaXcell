"""Forma de los datos de la contabilidad.

Un `Libro` es todo lo que la aplicación guarda: los ajustes, las categorías,
los movimientos y la cartera de inversión. Se serializa a JSON tal cual, así
que el archivo de datos se puede abrir con el bloc de notas y se entiende.

Las fechas son siempre cadenas 'AAAA-MM-DD'. Guardadas así se ordenan y se
comparan como texto, y nunca hay que pensar en zonas horarias ni en qué
formato de fecha tiene configurado el ordenador.
"""

from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

INGRESO = "Ingreso"
GASTO = "Gasto"
INVERSION = "Inversión"
TIPOS = (INGRESO, GASTO, INVERSION)

TEMAS = ("auto", "claro", "oscuro")

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)
MESES_CORTOS = (
    "ene", "feb", "mar", "abr", "may", "jun",
    "jul", "ago", "sep", "oct", "nov", "dic",
)

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

    @classmethod
    def desde_json(cls, d: dict) -> "Activo":
        fecha = d.get("ultima_valoracion", "")
        return cls(
            nombre=_texto(d.get("nombre")),
            aportacion_inicial=redondea(d.get("aportacion_inicial")),
            valor_mercado=redondea(d.get("valor_mercado")),
            ultima_valoracion=fecha if es_fecha(fecha) else "",
        )


@dataclass
class Movimiento:
    fecha: str
    descripcion: str = ""
    categoria: str = ""
    importe: float = 0.0
    activo: str = ""
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
        )


@dataclass
class AportacionGratis:
    """Dinero que entra en la cartera sin salir de la cuenta: cashback,
    promociones, redondeos. No es un ingreso ni un gasto."""

    fecha: str
    activo: str = ""
    concepto: str = ""
    importe: float = 0.0
    id: str = field(default_factory=nuevo_id)

    @classmethod
    def desde_json(cls, d: dict) -> "AportacionGratis":
        return cls(
            id=_texto(d.get("id")) or nuevo_id(),
            fecha=d.get("fecha", ""),
            activo=_texto(d.get("activo")),
            concepto=_texto(d.get("concepto")),
            importe=redondea(d.get("importe")),
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
class Ajustes:
    saldo_inicial: float = 0.0
    objetivo_inversion: float = 0.0
    ocultar_importes: bool = False
    tema: str = "auto"

    @classmethod
    def desde_json(cls, d: dict) -> "Ajustes":
        return cls(
            saldo_inicial=redondea(d.get("saldo_inicial")),
            objetivo_inversion=redondea(d.get("objetivo_inversion")),
            ocultar_importes=bool(d.get("ocultar_importes")),
            tema=d.get("tema") if d.get("tema") in TEMAS else "auto",
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
