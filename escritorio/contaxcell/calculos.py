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
    GASTO, INGRESO, INVERSION, MESES, MESES_CORTOS, PASO, VECES_AL_ANIO,
    Libro, Movimiento, Periodico,
    Cotizacion,
    anio_de, clave_mes, es_fecha, hoy, mes_de, redondea, redondea_titulos,
    suma_dias, suma_meses,
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
    categoria: str = ""
    # Participaciones que se tienen, sumando las compras que las traían.
    titulos: float = 0.0
    # Nadie ha dicho todavía lo que vale. No es lo mismo que valer cero: si se
    # tomara por cero, un activo recién importado diría que has perdido todo
    # lo que metiste. Mientras no se diga otra cosa se da por hecho que vale
    # lo aportado, y así lo generado es cero en vez de ser una alarma falsa.
    sin_valorar: bool = False
    # La cotizacion de la que sale el precio, si la hay.
    simbolo: str = ""
    # Si el valor de arriba viene de una cotizacion y no de lo que escribiste.
    cotizado: bool = False

    @property
    def precio_hoy(self) -> float:
        """Lo que vale hoy una participación.

        No hay que apuntarlo: sale de dividir lo que vale el activo entre las
        participaciones que hay. Con este precio ya se puede saber cómo va
        cada compra por separado, sin esperar a ninguna API. Cuando llegue,
        lo único que cambia es de dónde sale el número.
        """
        return self.valor_mercado / self.titulos if self.titulos > 0 else 0.0

    @property
    def hay_titulos(self) -> bool:
        """Si se sabe en participaciones o solo en euros. Las aportaciones
        apuntadas a mano no las traen, y entonces no hay evolución por
        compra que enseñar."""
        return self.titulos > 0

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

    @property
    def sin_valorar(self) -> list[FilaActivo]:
        """Los activos de los que todavía no se ha dicho lo que valen.

        Mientras estén así, su rentabilidad sale como cero y la de la cartera
        entera se queda corta. Por eso la pantalla avisa.
        """
        return [a for a in self.activos if a.sin_valorar]

    @property
    def aportado_sin_valorar(self) -> float:
        return redondea(sum(a.total_aportado for a in self.sin_valorar))


def cartera(libro: Libro) -> Cartera:
    aportaciones = [m for m in libro.movimientos if libro.tipo_de(m.categoria) == INVERSION]

    activos = []
    for activo in libro.activos:
        del_banco = redondea(sum(m.importe for m in aportaciones if m.activo == activo.nombre))
        gratis = redondea(sum(g.importe for g in libro.aportaciones_gratis if g.activo == activo.nombre))
        # Los títulos que compró una bonificación reinvertida son títulos
        # igual que los demás: cuentan para el precio y para lo que vale.
        titulos = redondea_titulos(
            sum(m.titulos for m in aportaciones if m.activo == activo.nombre)
            + sum(g.titulos for g in libro.aportaciones_gratis
                  if g.activo == activo.nombre))
        # Sin fecha de valoración y sin valor es que nunca se ha dicho lo que
        # vale, no que valga cero. Poner un cero y una fecha sí es decir que
        # se ha ido a cero, y eso se respeta.
        sin_valorar = not activo.ultima_valoracion and not activo.valor_mercado

        # Si el activo tiene cotizacion y sabemos lo que valia el ultimo dia,
        # manda el precio: se apunta solo y es mas de fiar que un numero
        # escrito a mano hace tres meses. Sin cotizacion, todo sigue igual.
        cierre = ultima_cotizacion(libro, activo.simbolo)
        valor = activo.valor_mercado
        valorado = activo.ultima_valoracion
        # Hacen falta las dos cosas: el precio de una participacion y cuantas
        # tienes. Sin titulos no hay nada que multiplicar, y ese activo se
        # sigue valorando a mano aunque tenga cotizacion puesta.
        cotizado = cierre is not None and titulos > 0
        if cotizado:
            valor = redondea(titulos * cierre.precio)
            valorado = cierre.fecha
            sin_valorar = False

        fila = FilaActivo(
            nombre=activo.nombre,
            aportacion_inicial=activo.aportacion_inicial,
            aportado_banco=del_banco,
            aportado_gratis=gratis,
            valor_mercado=valor,
            ultima_valoracion=valorado,
            categoria=activo.categoria,
            titulos=titulos,
            sin_valorar=sin_valorar,
            simbolo=activo.simbolo,
            cotizado=cotizado,
        )
        if sin_valorar:
            fila.valor_mercado = fila.total_aportado
        activos.append(fila)

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


