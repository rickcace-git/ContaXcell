"""Toda la aritmética de la contabilidad.

Es la traducción de las fórmulas de la plantilla de Excel: el saldo del banco,
el panel del mes, el resumen anual, el presupuesto y la cartera de inversión.

No toca disco ni interfaz: recibe un `Libro` y devuelve datos. Por eso se
puede probar entero sin abrir la ventana (ver `pruebas/`).

La idea que gobierna todo: hay tres tipos de movimiento, no dos. La inversión
sale del banco igual que un gasto, pero el dinero sigue siendo tuyo, así que
no cuenta como gasto al calcular el ahorro.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from .modelo import (
    GASTO, INGRESO, INVERSION, MESES, MESES_CORTOS,
    Libro, Movimiento, anio_de, clave_mes, es_fecha, hoy, mes_de, redondea,
)


# --- movimientos -----------------------------------------------------------

def efecto_en_banco(libro: Libro, movimiento: Movimiento) -> float:
    """Lo que el movimiento le hace al saldo: los ingresos suman, todo lo
    demás resta (gastos y aportaciones a inversión salen igual de la cuenta)."""
    if libro.tipo_de(movimiento.categoria) == INGRESO:
        return movimiento.importe
    return -movimiento.importe


def ordenados(movimientos: list[Movimiento]) -> list[Movimiento]:
    """De más antiguo a más reciente. El id desempata para que dos apuntes del
    mismo día salgan siempre en el mismo orden."""
    return sorted(movimientos, key=lambda m: (m.fecha, m.id))


@dataclass
class FilaLibro:
    """Un movimiento con lo que la interfaz necesita para pintarlo."""

    movimiento: Movimiento
    tipo: str
    balance: float

    @property
    def id(self) -> str:
        return self.movimiento.id

    @property
    def fecha(self) -> str:
        return self.movimiento.fecha

    @property
    def descripcion(self) -> str:
        return self.movimiento.descripcion

    @property
    def categoria(self) -> str:
        return self.movimiento.categoria

    @property
    def importe(self) -> float:
        return self.movimiento.importe

    @property
    def activo(self) -> str:
        return self.movimiento.activo


def con_balance(libro: Libro) -> list[FilaLibro]:
    """Los movimientos con el saldo acumulado hasta esa fila: la columna
    «Balance» de la hoja."""
    saldo = libro.ajustes.saldo_inicial
    filas = []
    for movimiento in ordenados(libro.movimientos):
        saldo = redondea(saldo + efecto_en_banco(libro, movimiento))
        filas.append(FilaLibro(
            movimiento=movimiento,
            tipo=libro.tipo_de(movimiento.categoria),
            balance=saldo,
        ))
    return filas


def saldo_banco(libro: Libro) -> float:
    saldo = libro.ajustes.saldo_inicial
    for movimiento in libro.movimientos:
        saldo = redondea(saldo + efecto_en_banco(libro, movimiento))
    return saldo


def saldo_hasta(libro: Libro, fecha_tope: str) -> float:
    """El saldo al terminar el día indicado."""
    saldo = libro.ajustes.saldo_inicial
    for movimiento in libro.movimientos:
        if movimiento.fecha <= fecha_tope:
            saldo = redondea(saldo + efecto_en_banco(libro, movimiento))
    return saldo


# --- totales de un periodo -------------------------------------------------

@dataclass
class Totales:
    ingresos: float = 0.0
    gastos: float = 0.0
    inversion: float = 0.0
    por_categoria: dict[str, float] = field(default_factory=dict)

    @property
    def ahorro(self) -> float:
        """Lo que te has quedado. La inversión no resta: sigue siendo tuya."""
        return redondea(self.ingresos - self.gastos)

    @property
    def flujo_neto(self) -> float:
        """Lo que ha variado el banco de verdad, con la inversión descontada."""
        return redondea(self.ahorro - self.inversion)

    @property
    def tasa_ahorro(self) -> float:
        return self.ahorro / self.ingresos if self.ingresos > 0 else 0.0

    @property
    def hay_datos(self) -> bool:
        return bool(self.ingresos or self.gastos or self.inversion)


def totales(libro: Libro, filtro) -> Totales:
    resultado = Totales()
    for movimiento in libro.movimientos:
        if not filtro(movimiento):
            continue
        tipo = libro.tipo_de(movimiento.categoria)
        acumulado = resultado.por_categoria.get(movimiento.categoria, 0.0)
        resultado.por_categoria[movimiento.categoria] = redondea(acumulado + movimiento.importe)
        if tipo == INGRESO:
            resultado.ingresos = redondea(resultado.ingresos + movimiento.importe)
        elif tipo == INVERSION:
            resultado.inversion = redondea(resultado.inversion + movimiento.importe)
        else:
            resultado.gastos = redondea(resultado.gastos + movimiento.importe)
    return resultado


def totales_del_mes(libro: Libro, mes: str) -> Totales:
    return totales(libro, lambda m: mes_de(m.fecha) == mes)


def totales_del_anio(libro: Libro, anio: int) -> Totales:
    return totales(libro, lambda m: anio_de(m.fecha) == anio)


# --- resumen anual ---------------------------------------------------------

@dataclass
class MesDelAnio:
    clave: str
    nombre: str
    corto: str
    totales: Totales
    saldo_final: float

    @property
    def hay_datos(self) -> bool:
        return self.totales.hay_datos


@dataclass
class FilaReparto:
    nombre: str
    importe: float
    porcentaje: float


@dataclass
class Reparto:
    total: float
    filas: list[FilaReparto]


@dataclass
class ResumenAnual:
    anio: int
    meses: list[MesDelAnio]
    total: Totales
    meses_con_datos: int
    gasto: Reparto
    ingreso: Reparto


def resumen_anual(libro: Libro, anio: int) -> ResumenAnual:
    meses = []
    for indice in range(12):
        clave = clave_mes(anio, indice)
        # '-31' aunque el mes tenga 28 días: las fechas se comparan como
        # texto, así que basta con que sea mayor que cualquier día real.
        meses.append(MesDelAnio(
            clave=clave,
            nombre=MESES[indice],
            corto=MESES_CORTOS[indice],
            totales=totales_del_mes(libro, clave),
            saldo_final=saldo_hasta(libro, clave + "-31"),
        ))

    total = totales_del_anio(libro, anio)
    return ResumenAnual(
        anio=anio,
        meses=meses,
        total=total,
        meses_con_datos=sum(1 for m in meses if m.hay_datos),
        gasto=reparto_por_tipo(libro, total.por_categoria, GASTO),
        ingreso=reparto_por_tipo(libro, total.por_categoria, INGRESO),
    )


def reparto_por_tipo(libro: Libro, por_categoria: dict[str, float], tipo: str) -> Reparto:
    """Las categorías de un tipo ordenadas por importe, con el peso de cada
    una sobre el total. Es lo que pinta las barras del resumen."""
    filas = [
        FilaReparto(nombre=c.nombre, importe=por_categoria.get(c.nombre, 0.0), porcentaje=0.0)
        for c in libro.categorias
        if c.tipo == tipo
    ]

    # Categorías borradas que aún tienen movimientos antiguos: se agrupan con
    # los gastos para que el total siga cuadrando con la suma real.
    if tipo == GASTO:
        conocidas = {c.nombre for c in libro.categorias}
        for nombre, importe in por_categoria.items():
            if nombre not in conocidas:
                filas.append(FilaReparto(nombre=nombre, importe=importe, porcentaje=0.0))

    total = redondea(sum(f.importe for f in filas))
    for fila in filas:
        fila.porcentaje = fila.importe / total if total > 0 else 0.0
    filas.sort(key=lambda f: f.importe, reverse=True)
    return Reparto(total=total, filas=filas)


# --- presupuesto -----------------------------------------------------------

@dataclass
class FilaPresupuesto:
    nombre: str
    presupuesto: float
    real: float

    @property
    def disponible(self) -> float:
        return redondea(self.presupuesto - self.real)

    @property
    def consumido(self) -> float:
        """Fracción del tope consumida. Sin tope devuelve infinito si hay
        gasto, para que la barra salga en rojo en vez de vacía."""
        if self.presupuesto > 0:
            return self.real / self.presupuesto
        return float("inf") if self.real > 0 else 0.0


@dataclass
class Presupuesto:
    mes: str
    filas: list[FilaPresupuesto]
    ingresos: float
    aportado: float
    objetivo_inversion: float

    @property
    def presupuestado(self) -> float:
        return redondea(sum(f.presupuesto for f in self.filas))

    @property
    def gastado(self) -> float:
        return redondea(sum(f.real for f in self.filas))

    @property
    def disponible(self) -> float:
        return redondea(self.presupuestado - self.gastado)

    @property
    def consumido(self) -> float:
        return self.gastado / self.presupuestado if self.presupuestado > 0 else 0.0

    @property
    def margen(self) -> float:
        """Lo que ingresas menos lo que tenías previsto gastar."""
        return redondea(self.ingresos - self.presupuestado)

    @property
    def pendiente(self) -> float:
        return redondea(max(0.0, self.objetivo_inversion - self.aportado))


def presupuesto_del_mes(libro: Libro, mes: str) -> Presupuesto:
    t = totales_del_mes(libro, mes)
    return Presupuesto(
        mes=mes,
        filas=[
            FilaPresupuesto(
                nombre=c.nombre,
                presupuesto=c.presupuesto,
                real=t.por_categoria.get(c.nombre, 0.0),
            )
            for c in libro.categorias
            if c.tipo == GASTO
        ],
        ingresos=t.ingresos,
        aportado=t.inversion,
        objetivo_inversion=libro.ajustes.objetivo_inversion,
    )


# --- cartera de inversión --------------------------------------------------

@dataclass
class FilaActivo:
    nombre: str
    aportacion_inicial: float
    aportado_banco: float
    aportado_gratis: float
    valor_mercado: float
    ultima_valoracion: str

    @property
    def total_aportado(self) -> float:
        """Las tres formas de que entre dinero, sumadas. Ninguna es
        rentabilidad."""
        return redondea(self.aportacion_inicial + self.aportado_banco + self.aportado_gratis)

    @property
    def generado(self) -> float:
        """Lo único que ha hecho el mercado: lo que vale hoy menos todo lo
        que has metido, vengas de donde vengas."""
        return redondea(self.valor_mercado - self.total_aportado)

    @property
    def rentabilidad(self) -> float:
        return self.generado / self.total_aportado if self.total_aportado > 0 else 0.0


@dataclass
class PuntoHistorico:
    id: str
    fecha: str
    aportado: float
    valor_mercado: float

    @property
    def generado(self) -> float:
        return redondea(self.valor_mercado - self.aportado)

    @property
    def rentabilidad(self) -> float:
        return self.generado / self.aportado if self.aportado > 0 else 0.0


@dataclass
class Cartera:
    activos: list[FilaActivo]
    historico: list[PuntoHistorico]
    sin_asignar_banco: float
    sin_asignar_gratis: float

    def _suma(self, campo: str) -> float:
        return redondea(sum(getattr(a, campo) for a in self.activos))

    @property
    def aportacion_inicial(self) -> float:
        return self._suma("aportacion_inicial")

    @property
    def aportado_banco(self) -> float:
        return self._suma("aportado_banco")

    @property
    def aportado_gratis(self) -> float:
        return self._suma("aportado_gratis")

    @property
    def total_aportado(self) -> float:
        return self._suma("total_aportado")

    @property
    def valor_mercado(self) -> float:
        return self._suma("valor_mercado")

    @property
    def generado(self) -> float:
        return redondea(self.valor_mercado - self.total_aportado)

    @property
    def rentabilidad(self) -> float:
        return self.generado / self.total_aportado if self.total_aportado > 0 else 0.0

    @property
    def ganado_sin_poner(self) -> float:
        """Lo que ha crecido la cartera sin que salga de tu bolsillo:
        el mercado más lo que te han regalado."""
        return redondea(self.generado + self.aportado_gratis)


def cartera(libro: Libro) -> Cartera:
    aportaciones = [m for m in libro.movimientos if libro.tipo_de(m.categoria) == INVERSION]

    activos = []
    for activo in libro.activos:
        del_banco = redondea(sum(m.importe for m in aportaciones if m.activo == activo.nombre))
        gratis = redondea(sum(g.importe for g in libro.aportaciones_gratis if g.activo == activo.nombre))
        activos.append(FilaActivo(
            nombre=activo.nombre,
            aportacion_inicial=activo.aportacion_inicial,
            aportado_banco=del_banco,
            aportado_gratis=gratis,
            valor_mercado=activo.valor_mercado,
            ultima_valoracion=activo.ultima_valoracion,
        ))

    resultado = Cartera(
        activos=activos,
        historico=[],
        sin_asignar_banco=0.0,
        sin_asignar_gratis=0.0,
    )

    # Si esto no es cero, hay aportaciones apuntadas sin decir a qué activo
    # fueron y los totales por activo no cuadran con el total real.
    total_banco = redondea(sum(m.importe for m in aportaciones))
    total_gratis = redondea(sum(g.importe for g in libro.aportaciones_gratis))
    resultado.sin_asignar_banco = redondea(total_banco - resultado.aportado_banco)
    resultado.sin_asignar_gratis = redondea(total_gratis - resultado.aportado_gratis)
    resultado.historico = _historico(libro, aportaciones)
    return resultado


def _historico(libro: Libro, aportaciones: list[Movimiento]) -> list[PuntoHistorico]:
    """Para cada valoración apuntada, cuánto llevabas aportado ese día. La
    diferencia con lo que valía es lo que había hecho el mercado hasta ahí."""
    inicial = redondea(sum(a.aportacion_inicial for a in libro.activos))
    puntos = []
    for valoracion in sorted(libro.historico, key=lambda v: v.fecha):
        del_banco = sum(m.importe for m in aportaciones if m.fecha <= valoracion.fecha)
        gratis = sum(g.importe for g in libro.aportaciones_gratis if g.fecha <= valoracion.fecha)
        puntos.append(PuntoHistorico(
            id=valoracion.id,
            fecha=valoracion.fecha,
            aportado=redondea(inicial + del_banco + gratis),
            valor_mercado=valoracion.valor_mercado,
        ))
    return puntos


# --- indicadores -----------------------------------------------------------

@dataclass
class Indicadores:
    anio: int
    saldo_banco: float
    meses_con_datos: int
    ahorro_medio: float
    gasto_medio: float
    tasa_ahorro: float
    mes_mayor_gasto: str
    meses_de_colchon: float
    inversion_anual: float
    total_aportado: float
    valor_cartera: float
    generado_mercado: float
    patrimonio: float


def indicadores(libro: Libro, anio: int) -> Indicadores:
    resumen = resumen_anual(libro, anio)
    inversiones = cartera(libro)
    saldo = saldo_banco(libro)
    meses = resumen.meses_con_datos

    gasto_medio = redondea(resumen.total.gastos / meses) if meses else 0.0
    mes_mayor = max(resumen.meses, key=lambda m: m.totales.gastos, default=None)

    return Indicadores(
        anio=anio,
        saldo_banco=saldo,
        meses_con_datos=meses,
        ahorro_medio=redondea(resumen.total.ahorro / meses) if meses else 0.0,
        gasto_medio=gasto_medio,
        tasa_ahorro=resumen.total.tasa_ahorro,
        mes_mayor_gasto=mes_mayor.nombre if mes_mayor and mes_mayor.totales.gastos > 0 else "",
        # Cuántos meses aguantarías con lo que hay en el banco si dejaras de
        # ingresar y siguieras gastando tu media.
        meses_de_colchon=saldo / gasto_medio if gasto_medio > 0 else 0.0,
        inversion_anual=resumen.total.inversion,
        total_aportado=inversiones.total_aportado,
        valor_cartera=inversiones.valor_mercado,
        generado_mercado=inversiones.generado,
        patrimonio=redondea(saldo + inversiones.valor_mercado),
    )


# --- listas para los selectores --------------------------------------------

def anios_con_datos(libro: Libro) -> list[int]:
    """De más reciente a más antiguo, con el año en curso siempre incluido
    para que la lista nunca salga vacía."""
    anios = {anio_de(m.fecha) for m in libro.movimientos if es_fecha(m.fecha)}
    anios.add(date.today().year)
    return sorted(anios, reverse=True)


def meses_con_datos(libro: Libro) -> list[str]:
    """Igual que los años, pero por mes y con el mes actual siempre presente."""
    meses = {mes_de(m.fecha) for m in libro.movimientos if es_fecha(m.fecha)}
    meses.add(mes_de(hoy()))
    return sorted(meses, reverse=True)
