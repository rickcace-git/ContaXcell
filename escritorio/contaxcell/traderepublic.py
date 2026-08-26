"""Leer el extracto en PDF de Trade Republic.

El «Certificado de saldo y movimientos» que descarga la aplicación del banco
trae, entre otras cosas, las compras del plan de inversión. De cada una
interesa lo que no está en ningún otro sitio: **cuántas participaciones**
compró. Sin ese dato solo se sabe cuánto dinero se metió, y no se puede saber
cómo ha ido cada compra por separado.

Cómo se lee, que tiene más miga de la que parece:

1. El PDF guarda su contenido comprimido con zlib. Se descomprime a mano.
2. La letra va incrustada con una codificación propia del archivo, así que
   los bytes del texto no son letras: hay que pasarlos por la tabla
   `ToUnicode` que el propio PDF lleva dentro. Sin eso sale un galimatías.
3. Cada trozo de texto viene con su posición en la página, y las filas de la
   tabla se reconstruyen agrupando por altura.

No usa ninguna librería de fuera: solo `re` y `zlib`, que vienen con Python.
Meter una librería de PDF habría engordado el ejecutable y dado otra excusa
al antivirus.

Este módulo no toca disco más que para leer el archivo que se le dice, ni
sabe nada de la ventana. Se prueba entero con un PDF de ejemplo.
"""

from __future__ import annotations

import re
import zlib
from dataclasses import dataclass, field

from .modelo import redondea, redondea_titulos

# --- lo que sacamos del extracto -------------------------------------------

COMPRA = "compra"
INGRESO_SUELTO = "ingreso"
# Una bonificación que se reinvirtió: entra en la cartera sin salir de tu
# bolsillo. No es ingreso ni aportación desde el banco, es la tercera forma.
GRATIS = "gratis"

# Cuántos días puede tardar el banco en reinvertir una bonificación. La suya
# cae a primeros de mes y la compra se hace con el siguiente plan de ahorro.
DIAS_PARA_REINVERTIR = 10


@dataclass
class Apunte:
    """Una línea del extracto que nos interesa."""

    clase: str          # COMPRA o INGRESO_SUELTO
    fecha: str          # 'AAAA-MM-DD'
    concepto: str
    importe: float
    # Solo las compras:
    isin: str = ""
    nombre_activo: str = ""
    titulos: float = 0.0

    @property
    def precio(self) -> float:
        return self.importe / self.titulos if self.titulos > 0 else 0.0


@dataclass
class Lectura:
    """El resultado de leer un extracto."""

    apuntes: list[Apunte] = field(default_factory=list)
    desde: str = ""
    hasta: str = ""
    avisos: list[str] = field(default_factory=list)

    @property
    def compras(self) -> list[Apunte]:
        return [a for a in self.apuntes if a.clase == COMPRA]

    @property
    def ingresos(self) -> list[Apunte]:
        return [a for a in self.apuntes if a.clase == INGRESO_SUELTO]

    @property
    def gratis(self) -> list[Apunte]:
        """Bonificaciones que se reinvirtieron: dinero que entró en la cartera
        sin salir de tu bolsillo."""
        return [a for a in self.apuntes if a.clase == GRATIS]


class NoEsUnExtracto(Exception):
    """El archivo no parece un extracto de Trade Republic."""


# --- el PDF por dentro -----------------------------------------------------

_FLUJO = re.compile(rb"stream\r?\n(.*?)endstream", re.S)
_RANGO = re.compile(r"<([0-9A-Fa-f]+)><([0-9A-Fa-f]+)><([0-9A-Fa-f]+)>")
_TROZO = re.compile(rb"1 0 0 1 ([\d.]+) ([\d.]+) Tm|\((?:[^()\\]|\\.)*\)")
_ESCAPE = re.compile(rb"\\([()\\])")