# --- pagos periódicos ------------------------------------------------------

# Tope de seguridad al recorrer vencimientos. Con un semanal desde hace veinte
# años salen mil y pico fechas; más que eso es un dato corrupto, y el bucle
# tiene que parar igualmente en vez de colgar la ventana.
TOPE_VENCIMIENTOS = 4000


def vencimiento(periodico: Periodico, numero: int) -> str:
    """La fecha del pago que hace `numero` (el primero es el cero).

    Se cuenta siempre desde `desde` y nunca desde el pago anterior: así los
    recibos del día 31 vuelven al 31 después de pasar por un febrero corto,
    en vez de quedarse en el 28 para siempre.
    """
    dias, meses = PASO.get(periodico.periodo, (0, 1))
    if dias:
        return suma_dias(periodico.desde, dias * numero)
    return suma_meses(periodico.desde, meses * numero)


def vencimientos(periodico: Periodico, hasta: str, desde: str = "") -> list[str]:
    """Las fechas en las que toca pagar, hasta `hasta` incluida.

    Con `desde` se recorta por abajo, para pedir solo lo que falta. La fecha
    de fin del propio periódico manda siempre: lo que se acaba, se acaba.
    """
    if not es_fecha(periodico.desde) or not es_fecha(hasta) or hasta < periodico.desde:
        return []
    tope = min(hasta, periodico.hasta) if periodico.hasta else hasta

    fechas = []
    for numero in range(TOPE_VENCIMIENTOS):
        fecha = vencimiento(periodico, numero)
        if not fecha or fecha > tope:
            break
        if not desde or fecha >= desde:
            fechas.append(fecha)
    return fechas


def proximo_vencimiento(periodico: Periodico, desde: str = "") -> str:
    """El siguiente pago a partir de `desde` (hoy si no se dice otra cosa)."""
    referencia = desde if es_fecha(desde) else hoy()
    if not es_fecha(periodico.desde):
        return ""
    for numero in range(TOPE_VENCIMIENTOS):
        fecha = vencimiento(periodico, numero)
        if not fecha or (periodico.hasta and fecha > periodico.hasta):
            return ""
        if fecha >= referencia:
            return fecha
    return ""


def esta_vigente(periodico: Periodico, fecha: str = "") -> bool:
    """Si sigue en marcha: encendido y sin haber llegado a su fecha de fin.

    Uno terminado no es lo mismo que uno apagado. El apagado puede volver; el
    terminado ya cumplió, y por eso ninguno de los dos suma en el total del
    mes pero se cuentan por separado.
    """
    if not periodico.encendido:
        return False
    referencia = fecha if es_fecha(fecha) else hoy()
    return not periodico.hasta or periodico.hasta >= referencia


def coste_mensual(periodico: Periodico) -> float:
    """Lo que supone al mes, para poder sumar cosas de distinto periodo.

    Un seguro anual de 240 € son 20 € al mes aunque solo se pague una vez.
    No se apunta así en ningún sitio: es solo para poder comparar.
    """
    return redondea(periodico.importe * VECES_AL_ANIO.get(periodico.periodo, 12) / 12)


def pendientes(libro: Libro, hasta: str) -> list[tuple[Periodico, list[str]]]:
    """Lo que cada periódico encendido tiene vencido y sin apuntar.

    Arranca en el día siguiente al último apuntado. Por eso borrar a mano un
    movimiento que salió solo no lo resucita: el periódico ya pasó por esa
    fecha y no vuelve sobre sus pasos.
    """
    resultado = []
    for periodico in libro.periodicos:
        if not periodico.encendido:
            continue
        arranque = suma_dias(periodico.apuntado_hasta, 1) if periodico.apuntado_hasta else ""
        fechas = vencimientos(periodico, hasta, arranque)
        if fechas:
            resultado.append((periodico, fechas))
    return resultado


def saltar_lo_pasado(periodico: Periodico, hasta: str) -> None:
    """Adelanta la marca hasta el último vencimiento anterior a `hasta`.

    Es lo que hay que hacer al volver a encender uno que estuvo apagado: esos
    meses no se pagaron, así que no se apuntan. Y al crear uno con fecha
    antigua cuando se dice que no se rellene el pasado.

    Solo adelanta, nunca retrasa: si no, apagar y encender el mismo día
    volvería a apuntar el pago de ese día.
    """
    pasados = [f for f in vencimientos(periodico, hasta) if f < hasta]
    if pasados and pasados[-1] > periodico.apuntado_hasta:
        periodico.apuntado_hasta = pasados[-1]


