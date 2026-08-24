"""Puente con Excel: traer la contabilidad de la plantilla y volcarla a .xlsx.

Importar y exportar usan la misma disposición de celdas que la plantilla
original, así que un archivo exportado se puede volver a importar, y el que
descargues de Google Sheets se lee sin tocar nada.

Los lectores no van a ciegas por número de fila: buscan las cabeceras y leen
hacia abajo hasta que se acaban los datos. Así aguantan que la hoja tenga más
categorías de las previstas o alguna fila insertada por el camino.

La exportación escribe valores ya calculados, no fórmulas: lo que se ve en la
aplicación es exactamente lo que aparece en el archivo, sin depender de que
Excel o Google Sheets recalculen nada.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from . import calculos
from .modelo import (
    GASTO, INGRESO, INVERSION,
    Activo, AportacionGratis, Categoria, Libro, Movimiento, Valoracion,
    es_fecha, hoy, mes_de, nombre_mes, redondea,
)

EUROS = '#,##0.00\\ "€"'
PORCENTAJE = "0.0%"
FECHA = "dd/mm/yyyy"
ENTERO = "0"
DECIMAL = "0.0"

# Hasta dónde miramos al leer. Son topes de seguridad para no recorrer una
# hoja de un millón de filas si el archivo viene raro.
_MAX_FILAS = 20000
_MAX_BLOQUE = 500


class ErrorDeImportacion(Exception):
    """Algo que el usuario puede entender y arreglar."""


# --- conversión de celdas --------------------------------------------------

def _a_fecha(valor) -> str:
    """Cualquier cosa que parezca una fecha, en 'AAAA-MM-DD'."""
    if isinstance(valor, dt.datetime):
        return valor.date().isoformat()
    if isinstance(valor, dt.date):
        return valor.isoformat()
    if isinstance(valor, str):
        texto = valor.strip()
        if es_fecha(texto[:10]):
            return texto[:10]
        # Formato español: 24/08/2026, 24-8-26.
        for separador in ("/", "-", "."):
            partes = texto.split(separador)
            if len(partes) == 3 and all(p.strip().isdigit() for p in partes):
                dia, mes, anio = (int(p) for p in partes)
                if anio < 100:
                    anio += 2000
                try:
                    return dt.date(anio, mes, dia).isoformat()
                except ValueError:
                    return ""
    return ""


def _a_texto(valor) -> str:
    if valor is None:
        return ""
    if isinstance(valor, (dt.datetime, dt.date)):
        return _a_fecha(valor)
    return str(valor).strip()


def _a_numero(valor) -> float:
    if isinstance(valor, bool):
        return 0.0
    if isinstance(valor, (int, float)):
        return redondea(valor)
    texto = _a_texto(valor)
    if not texto:
        return 0.0
    limpio = "".join(c for c in texto if c.isdigit() or c in ",.-").replace(",", ".")
    try:
        return redondea(float(limpio))
    except ValueError:
        return 0.0


def _celda(hoja, fila: int, columna: int):
    return hoja.cell(row=fila, column=columna).value


def _es_total(texto: str) -> bool:
    return texto.upper().startswith("TOTAL")


def _buscar_fila(hoja, columna: int, comienza_por: str, desde: int = 1, hasta: int = 120) -> int:
    """Número de la fila cuya celda empieza por ese texto, o 0 si no está."""
    objetivo = comienza_por.upper()
    for fila in range(desde, hasta + 1):
        if _a_texto(_celda(hoja, fila, columna)).upper().startswith(objetivo):
            return fila
    return 0


# --- lectura ---------------------------------------------------------------

def importar(ruta: Path | str) -> tuple[Libro, list[str]]:
    """Devuelve el libro leído y una lista de avisos que conviene enseñar."""
    try:
        # data_only=True da el último resultado calculado de las fórmulas, que
        # es lo que nos interesa: no queremos las fórmulas, queremos los datos.
        cuaderno = load_workbook(ruta, data_only=True)
    except Exception as error:  # openpyxl lanza de todo con archivos raros
        raise ErrorDeImportacion(
            "No se ha podido abrir el archivo. Comprueba que es un .xlsx y que "
            f"no lo tienes abierto en Excel ahora mismo.\n\n({error})"
        ) from error

    try:
        if "Movimientos" not in cuaderno.sheetnames:
            raise ErrorDeImportacion(
                "El archivo no tiene ninguna hoja llamada «Movimientos».\n\n"
                "¿Seguro que es la contabilidad y no otro Excel? Si la tuya está en "
                "Google Sheets, descárgala con Archivo → Descargar → Microsoft Excel."
            )

        libro = Libro()
        avisos: list[str] = []
        movimientos = cuaderno["Movimientos"]

        libro.ajustes.saldo_inicial = _a_numero(movimientos["K3"].value)
        libro.categorias = _leer_categorias(movimientos)
        libro.movimientos = _leer_movimientos(movimientos)
        _completar_categorias_sueltas(libro, avisos)

        if "Presupuesto" in cuaderno.sheetnames:
            _leer_presupuesto(cuaderno["Presupuesto"], libro)
        if "Inversiones" in cuaderno.sheetnames:
            _leer_inversiones(cuaderno["Inversiones"], libro)
    finally:
        cuaderno.close()

    if not libro.movimientos:
        avisos.append(
            "No se ha encontrado ningún movimiento con fecha e importe. Revisa que la "
            "hoja tenga las fechas en la columna A y los importes en la E o la F."
        )
    return libro, avisos


def _leer_categorias(hoja) -> list[Categoria]:
    """Panel de control: nombres en J6 hacia abajo y su tipo en la columna K."""
    categorias = []
    for fila in range(6, 40):
        nombre = _a_texto(_celda(hoja, fila, 10))
        if not nombre or _es_total(nombre):
            break
        crudo = _a_texto(_celda(hoja, fila, 11)).lower()
        if "ingreso" in crudo:
            tipo = INGRESO
        elif "inversi" in crudo:
            tipo = INVERSION
        else:
            tipo = GASTO
        categorias.append(Categoria(nombre=nombre, tipo=tipo))
    return categorias or Libro.vacio().categorias


def _leer_movimientos(hoja) -> list[Movimiento]:
    """Fecha en A, descripción en C, categoría en D, importe en E (ingreso) o
    F (gasto), activo en H. B (Mes) y G (Balance) son fórmulas y se ignoran."""
    movimientos = []
    for fila in range(2, min(hoja.max_row, _MAX_FILAS) + 1):
        fecha = _a_fecha(_celda(hoja, fila, 1))
        if not fecha:
            continue
        ingreso = _a_numero(_celda(hoja, fila, 5))
        gasto = _a_numero(_celda(hoja, fila, 6))
        importe = abs(ingreso or gasto)
        if not importe:
            continue
        movimientos.append(Movimiento(
            fecha=fecha,
            descripcion=_a_texto(_celda(hoja, fila, 3)),
            categoria=_a_texto(_celda(hoja, fila, 4)),
            importe=importe,
            activo=_a_texto(_celda(hoja, fila, 8)),
        ))
    return movimientos


def _completar_categorias_sueltas(libro: Libro, avisos: list[str]) -> None:
    """Una categoría que aparezca en los movimientos pero no en el panel se
    añade como gasto, para que ninguna fila quede huérfana."""
    conocidas = {c.nombre for c in libro.categorias}
    for movimiento in libro.movimientos:
        nombre = movimiento.categoria
        if nombre and nombre not in conocidas:
            conocidas.add(nombre)
            libro.categorias.append(Categoria(nombre=nombre, tipo=GASTO))
            avisos.append(
                f"La categoría «{nombre}» no estaba en el panel de la hoja: la he "
                "añadido como gasto. Cámbiale el tipo en Ajustes si no lo era."
            )


def _leer_presupuesto(hoja, libro: Libro) -> None:
    """Topes mensuales por categoría y objetivo de inversión.

    Los nombres de la columna A pueden ser fórmulas que apuntan al panel de
    Movimientos. Si el archivo no trae el resultado calculado, tiramos de esa
    correspondencia: la fila n-ésima es la categoría de gasto n-ésima.
    """
    cabecera = _buscar_fila(hoja, 1, "CATEGOR") or 4
    gastos = [c for c in libro.categorias if c.tipo == GASTO]
    por_nombre = {c.nombre: c for c in libro.categorias}

    # El bloque termina en la fila «TOTAL». Una fila vacía por el medio no lo
    # corta: es una categoría sin tope, y su hueco cuenta para que la
    # correspondencia por posición siga cuadrando con las de abajo.
    vacias_seguidas = 0
    for indice, fila in enumerate(range(cabecera + 1, cabecera + 1 + _MAX_BLOQUE)):
        nombre = _a_texto(_celda(hoja, fila, 1))
        celda_importe = _celda(hoja, fila, 2)
        if _es_total(nombre):
            break
        if not nombre and celda_importe is None:
            vacias_seguidas += 1
            if vacias_seguidas >= 3:
                break
        else:
            vacias_seguidas = 0
        categoria = por_nombre.get(nombre)
        if categoria is None and indice < len(gastos):
            categoria = gastos[indice]
        if categoria is not None:
            categoria.presupuesto = _a_numero(celda_importe)

    objetivo = _buscar_fila(hoja, 1, "OBJETIVO DE INVERSI")
    if objetivo:
        libro.ajustes.objetivo_inversion = _a_numero(_celda(hoja, objetivo, 2))


def _leer_inversiones(hoja, libro: Libro) -> None:
    _leer_activos(hoja, libro)
    _leer_aportaciones_gratis(hoja, libro)
    _leer_historico(hoja, libro)


def _leer_activos(hoja, libro: Libro) -> None:
    """Nombre en A, aportación inicial en B, valor de mercado en F, fecha de
    la última valoración en I. Las columnas C, D, E, G y H se recalculan."""
    cabecera = _buscar_fila(hoja, 1, "ACTIVO") or 5
    for fila in range(cabecera + 1, cabecera + 1 + _MAX_BLOQUE):
        nombre = _a_texto(_celda(hoja, fila, 1))
        if not nombre or _es_total(nombre):
            break
        libro.activos.append(Activo(
            nombre=nombre,
            aportacion_inicial=_a_numero(_celda(hoja, fila, 2)),
            valor_mercado=_a_numero(_celda(hoja, fila, 6)),
            ultima_valoracion=_a_fecha(_celda(hoja, fila, 9)),
        ))


def _leer_aportaciones_gratis(hoja, libro: Libro) -> None:
    """El registro de cashback: su cabecera es la fila con FECHA en A y
    ACTIVO en B, que es lo que la distingue de la tabla de activos."""
    cabecera = 0
    for fila in range(1, 200):
        if (_a_texto(_celda(hoja, fila, 1)).upper() == "FECHA"
                and _a_texto(_celda(hoja, fila, 2)).upper().startswith("ACTIVO")):
            cabecera = fila
            break
    if not cabecera:
        return

    for fila in range(cabecera + 1, cabecera + 1 + _MAX_BLOQUE):
        fecha = _a_fecha(_celda(hoja, fila, 1))
        nombre = _a_texto(_celda(hoja, fila, 1))
        if _es_total(nombre):
            break
        importe = _a_numero(_celda(hoja, fila, 4))
        if not fecha or not importe:
            continue
        libro.aportaciones_gratis.append(AportacionGratis(
            fecha=fecha,
            activo=_a_texto(_celda(hoja, fila, 2)),
            concepto=_a_texto(_celda(hoja, fila, 3)),
            importe=importe,
        ))


def _leer_historico(hoja, libro: Libro) -> None:
    """Vive en las columnas K a N para no estorbar a las tablas de la
    izquierda: fecha en K y valor de mercado en M."""
    cabecera = _buscar_fila(hoja, 11, "FECHA") or 5
    for fila in range(cabecera + 1, cabecera + 1 + _MAX_BLOQUE):
        fecha = _a_fecha(_celda(hoja, fila, 11))
        if not fecha:
            continue
        libro.historico.append(Valoracion(
            fecha=fecha,
            valor_mercado=_a_numero(_celda(hoja, fila, 13)),
        ))


# --- escritura -------------------------------------------------------------

_RELLENO_CABECERA = PatternFill("solid", fgColor="E8EBF0")
_BORDE_CABECERA = Border(bottom=Side(style="thin", color="B6BDC7"))
_NEGRITA = Font(bold=True)
_TITULO = Font(bold=True, size=13)
_NOTA = Font(italic=True, color="6B7280")


def _fecha_excel(iso: str):
    return dt.date.fromisoformat(iso) if es_fecha(iso) else None


def _pon(hoja, fila: int, columna: int, valor, formato: str | None = None,
         fuente: Font | None = None):
    celda = hoja.cell(row=fila, column=columna, value=valor)
    if formato:
        celda.number_format = formato
    if fuente:
        celda.font = fuente
    return celda


def _pon_cabecera(hoja, fila: int, columna_inicial: int, titulos: list[str]) -> None:
    for desplazamiento, titulo in enumerate(titulos):
        celda = _pon(hoja, fila, columna_inicial + desplazamiento, titulo, fuente=_NEGRITA)
        celda.fill = _RELLENO_CABECERA
        celda.border = _BORDE_CABECERA
        celda.alignment = Alignment(horizontal="left")


def _anchos(hoja, columnas: dict[int, float]) -> None:
    for indice, ancho in columnas.items():
        hoja.column_dimensions[get_column_letter(indice)].width = ancho


def exportar(ruta: Path | str, libro: Libro, anio: int) -> Path:
    cuaderno = Workbook()
    cuaderno.remove(cuaderno.active)

    _escribir_movimientos(cuaderno, libro)
    _escribir_resumen(cuaderno, libro, anio)
    _escribir_presupuesto(cuaderno, libro)
    _escribir_inversiones(cuaderno, libro)

    destino = Path(ruta)
    cuaderno.save(destino)
    return destino


def _escribir_movimientos(cuaderno: Workbook, libro: Libro) -> None:
    hoja = cuaderno.create_sheet("Movimientos")
    _anchos(hoja, {1: 12, 2: 16, 3: 34, 4: 24, 5: 14, 6: 14, 7: 14, 8: 20,
                   10: 26, 11: 14, 12: 15})
    _pon_cabecera(hoja, 1, 1, ["Fecha", "Mes", "Descripción", "Categoría",
                               "Ingresos", "Gastos", "Balance", "Activo"])

    fila = 2
    for registro in calculos.con_balance(libro):
        es_ingreso = registro.tipo == INGRESO
        _pon(hoja, fila, 1, _fecha_excel(registro.fecha), FECHA)
        _pon(hoja, fila, 2, nombre_mes(mes_de(registro.fecha)))
        _pon(hoja, fila, 3, registro.descripcion)
        _pon(hoja, fila, 4, registro.categoria)
        _pon(hoja, fila, 5, registro.importe if es_ingreso else None, EUROS)
        _pon(hoja, fila, 6, None if es_ingreso else registro.importe, EUROS)
        _pon(hoja, fila, 7, registro.balance, EUROS)
        _pon(hoja, fila, 8, registro.activo)
        fila += 1

    _escribir_panel(hoja, libro)
    hoja.freeze_panes = "A2"
    if fila > 2:
        hoja.auto_filter.ref = f"A1:H{fila - 1}"


def _escribir_panel(hoja, libro: Libro) -> None:
    """El panel J/K/L de la plantilla. Además de resumir el mes, es lo que
    permite que este mismo archivo se pueda volver a importar: de aquí salen
    las categorías con su tipo y el saldo inicial."""
    mes = mes_de(hoy())
    totales = calculos.totales_del_mes(libro, mes)

    _pon(hoja, 1, 10, "PANEL DE CONTROL", fuente=_TITULO)
    _pon(hoja, 2, 10, "Mes activo")
    _pon(hoja, 2, 11, _fecha_excel(mes + "-01"), "mmmm yyyy")
    _pon(hoja, 3, 10, "Saldo inicial del banco")
    _pon(hoja, 3, 11, libro.ajustes.saldo_inicial, EUROS)

    _pon_cabecera(hoja, 5, 10, ["CATEGORÍA", "TIPO", "MES ACTIVO"])
    fila = 6
    for categoria in libro.categorias:
        _pon(hoja, fila, 10, categoria.nombre)
        _pon(hoja, fila, 11, categoria.tipo)
        _pon(hoja, fila, 12, totales.por_categoria.get(categoria.nombre, 0.0), EUROS)
        fila += 1

    fila += 1
    for nombre, valor, formato in [
        ("TOTAL INGRESOS", totales.ingresos, EUROS),
        ("TOTAL GASTOS", totales.gastos, EUROS),
        ("AHORRO (ingresos − gastos)", totales.ahorro, EUROS),
        ("% de ahorro", totales.tasa_ahorro, PORCENTAJE),
        ("Aportado a inversión", totales.inversion, EUROS),
        ("FLUJO NETO del banco", totales.flujo_neto, EUROS),
        ("Saldo actual del banco", calculos.saldo_banco(libro), EUROS),
    ]:
        _pon(hoja, fila, 10, nombre, fuente=_NEGRITA)
        _pon(hoja, fila, 12, valor, formato)
        fila += 1

    fila += 1
    _pon(hoja, fila, 10, "Generado por ContaXcell. Las columnas B y G están calculadas, "
                         "no son fórmulas.", fuente=_NOTA)


def _escribir_resumen(cuaderno: Workbook, libro: Libro, anio: int) -> None:
    hoja = cuaderno.create_sheet("Resumen")
    resumen = calculos.resumen_anual(libro, anio)
    datos = calculos.indicadores(libro, anio)
    _anchos(hoja, {1: 32, 2: 15, 3: 15, 4: 15, 5: 15, 6: 17})

    _pon(hoja, 1, 1, f"RESUMEN {anio}", fuente=_TITULO)
    _pon_cabecera(hoja, 3, 1, ["Mes", "Ingresos", "Gastos", "Ahorro",
                               "Inversión", "Saldo del banco"])
    fila = 4
    for mes in resumen.meses:
        _pon(hoja, fila, 1, mes.nombre)
        for columna, valor in enumerate(
            [mes.totales.ingresos, mes.totales.gastos, mes.totales.ahorro,
             mes.totales.inversion, mes.saldo_final], start=2
        ):
            _pon(hoja, fila, columna, valor, EUROS)
        fila += 1

    _pon(hoja, fila, 1, f"TOTAL {anio}", fuente=_NEGRITA)
    for columna, valor in enumerate(
        [resumen.total.ingresos, resumen.total.gastos, resumen.total.ahorro,
         resumen.total.inversion, datos.saldo_banco], start=2
    ):
        _pon(hoja, fila, columna, valor, EUROS, _NEGRITA)
    fila += 2

    for titulo, reparto in (("Gasto por categoría", resumen.gasto),
                            ("Ingreso por categoría", resumen.ingreso)):
        _pon_cabecera(hoja, fila, 1, [titulo, "Total año", "% del total"])
        fila += 1
        for registro in reparto.filas:
            if not registro.importe:
                continue
            _pon(hoja, fila, 1, registro.nombre)
            _pon(hoja, fila, 2, registro.importe, EUROS)
            _pon(hoja, fila, 3, registro.porcentaje, PORCENTAJE)
            fila += 1
        _pon(hoja, fila, 1, "Total", fuente=_NEGRITA)
        _pon(hoja, fila, 2, reparto.total, EUROS, _NEGRITA)
        fila += 2

    _pon_cabecera(hoja, fila, 1, ["Indicador", "Valor"])
    fila += 1
    for nombre, valor, formato in [
        ("Saldo actual del banco", datos.saldo_banco, EUROS),
        ("Meses con datos", datos.meses_con_datos, ENTERO),
        ("Ahorro medio mensual", datos.ahorro_medio, EUROS),
        ("Gasto medio mensual", datos.gasto_medio, EUROS),
        ("Tasa de ahorro del año", datos.tasa_ahorro, PORCENTAJE),
        ("Mes de mayor gasto", datos.mes_mayor_gasto or "—", None),
        ("Meses de colchón", datos.meses_de_colchon, DECIMAL),
        ("Aportado a inversión (año)", datos.inversion_anual, EUROS),
        ("Total aportado a la cartera", datos.total_aportado, EUROS),
        ("Valor de la cartera", datos.valor_cartera, EUROS),
        ("Generado por el mercado", datos.generado_mercado, EUROS),
        ("Patrimonio (banco + cartera)", datos.patrimonio, EUROS),
    ]:
        _pon(hoja, fila, 1, nombre)
        _pon(hoja, fila, 2, valor, formato)
        fila += 1


def _escribir_presupuesto(cuaderno: Workbook, libro: Libro) -> None:
    hoja = cuaderno.create_sheet("Presupuesto")
    mes = mes_de(hoy())
    presupuesto = calculos.presupuesto_del_mes(libro, mes)
    _anchos(hoja, {1: 34, 2: 15, 3: 15, 4: 15, 5: 15})

    _pon(hoja, 1, 1, "PRESUPUESTO MENSUAL", fuente=_TITULO)
    _pon(hoja, 2, 1, f"Gasto real y consumo referidos a {nombre_mes(mes)}.", fuente=_NOTA)
    _pon_cabecera(hoja, 4, 1, ["CATEGORÍA", "PRESUPUESTO", "GASTO REAL",
                               "DISPONIBLE", "% CONSUMIDO"])

    fila = 5
    for registro in presupuesto.filas:
        _pon(hoja, fila, 1, registro.nombre)
        _pon(hoja, fila, 2, registro.presupuesto, EUROS)
        _pon(hoja, fila, 3, registro.real, EUROS)
        _pon(hoja, fila, 4, registro.disponible, EUROS)
        consumido = registro.consumido if registro.consumido != float("inf") else None
        _pon(hoja, fila, 5, consumido, PORCENTAJE)
        fila += 1

    _pon(hoja, fila, 1, "TOTAL", fuente=_NEGRITA)
    for columna, valor, formato in [
        (2, presupuesto.presupuestado, EUROS), (3, presupuesto.gastado, EUROS),
        (4, presupuesto.disponible, EUROS), (5, presupuesto.consumido, PORCENTAJE),
    ]:
        _pon(hoja, fila, columna, valor, formato, _NEGRITA)
    fila += 2

    for nombre, valor in [
        ("Ingresos del mes", presupuesto.ingresos),
        ("Margen (ingresos − presupuesto)", presupuesto.margen),
        ("Objetivo de inversión mensual", presupuesto.objetivo_inversion),
        ("Aportado este mes", presupuesto.aportado),
        ("Pendiente de aportar", presupuesto.pendiente),
    ]:
        _pon(hoja, fila, 1, nombre)
        _pon(hoja, fila, 2, valor, EUROS)
        fila += 1


def _escribir_inversiones(cuaderno: Workbook, libro: Libro) -> None:
    hoja = cuaderno.create_sheet("Inversiones")
    datos = calculos.cartera(libro)
    _anchos(hoja, {1: 28, 2: 17, 3: 18, 4: 16, 5: 16, 6: 17, 7: 19, 8: 11, 9: 16,
                   11: 14, 12: 20, 13: 18, 14: 15})

    _pon(hoja, 1, 1, "CARTERA DE INVERSIÓN", fuente=_TITULO)
    _pon(hoja, 2, 1, "Las tres formas de que entre dinero se suman en TOTAL APORTADO. "
                     "Ninguna de las tres es rentabilidad.", fuente=_NOTA)
    _pon(hoja, 3, 1, "GENERADO POR EL MERCADO = Valor de mercado − Total aportado.",
         fuente=_NOTA)

    _pon_cabecera(hoja, 5, 1, ["ACTIVO", "1· APORTACIÓN INICIAL", "2· APORTADO DEL BANCO",
                               "3· APORTADO GRATIS", "TOTAL APORTADO", "VALOR DE MERCADO",
                               "GENERADO POR EL MERCADO", "RENTAB. %", "ÚLTIMA VALORACIÓN"])
    fila = 6
    for activo in datos.activos:
        _pon(hoja, fila, 1, activo.nombre)
        for columna, valor in enumerate(
            [activo.aportacion_inicial, activo.aportado_banco, activo.aportado_gratis,
             activo.total_aportado, activo.valor_mercado, activo.generado], start=2
        ):
            _pon(hoja, fila, columna, valor, EUROS)
        _pon(hoja, fila, 8, activo.rentabilidad, PORCENTAJE)
        _pon(hoja, fila, 9, _fecha_excel(activo.ultima_valoracion), FECHA)
        fila += 1

    _pon(hoja, fila, 1, "TOTAL CARTERA", fuente=_NEGRITA)
    for columna, valor in enumerate(
        [datos.aportacion_inicial, datos.aportado_banco, datos.aportado_gratis,
         datos.total_aportado, datos.valor_mercado, datos.generado], start=2
    ):
        _pon(hoja, fila, columna, valor, EUROS, _NEGRITA)
    _pon(hoja, fila, 8, datos.rentabilidad, PORCENTAJE, _NEGRITA)
    fila += 2

    for nombre, valor, formato in [
        ("Aportado del banco sin asignar a un activo", datos.sin_asignar_banco, EUROS),
        ("Cashback sin asignar a un activo", datos.sin_asignar_gratis, EUROS),
        ("Ganado sin poner dinero (mercado + gratis)", datos.ganado_sin_poner, EUROS),
    ]:
        _pon(hoja, fila, 1, nombre)
        _pon(hoja, fila, 2, valor, formato)
        fila += 1
    fila += 1

    _pon(hoja, fila, 1, "APORTACIONES GRATIS · cashback, promociones, redondeos",
         fuente=_TITULO)
    _pon(hoja, fila + 1, 1, "Dinero que entra en la cartera sin salir de tu cuenta. "
                            "No es un ingreso ni un gasto.", fuente=_NOTA)
    _pon_cabecera(hoja, fila + 2, 1, ["FECHA", "ACTIVO", "CONCEPTO", "IMPORTE"])
    fila += 3
    for aportacion in sorted(libro.aportaciones_gratis, key=lambda a: a.fecha):
        _pon(hoja, fila, 1, _fecha_excel(aportacion.fecha), FECHA)
        _pon(hoja, fila, 2, aportacion.activo)
        _pon(hoja, fila, 3, aportacion.concepto)
        _pon(hoja, fila, 4, aportacion.importe, EUROS)
        fila += 1
    _pon(hoja, fila, 1, "TOTAL GRATIS", fuente=_NEGRITA)
    _pon(hoja, fila, 4, datos.aportado_gratis + datos.sin_asignar_gratis, EUROS, _NEGRITA)

    # El histórico va en las columnas K a N para no chocar con las tablas de
    # la izquierda, igual que en la plantilla.
    _pon(hoja, 1, 11, "HISTÓRICO DE LA CARTERA", fuente=_TITULO)
    _pon_cabecera(hoja, 5, 11, ["FECHA", "APORTADO ACUMULADO", "VALOR DE MERCADO", "GENERADO"])
    fila = 6
    for punto in datos.historico:
        _pon(hoja, fila, 11, _fecha_excel(punto.fecha), FECHA)
        _pon(hoja, fila, 12, punto.aportado, EUROS)
        _pon(hoja, fila, 13, punto.valor_mercado, EUROS)
        _pon(hoja, fila, 14, punto.generado, EUROS)
        fila += 1