def _flujos(datos: bytes) -> list[bytes]:
    sueltos = []
    for comprimido in _FLUJO.findall(datos):
        try:
            sueltos.append(zlib.decompress(comprimido))
        except zlib.error:
            pass  # imágenes y letras: no son texto, no estorban
    return sueltos


def _tabla_de_letras(flujos: list[bytes]) -> dict[int, str]:
    """La tabla que traduce los códigos del archivo a letras de verdad."""
    tabla: dict[int, str] = {}
    for flujo in flujos:
        if b"beginbfrange" not in flujo:
            continue
        for desde, hasta, destino in _RANGO.findall(flujo.decode("latin-1")):
            principio, final, meta = int(desde, 16), int(hasta, 16), int(destino, 16)
            # Los rangos largos vienen como principio-final; los sueltos, con
            # los dos iguales. Se tratan igual.
            for salto in range(min(final - principio + 1, 512)):
                tabla[principio + salto] = chr(meta + salto)
    return tabla


def _descifra(bruto: bytes, tabla: dict[int, str]) -> str:
    cuerpo = _ESCAPE.sub(rb"\1", bruto[1:-1])
    if len(cuerpo) % 2:
        cuerpo += b"\x00"
    return "".join(tabla.get(cuerpo[i] * 256 + cuerpo[i + 1], "")
                   for i in range(0, len(cuerpo), 2))


def lineas_del_pdf(datos: bytes) -> list[str]:
    """El texto del PDF, una cadena por fila de la página.

    Los trozos se agrupan por la altura a la que están y se ordenan de
    izquierda a derecha, que es como se reconstruye una tabla.
    """
    flujos = _flujos(datos)
    tabla = _tabla_de_letras(flujos)
    if not tabla:
        raise NoEsUnExtracto("el PDF no trae la tabla de letras que hace falta")

    lineas = []
    for pagina in (f for f in flujos if b"BT" in f and b"Tf" in f):
        trozos = []
        altura = 0.0
        izquierda = 0.0
        for encontrado in _TROZO.finditer(pagina):
            marca = encontrado.group(0)
            if marca.startswith(b"1 0 0 1"):
                izquierda = float(encontrado.group(1))
                altura = float(encontrado.group(2))
            else:
                texto = _descifra(marca, tabla)
                if texto.strip():
                    trozos.append((round(altura, 1), izquierda, texto.strip()))

        for nivel in sorted({t[0] for t in trozos}, reverse=True):
            fila = sorted((t for t in trozos if t[0] == nivel), key=lambda t: t[1])
            lineas.append("  |  ".join(t[2] for t in fila))
    return lineas


# --- del texto a los apuntes -----------------------------------------------

MESES_CORTOS_EXTRACTO = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

_DIA = re.compile(r"\b(\d{1,2}) (" + "|".join(MESES_CORTOS_EXTRACTO) + r")\b")
_ANIO = re.compile(r"^\s*(\d{4})\b")
_ISIN = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}\d)\b")
_EUROS = re.compile(r"([\d.]+,\d{2})")
_TITULOS = re.compile(r"quantity:\s*([\d.]+)")

# Lo que Trade Republic escribe en cada tipo de línea.
_MARCA_COMPRA = "Savings plan execution"
CONCEPTO_INTERESES = "Intereses de Trade Republic"
CONCEPTO_BONIFICACION = "Bonificación de Trade Republic"

# Los intereses son dinero que te dan de verdad y se quedan en la cuenta: son
# un ingreso. La bonificación normalmente se reinvierte, y entonces deja de
# ser ingreso para ser aportación gratis a la cartera.
_MARCAS_INGRESO = {
    "Interest payment": CONCEPTO_INTERESES,
    "Cash reward allocation": CONCEPTO_BONIFICACION,
}


def _a_euros(texto: str) -> float:
    return redondea(float(texto.replace(".", "").replace(",", ".")))


def _fecha(dia_mes: re.Match, anio: str) -> str:
    dia = int(dia_mes.group(1))
    mes = MESES_CORTOS_EXTRACTO[dia_mes.group(2)]
    return f"{anio}-{mes:02d}-{dia:02d}"