def apuntar_pendientes(libro: Libro, hasta: str) -> list[Movimiento]:
    """Convierte en movimientos de verdad todo lo vencido y sin apuntar.

    Es la única función de este módulo que modifica el libro. Vive aquí de
    todos modos porque es la regla del dominio, no interfaz: no toca disco ni
    ventana, y se prueba sin abrir nada.
    """
    creados = []
    for periodico, fechas in pendientes(libro, hasta):
        for fecha in fechas:
            creados.append(Movimiento(
                fecha=fecha,
                descripcion=periodico.nombre,
                categoria=periodico.categoria,
                importe=periodico.importe,
                activo=periodico.activo,
                origen=periodico.id,
            ))
        periodico.apuntado_hasta = fechas[-1]
    libro.movimientos.extend(creados)
    return creados


@dataclass
class ResumenPeriodicos:
    """Lo que suman los pagos periódicos, todo puesto en meses."""

    encendidos: int = 0
    apagados: int = 0
    terminados: int = 0
    gasto: float = 0.0
    ingreso: float = 0.0
    inversion: float = 0.0

    @property
    def total(self) -> int:
        return self.encendidos + self.apagados + self.terminados


def resumen_periodicos(libro: Libro, fecha: str = "") -> ResumenPeriodicos:
    """Cuánto se va y cuánto entra al mes por lo que sigue en marcha.

    Ni los apagados ni los terminados suman: meter en el total de este mes un
    gimnasio del que te diste de baja, o la última cuota de un préstamo que ya
    pagaste, engañaría.
    """
    resumen = ResumenPeriodicos()
    for periodico in libro.periodicos:
        if not esta_vigente(periodico, fecha):
            if periodico.encendido:
                resumen.terminados += 1
            else:
                resumen.apagados += 1
            continue
        resumen.encendidos += 1
        al_mes = coste_mensual(periodico)
        tipo = libro.tipo_de(periodico.categoria)
        if tipo == INGRESO:
            resumen.ingreso = redondea(resumen.ingreso + al_mes)
        elif tipo == INVERSION:
            resumen.inversion = redondea(resumen.inversion + al_mes)
        else:
            resumen.gasto = redondea(resumen.gasto + al_mes)
    return resumen


def apuntados_por(libro: Libro, periodico: Periodico) -> int:
    """Cuántos movimientos del libro los apuntó este periódico."""
    return sum(1 for m in libro.movimientos if m.origen == periodico.id)


# --- las compras, una a una ------------------------------------------------

@dataclass
class Compra:
    """Una aportación concreta con lo que compró y lo que vale hoy.

    Es lo que contesta a «los mismos 100 € de cada semana, ¿cómo van?».
    Cien euros compran más participaciones cuando el fondo está barato, y
    esa compra sube más que la de la semana en que estaba caro.
    """

    id: str
    fecha: str
    descripcion: str
    importe: float
    titulos: float
    precio_hoy: float

    @property
    def precio_pagado(self) -> float:
        """Lo que costó cada participación aquel día."""
        return self.importe / self.titulos if self.titulos > 0 else 0.0

    @property
    def valor_hoy(self) -> float:
        return redondea(self.titulos * self.precio_hoy)

    @property
    def generado(self) -> float:
        return redondea(self.valor_hoy - self.importe)

    @property
    def rentabilidad(self) -> float:
        return self.generado / self.importe if self.importe > 0 else 0.0


def compras_de(libro: Libro, nombre_activo: str) -> list[Compra]:
    """Las aportaciones a ese activo que dijeron cuántos títulos compraban.

    Las apuntadas a mano no lo dicen y se quedan fuera: sin participaciones
    no se puede saber cómo ha ido esa compra en concreto, solo cuánto se
    metió. Van de la más reciente a la más antigua.
    """
    fila = next((a for a in cartera(libro).activos if a.nombre == nombre_activo), None)
    if fila is None:
        return []

    # Si nadie ha dicho lo que vale el activo, no hay precio de hoy y no se
    # inventa: para la cartera se da por hecho que vale lo aportado, pero eso
    # es el precio medio, y usarlo aquí haría que la compra barata saliera
    # ganando y la cara perdiendo por pura aritmética.
    precio = 0.0 if fila.sin_valorar else fila.precio_hoy
    compras = [
        Compra(id=m.id, fecha=m.fecha, descripcion=m.descripcion,
               importe=m.importe, titulos=m.titulos, precio_hoy=precio)
        for m in libro.movimientos
        if m.activo == nombre_activo and m.titulos > 0
        and libro.tipo_de(m.categoria) == INVERSION
    ]
    return sorted(compras, key=lambda c: (c.fecha, c.id), reverse=True)


