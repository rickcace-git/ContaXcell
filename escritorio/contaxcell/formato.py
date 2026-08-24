"""Cómo se enseñan las cifras y las fechas.

El formato se hace a mano en vez de con `locale` porque el módulo de idioma de
Python depende de lo que tenga configurado cada Windows, y aquí queremos que
todo el mundo vea «1.234,56 €» aunque su equipo esté en inglés.

Aquí vive también el interruptor del botón del ojo: cualquier importe que se
pinte pasa por `euros()`, así que taparlos no depende de acordarse en cada
pantalla.
"""

from __future__ import annotations

from .modelo import MESES, MESES_CORTOS, es_fecha

TAPADO = "••••"

_oculto = False


def ocultar_importes(valor: bool) -> None:
    global _oculto
    _oculto = bool(valor)


def hay_importes_ocultos() -> bool:
    return _oculto


# --- números ---------------------------------------------------------------

def _separa_miles(digitos: str) -> str:
    partes = []
    while len(digitos) > 3:
        partes.insert(0, digitos[-3:])
        digitos = digitos[:-3]
    partes.insert(0, digitos)
    return ".".join(partes)


def numero(valor: float, decimales: int = 2) -> str:
    """Formato español: punto para los miles, coma para los decimales."""
    try:
        cantidad = float(valor)
    except (TypeError, ValueError):
        cantidad = 0.0
    if cantidad != cantidad:  # NaN
        return "—"
    if cantidad in (float("inf"), float("-inf")):
        return "—"

    signo = "-" if cantidad < 0 else ""
    texto = f"{abs(cantidad):.{decimales}f}"
    if decimales:
        entero, decimal = texto.split(".")
        return f"{signo}{_separa_miles(entero)},{decimal}"
    return f"{signo}{_separa_miles(texto)}"


def euros(valor: float, siempre_visible: bool = False) -> str:
    if _oculto and not siempre_visible:
        return TAPADO
    return numero(valor) + " €"


def euros_con_signo(valor: float, siempre_visible: bool = False) -> str:
    """Para los resultados: un «+» delante deja claro de un vistazo que es
    ganancia y no simplemente una cantidad."""
    if _oculto and not siempre_visible:
        return TAPADO
    marca = "+" if float(valor or 0) > 0 else ""
    return marca + numero(valor) + " €"


def porcentaje(valor: float, decimales: int = 1) -> str:
    try:
        cantidad = float(valor)
    except (TypeError, ValueError):
        return "—"
    if cantidad != cantidad or cantidad in (float("inf"), float("-inf")):
        return "—"
    return numero(cantidad * 100, decimales) + " %"


def decimal(valor: float, decimales: int = 1) -> str:
    return numero(valor, decimales)


def texto_a_numero(texto: str) -> float | None:
    """Lee lo que escriba el usuario. Devuelve None si no hay forma.

    Acepta coma o punto porque en un teclado español la coma es lo natural, y
    se traga los espacios, los puntos de los miles y el símbolo del euro.
    """
    if texto is None:
        return None
    limpio = str(texto).strip().replace("€", "").replace(" ", "").replace(" ", "")
    if not limpio:
        return None

    # Si hay coma, manda ella como separador decimal y los puntos son miles.
    if "," in limpio:
        limpio = limpio.replace(".", "").replace(",", ".")
    elif limpio.count(".") > 1:
        limpio = limpio.replace(".", "")

    try:
        return float(limpio)
    except ValueError:
        return None


# --- fechas ----------------------------------------------------------------

def fecha_corta(iso: str) -> str:
    """'24 ago 2026'. Se trocea la cadena en vez de usar datetime para que no
    haya manera de que una zona horaria reste un día."""
    if not es_fecha(iso):
        return ""
    anio, mes, dia = iso.split("-")
    return f"{int(dia)} {MESES_CORTOS[int(mes) - 1]} {anio}"


def fecha_larga(iso: str) -> str:
    if not es_fecha(iso):
        return ""
    anio, mes, dia = iso.split("-")
    return f"{int(dia)} de {MESES[int(mes) - 1]} de {anio}"


def fecha_a_texto(iso: str) -> str:
    """Para las casillas donde se escribe una fecha: dd/mm/aaaa."""
    if not es_fecha(iso):
        return ""
    anio, mes, dia = iso.split("-")
    return f"{dia}/{mes}/{anio}"


def texto_a_fecha(texto: str) -> str | None:
    """Lo contrario: admite 24/8/26, 24-08-2026 y 2026-08-24."""
    limpio = str(texto or "").strip()
    if not limpio:
        return None
    if es_fecha(limpio):
        return limpio

    for separador in ("/", "-", "."):
        if separador in limpio:
            partes = limpio.split(separador)
            break
    else:
        return None

    if len(partes) != 3 or not all(p.strip().isdigit() for p in partes):
        return None

    primero, segundo, tercero = (int(p) for p in partes)
    # 2026-08-24 viene con el año delante; 24/08/2026, detrás.
    if primero > 31:
        anio, mes, dia = primero, segundo, tercero
    else:
        dia, mes, anio = primero, segundo, tercero
    if anio < 100:
        anio += 2000

    from datetime import date
    try:
        return date(anio, mes, dia).isoformat()
    except ValueError:
        return None