def _sin_columna(fila: str) -> str:
    """Quita la primera columna, que es la de la fecha, y deja la descripción."""
    return fila.split("|", 1)[-1].strip() if "|" in fila else fila.strip()


def _nombre_corto(descripcion: str) -> str:
    """Un nombre que quepa en la tabla.

    El banco escribe «iShares III plc - iShares Core MSCI World UCITS ETF USD
    (Acc)». Lo que identifica al fondo es el índice que sigue, así que se
    busca ese y lo demás sobra.
    """
    conocidos = ("MSCI World", "MSCI Emerging Markets", "S&P 500", "Nasdaq",
                 "FTSE All-World", "Euro Stoxx 50", "STOXX Europe 600",
                 "MSCI ACWI", "MSCI Europe", "MSCI USA")
    for indice in conocidos:
        if indice.lower() in descripcion.lower():
            return indice

    # Si no es ninguno conocido, se corta por el guion y se quitan las siglas
    # del envoltorio, que no distinguen un fondo de otro.
    limpio = descripcion.split("quantity")[0]
    limpio = re.sub(r"\b[A-Z]{2}[A-Z0-9]{9}\d\b", " ", limpio)
    limpio = limpio.replace(_MARCA_COMPRA, " ").split(" - ")[-1]
    limpio = re.sub(r"\b(UCITS|ETF|USD|EUR|Acc|Dist|plc|III|II)\b", " ", limpio)
    limpio = re.sub(r"[(),]", " ", limpio)
    return " ".join(limpio.split())[:40] or "Fondo"


def leer(ruta: str) -> Lectura:
    """Lee el extracto y devuelve lo que se puede apuntar."""
    with open(ruta, "rb") as archivo:
        datos = archivo.read()
    return leer_lineas(lineas_del_pdf(datos))


def leer_lineas(lineas: list[str]) -> Lectura:
    """La parte que entiende el texto, separada para poder probarla."""
    lectura = Lectura()

    def fila(indice: int) -> str:
        return lineas[indice] if 0 <= indice < len(lineas) else ""

    for numero, linea in enumerate(lineas):
        if _MARCA_COMPRA in linea:
            apunte = _compra(linea, fila(numero + 1), fila(numero + 2))
            if apunte is not None:
                lectura.apuntes.append(apunte)
            else:
                lectura.avisos.append(f"No he entendido una compra: {linea[:60]}…")
            continue

        for marca, concepto in _MARCAS_INGRESO.items():
            if marca in linea:
                # El día va en la fila de encima y el año en la de debajo:
                # el banco parte la fecha en dos para que quepa la columna.
                apunte = _ingreso(linea, fila(numero - 1), fila(numero + 1), concepto)
                if apunte is not None:
                    lectura.apuntes.append(apunte)
                else:
                    lectura.avisos.append(f"No he entendido un ingreso: {linea[:60]}…")
                break

    _emparejar_bonificaciones(lectura)

    fechas = sorted(a.fecha for a in lectura.apuntes)
    if fechas:
        lectura.desde, lectura.hasta = fechas[0], fechas[-1]
    return lectura


def _emparejar_bonificaciones(lectura: Lectura) -> None:
    """Junta cada bonificación con la compra en la que se reinvirtió.

    El banco te regala 4,61 €, entran en la cuenta y a los pocos días se
    invierten. Son un solo hecho contado en dos líneas: si se apuntara el
    ingreso y además la compra como dinero salido del banco, ese regalo se
    contaría dos veces y encima parecería que lo pusiste tú.

    Se reconocen porque la compra tiene el mismo importe exacto que la
    bonificación y viene justo después. La bonificación que no encuentre su
    compra se queda como ingreso: te la dieron y no la reinvertiste.
    """
    pendientes = [a for a in lectura.apuntes
                  if a.clase == INGRESO_SUELTO and a.concepto == CONCEPTO_BONIFICACION]
    if not pendientes:
        return

    emparejadas = []
    for bonificacion in pendientes:
        tope = _suma_dias(bonificacion.fecha, DIAS_PARA_REINVERTIR)
        for compra in lectura.apuntes:
            if (compra.clase == COMPRA
                    and abs(compra.importe - bonificacion.importe) < 0.005
                    and bonificacion.fecha <= compra.fecha <= tope):
                compra.clase = GRATIS
                compra.concepto = bonificacion.concepto
                emparejadas.append(bonificacion)
                break

    for bonificacion in emparejadas:
        lectura.apuntes.remove(bonificacion)