@dataclass
class GrupoCartera:
    """Los activos de una misma categoría, sumados."""

    categoria: str
    activos: list[FilaActivo]
    # Qué parte de la cartera es este grupo. Lo rellena `por_categoria`, que
    # es quien conoce el total.
    peso: float = 0.0

    def _suma(self, campo: str) -> float:
        return redondea(sum(getattr(a, campo) for a in self.activos))

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


SIN_CATEGORIA = "Sin categoría"


def por_categoria(cartera_actual: Cartera) -> list[GrupoCartera]:
    """La cartera agrupada, de más dinero a menos.

    Sirve para ver cuánto hay en índices y cuánto en acciones sueltas aunque
    haya diez fondos distintos. Lo que no tiene categoría se agrupa aparte en
    vez de esconderse.
    """
    grupos: dict[str, list[FilaActivo]] = {}
    for activo in cartera_actual.activos:
        grupos.setdefault(activo.categoria or SIN_CATEGORIA, []).append(activo)

    total = cartera_actual.valor_mercado
    resultado = [GrupoCartera(categoria=nombre, activos=lista)
                 for nombre, lista in grupos.items()]
    for grupo in resultado:
        grupo.peso = grupo.valor_mercado / total if total > 0 else 0.0
    return sorted(resultado, key=lambda g: -g.valor_mercado)


# --- cotizaciones ----------------------------------------------------------

def cotizaciones_de(libro: Libro, simbolo: str) -> list[Cotizacion]:
    """Los cierres guardados de esa cotización, del más antiguo al más nuevo."""
    codigo = (simbolo or "").strip().upper()
    if not codigo:
        return []
    return sorted((c for c in libro.cotizaciones if c.simbolo == codigo),
                  key=lambda c: c.fecha)


def ultima_cotizacion(libro: Libro, simbolo: str, hasta: str = "") -> Cotizacion | None:
    """El último cierre conocido, o el último hasta una fecha.

    Se busca «hasta» y no «en» a propósito: los fines de semana y los
    festivos no tienen cierre, y preguntar por un sábado tiene que devolver
    el viernes, no nada.
    """
    encontradas = cotizaciones_de(libro, simbolo)
    if hasta:
        encontradas = [c for c in encontradas if c.fecha <= hasta]
    return encontradas[-1] if encontradas else None


def guardar_cotizaciones(libro: Libro, simbolo: str, nuevas: list) -> int:
    """Mete los cierres que traiga el servidor, pisando los repetidos.

    Devuelve cuántos son nuevos. Un cierre puede corregirse el mismo día, así
    que el que llega manda sobre el que hubiera.
    """
    codigo = (simbolo or "").strip().upper()
    if not codigo:
        return 0

    por_fecha = {c.fecha: c for c in libro.cotizaciones if c.simbolo == codigo}
    antes = len(por_fecha)
    for cotizacion in nuevas:
        if cotizacion.fecha and cotizacion.precio > 0:
            por_fecha[cotizacion.fecha] = cotizacion

    libro.cotizaciones = [c for c in libro.cotizaciones if c.simbolo != codigo]
    libro.cotizaciones.extend(por_fecha[f] for f in sorted(por_fecha))
    return len(por_fecha) - antes


def simbolos_del_libro(libro: Libro) -> list[str]:
    """Las cotizaciones que hay que mantener al día: las de los activos que
    tienen una puesta. Sin repetir, que dos activos pueden compartirla."""
    vistos = []
    for activo in libro.activos:
        codigo = (activo.simbolo or "").strip().upper()
        if codigo and codigo not in vistos:
            vistos.append(codigo)
    return vistos


def desde_cuando_hacen_falta(libro: Libro, simbolo: str) -> str:
    """Desde qué fecha interesa el histórico de esa cotización.

    Desde la primera aportación al activo: antes de comprar, lo que valiera
    no cambia nada de lo tuyo. Así la primera petición no se trae veinte años
    de cierres para nada.
    """
    codigo = (simbolo or "").strip().upper()
    nombres = {a.nombre for a in libro.activos
               if (a.simbolo or "").strip().upper() == codigo}
    fechas = [m.fecha for m in libro.movimientos
              if m.activo in nombres and es_fecha(m.fecha)]
    fechas += [g.fecha for g in libro.aportaciones_gratis
               if g.activo in nombres and es_fecha(g.fecha)]
    return min(fechas) if fechas else hoy()