def _suma_dias(fecha: str, dias: int) -> str:
    from .modelo import suma_dias
    return suma_dias(fecha, dias) or fecha


def _compra(linea: str, siguiente: str, tercera: str) -> Apunte | None:
    """Una compra ocupa tres filas: la fecha y el principio de la descripción,
    el importe, y el año con el final de la descripción y las participaciones."""
    dia = _DIA.search(linea)
    anio = _ANIO.search(tercera)
    importe = _EUROS.search(siguiente)
    titulos = _TITULOS.search(tercera)
    if not (dia and anio and importe and titulos):
        return None

    cuantos = redondea_titulos(titulos.group(1))
    if cuantos <= 0:
        return None

    # La descripción viene partida entre las dos filas y con la columna de la
    # fecha por delante. Se quita esa columna y se pegan los dos trozos, que
    # es donde queda el nombre del fondo entero.
    descripcion = f"{_sin_columna(linea)} {_sin_columna(tercera)}"
    isin = _ISIN.search(linea)
    return Apunte(
        clase=COMPRA,
        fecha=_fecha(dia, anio.group(1)),
        concepto="Compra del plan de inversión",
        importe=_a_euros(importe.group(1)),
        isin=isin.group(1) if isin else "",
        nombre_activo=_nombre_corto(descripcion),
        titulos=cuantos,
    )


def _ingreso(linea: str, anterior: str, siguiente: str, concepto: str) -> Apunte | None:
    """Los intereses y las bonificaciones ocupan una fila, pero su fecha está
    partida: el día encima y el año debajo."""
    dia = _DIA.search(linea) or _DIA.search(anterior)
    anio = (re.search(r"\b(20\d{2})\b", siguiente)
            or re.search(r"\b(20\d{2})\b", linea)
            or re.search(r"\b(20\d{2})\b", anterior))
    importe = _EUROS.search(linea)
    if not (dia and anio and importe):
        return None
    return Apunte(
        clase=INGRESO_SUELTO,
        fecha=_fecha(dia, anio.group(1)),
        concepto=concepto,
        importe=_a_euros(importe.group(1)),
    )


# --- del extracto al libro -------------------------------------------------

@dataclass
class Resultado:
    """Lo que ha pasado al importar."""

    compras: int = 0
    ingresos: int = 0
    repetidos: int = 0
    activos_nuevos: list = field(default_factory=list)
    invertido: float = 0.0
    ingresado: float = 0.0
    # Aportaciones a mano que se han quitado por venir ya en el extracto.
    sustituidas: int = 0
    sustituido: float = 0.0
    # Bonificaciones reinvertidas: entran en la cartera sin salir del banco.
    gratis: int = 0
    regalado: float = 0.0
    # Bonificaciones que una importacion anterior habia apuntado como dinero
    # salido del banco y que ahora se colocan donde tocaba.
    corregidas: int = 0


def _ya_esta(libro, fecha: str, importe: float, titulos: float, concepto: str) -> bool:
    """Si ese apunte ya está en el libro.

    Importar dos veces el mismo extracto, o dos extractos que se solapan, no
    puede duplicar nada: es lo primero que haría cualquiera sin darse cuenta.
    Se compara por fecha e importe, y por participaciones cuando las hay, que
    es lo que distingue dos compras del mismo día.
    """
    for m in libro.movimientos:
        if m.fecha != fecha or abs(m.importe - importe) > 0.005:
            continue
        if titulos > 0:
            if abs(m.titulos - titulos) < 0.0000005:
                return True
        elif m.descripcion == concepto:
            return True
    return False


def _como_movimiento(libro, apunte):
    """La misma bonificación, pero apuntada como si fuera dinero del banco.

    Es lo que dejaron las importaciones de antes de saber distinguirla. Se
    reconoce por fecha, importe y participaciones, que es una coincidencia
    imposible de casualidad.
    """
    for m in libro.movimientos:
        if (m.fecha == apunte.fecha and abs(m.importe - apunte.importe) < 0.005
                and abs(m.titulos - apunte.titulos) < 0.0000005 and m.titulos > 0):
            return m
    return None


def _ya_esta_gratis(libro, apunte, nombre_activo: str) -> bool:
    """Si esa bonificación ya está apuntada en la cartera."""
    for g in libro.aportaciones_gratis:
        if (g.fecha == apunte.fecha and abs(g.importe - apunte.importe) < 0.005
                and g.activo == nombre_activo):
            return True
    return False


def aplicar(libro, lectura: Lectura, categoria_inversion: str,
            categoria_ingreso: str, categoria_activo: str = "",
            sustituir: list | None = None,
            categoria_bonificacion: str = "") -> Resultado:
    """Apunta en el libro lo que trae el extracto.

    Las compras se apuntan como aportaciones a su activo, con las
    participaciones que compraron. Los intereses y las bonificaciones, como
    ingresos: son dinero que entra de verdad.

    Los activos se reconocen por su código del banco, así que importar otro
    extracto del mismo fondo no crea uno nuevo aunque el nombre venga escrito
    de otra manera.
    """
    from .modelo import Activo, AportacionGratis, Movimiento

    resultado = Resultado()

    # Primero fuera las apuntadas a mano que el extracto vuelve a traer: si
    # se quedaran, el mismo dinero estaría contado dos veces.
    if sustituir:
        aparte = set(sustituir)
        quitadas = [m for m in libro.movimientos if m.id in aparte]
        libro.movimientos = [m for m in libro.movimientos if m.id not in aparte]
        resultado.sustituidas = len(quitadas)
        resultado.sustituido = redondea(sum(m.importe for m in quitadas))

    for apunte in lectura.compras + lectura.gratis:
        activo = libro.activo_por_isin(apunte.isin) or libro.activo(apunte.nombre_activo)
        if activo is None:
            activo = Activo(nombre=_nombre_libre(libro, apunte.nombre_activo),
                            isin=apunte.isin, categoria=categoria_activo)
            libro.activos.append(activo)
            resultado.activos_nuevos.append(activo.nombre)
        elif not activo.isin and apunte.isin:
            activo.isin = apunte.isin  # ya lo tenía a mano, ahora sabemos cuál es

        if apunte.clase == GRATIS:
            # No sale del banco: te lo regalaron y se reinvirtió. Por eso va
            # como aportación gratis y no como movimiento.
            #
            # La limpieza va primero y se hace SIEMPRE, esté ya apuntada la
            # aportación gratis o no. Quien reimportó con una versión que ya
            # separaba el cashback pero todavía no limpiaba, se quedó con el
            # regalo en los dos sitios: en el banco y en la cartera. Si aquí
            # se saliera por «ya está», ese caso no se arreglaría nunca.
            vieja = _como_movimiento(libro, apunte)
            if vieja is not None:
                libro.movimientos.remove(vieja)
                resultado.corregidas += 1

            if _ya_esta_gratis(libro, apunte, activo.nombre):
                resultado.repetidos += 1
                continue

            libro.aportaciones_gratis.append(AportacionGratis(
                fecha=apunte.fecha,
                activo=activo.nombre,
                concepto=apunte.concepto,
                importe=apunte.importe,
                titulos=apunte.titulos,
            ))
            resultado.gratis += 1
            resultado.regalado = redondea(resultado.regalado + apunte.importe)
            continue

        if _ya_esta(libro, apunte.fecha, apunte.importe, apunte.titulos, apunte.concepto):
            resultado.repetidos += 1
            continue

        libro.movimientos.append(Movimiento(
            fecha=apunte.fecha,
            descripcion=apunte.concepto,
            categoria=categoria_inversion,
            importe=apunte.importe,
            activo=activo.nombre,
            titulos=apunte.titulos,
        ))
        resultado.compras += 1
        resultado.invertido = redondea(resultado.invertido + apunte.importe)

    for apunte in lectura.ingresos:
        if _ya_esta(libro, apunte.fecha, apunte.importe, 0.0, apunte.concepto):
            resultado.repetidos += 1
            continue
        # Una bonificacion que no se reinvirtio tambien es dinero que entra,
        # pero no tiene por que ir en la misma categoria que los intereses.
        categoria = categoria_ingreso
        if apunte.concepto == CONCEPTO_BONIFICACION and categoria_bonificacion:
            categoria = categoria_bonificacion
        libro.movimientos.append(Movimiento(
            fecha=apunte.fecha,
            descripcion=apunte.concepto,
            categoria=categoria,
            importe=apunte.importe,
        ))
        resultado.ingresos += 1
        resultado.ingresado = redondea(resultado.ingresado + apunte.importe)

    return resultado


def _nombre_libre(libro, propuesto: str) -> str:
    """Un nombre que no choque con otro activo que ya exista."""
    nombre = propuesto or "Fondo"
    if libro.activo(nombre) is None:
        return nombre
    for numero in range(2, 50):
        candidato = f"{nombre} ({numero})"
        if libro.activo(candidato) is None:
            return candidato
    return nombre


# --- lo que ya tenías apuntado a mano --------------------------------------

def activos_del_extracto(libro, lectura: Lectura) -> list[str]:
    """Cómo se van a llamar en el libro los activos que trae el extracto."""
    nombres = []
    for apunte in lectura.compras:
        activo = libro.activo_por_isin(apunte.isin) or libro.activo(apunte.nombre_activo)
        nombre = activo.nombre if activo else apunte.nombre_activo
        if nombre not in nombres:
            nombres.append(nombre)
    return nombres


def _meses_que_cubre(lectura: Lectura) -> tuple[str, str]:
    """Del día 1 del primer mes con compras al 31 del último.

    Se mira por meses enteros y no por los días exactos de las compras
    porque una aportación apuntada a mano lleva la fecha en que te acordaste
    —el día 1, o el último del mes—, no la del día en que el banco compró.
    """
    fechas = sorted(a.fecha for a in lectura.compras)
    if not fechas:
        return "", ""
    return fechas[0][:7] + "-01", fechas[-1][:7] + "-31"


def aportaciones_a_mano(libro, lectura: Lectura) -> list:
    """Las aportaciones que apuntaste tú y que el extracto vuelve a traer.

    Es el problema gordo de importar: si apuntas «400 € a inversión» una vez
    al mes y luego importas seis meses, entran veinticuatro compras de 100 €
    que son ese mismo dinero. Quedándose las dos cosas, la cartera diría que
    metiste el doble.

    Se reconocen porque no traen participaciones: las importadas sí. Van por
    meses enteros y solo cuentan las del mismo activo o las que no dicen a
    cuál, para no tocar lo que aportas a otro sitio.
    """
    desde, hasta = _meses_que_cubre(lectura)
    if not desde:
        return []

    from .modelo import INVERSION
    nombres = set(activos_del_extracto(libro, lectura))
    return [m for m in libro.movimientos
            if libro.tipo_de(m.categoria) == INVERSION
            and not m.titulos
            and desde <= m.fecha <= hasta
            and (not m.activo or m.activo in nombres)]
