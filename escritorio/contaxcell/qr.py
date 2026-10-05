"""Códigos QR, hechos aquí mismo y sin librerías.

Sirven para una cosa: que el móvil escanee la dirección de descarga de la app
desde Ajustes o desde la guía. Por eso solo se hace lo que hace falta para
eso, y nada más:

- Modo «byte» (vale para cualquier texto; una dirección cabe de sobra).
- Corrección de errores M: aguanta que se pierda un 15 % del dibujo, que es
  lo que se pierde fotografiando una pantalla con reflejos.
- Versiones 1 a 10, o sea, hasta 213 caracteres. Una dirección no llega.

Cómo se hace un QR, en corto: el texto se pasa a bytes, se le añaden bytes
de corrección (Reed-Solomon, la misma idea que en los CD), todo eso se coloca
en zigzag sobre una cuadrícula que ya tiene los tres cuadros de las esquinas
y las demás marcas fijas, y se le aplica la «máscara» que deja el dibujo más
fácil de leer (sin grandes manchas ni rayas que confundan a la cámara).

Este módulo no toca la ventana ni el disco: `matriz()` devuelve la
cuadrícula y `png()` la imagen, que la ventana convierte en PhotoImage.
"""

from __future__ import annotations

import struct
import zlib

# Para la corrección M, por versión (índice = versión): cuántos bytes de
# corrección lleva cada bloque y en cuántos bloques se parte el mensaje. Son
# las tablas de la norma (ISO/IEC 18004); el índice 0 no se usa.
_CORRECCION_POR_BLOQUE = (None, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26)
_BLOQUES = (None, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5)
VERSION_MAXIMA = 10

# El nivel M se escribe como 0 en la información de formato.
_BITS_NIVEL_M = 0


class DemasiadoLargo(ValueError):
    """El texto no cabe en un QR de versión 10 con corrección M."""


# --- aritmética del cuerpo de Galois GF(256), la de Reed-Solomon -------------------

def _multiplica(x: int, y: int) -> int:
    """x · y en GF(2⁸) con el polinomio 0x11D, el que usa el QR."""
    resultado = 0
    for i in range(7, -1, -1):
        resultado = (resultado << 1) ^ ((resultado >> 7) * 0x11D)
        resultado ^= ((y >> i) & 1) * x
    return resultado


def _divisor(grado: int) -> list[int]:
    """El polinomio generador de Reed-Solomon de ese grado."""
    resultado = [0] * (grado - 1) + [1]
    raiz = 1
    for _ in range(grado):
        for j in range(grado):
            resultado[j] = _multiplica(resultado[j], raiz)
            if j + 1 < grado:
                resultado[j] ^= resultado[j + 1]
        raiz = _multiplica(raiz, 0x02)
    return resultado


def _correccion(datos: list[int], divisor: list[int]) -> list[int]:
    """Los bytes de corrección: el resto de dividir los datos por el divisor."""
    resto = [0] * len(divisor)
    for byte in datos:
        factor = byte ^ resto.pop(0)
        resto.append(0)
        for i, coef in enumerate(divisor):
            resto[i] ^= _multiplica(coef, factor)
    return resto


# --- tamaños de cada versión ----------------------------------------------------------

def _lado(version: int) -> int:
    return version * 4 + 17


def _modulos_de_datos(version: int) -> int:
    """Cuántos cuadritos quedan para datos y corrección, quitadas las marcas fijas."""
    resultado = (16 * version + 128) * version + 64
    if version >= 2:
        alineaciones = version // 7 + 2
        resultado -= (25 * alineaciones - 10) * alineaciones - 55
        if version >= 7:
            resultado -= 36
    return resultado


def _bytes_de_datos(version: int) -> int:
    return (_modulos_de_datos(version) // 8
            - _CORRECCION_POR_BLOQUE[version] * _BLOQUES[version])


def _posiciones_alineacion(version: int) -> list[int]:
    if version == 1:
        return []
    cuantas = version // 7 + 2
    paso = (version * 8 + cuantas * 3 + 5) // (cuantas * 4 - 4) * 2
    ultima = _lado(version) - 7
    return [6] + [ultima - i * paso for i in range(cuantas - 2, -1, -1)]


# --- el mensaje en bytes ----------------------------------------------------------------

def _version_para(datos: bytes) -> int:
    for version in range(1, VERSION_MAXIMA + 1):
        bits_cuenta = 8 if version < 10 else 16
        if 4 + bits_cuenta + 8 * len(datos) <= _bytes_de_datos(version) * 8:
            return version
    raise DemasiadoLargo(f"{len(datos)} bytes no caben en un QR de versión {VERSION_MAXIMA}")


def _palabras(datos: bytes, version: int) -> list[int]:
    """Modo, longitud, los datos, el cierre y el relleno; luego la corrección
    de cada bloque, y todo intercalado como manda la norma."""
    bits: list[int] = []

    def pon(valor: int, cuantos: int) -> None:
        bits.extend((valor >> i) & 1 for i in range(cuantos - 1, -1, -1))

    pon(0b0100, 4)  # modo byte
    pon(len(datos), 8 if version < 10 else 16)
    for byte in datos:
        pon(byte, 8)
    capacidad = _bytes_de_datos(version) * 8
    pon(0, min(4, capacidad - len(bits)))
    pon(0, -len(bits) % 8)
    relleno = (0xEC, 0x11)
    i = 0
    while len(bits) < capacidad:
        pon(relleno[i % 2], 8)
        i += 1
    palabras = [int("".join(map(str, bits[j:j + 8])), 2) for j in range(0, len(bits), 8)]

    # En bloques: los primeros, cortos; los últimos, un byte más largos.
    bloques_total = _BLOQUES[version]
    largo_correccion = _CORRECCION_POR_BLOQUE[version]
    brutos = _modulos_de_datos(version) // 8
    cortos = bloques_total - brutos % bloques_total
    largo_corto = brutos // bloques_total
    divisor = _divisor(largo_correccion)
    bloques = []
    k = 0
    for b in range(bloques_total):
        trozo = palabras[k:k + largo_corto - largo_correccion + (0 if b < cortos else 1)]
        k += len(trozo)
        correccion = _correccion(trozo, divisor)
        if b < cortos:
            trozo = trozo + [0]  # hueco para igualar, que no se escribe
        bloques.append(trozo + correccion)

    resultado = []
    for i in range(len(bloques[0])):
        for b, bloque in enumerate(bloques):
            if i != largo_corto - largo_correccion or b >= cortos:
                resultado.append(bloque[i])
    return resultado


# --- el dibujo ----------------------------------------------------------------------------

_MASCARAS = (
    lambda x, y: (x + y) % 2 == 0,
    lambda x, y: y % 2 == 0,
    lambda x, y: x % 3 == 0,
    lambda x, y: (x + y) % 3 == 0,
    lambda x, y: (x // 3 + y // 2) % 2 == 0,
    lambda x, y: x * y % 2 + x * y % 3 == 0,
    lambda x, y: (x * y % 2 + x * y % 3) % 2 == 0,
    lambda x, y: ((x + y) % 2 + x * y % 3) % 2 == 0,
)


class _Lienzo:
    def __init__(self, version: int):
        self.version = version
        self.lado = _lado(version)
        self.negro = [[False] * self.lado for _ in range(self.lado)]
        self.fijo = [[False] * self.lado for _ in range(self.lado)]

    def fija(self, x: int, y: int, negro: bool) -> None:
        self.negro[y][x] = negro
        self.fijo[y][x] = True

    def marcas_fijas(self) -> None:
        lado = self.lado
        for i in range(lado):  # las líneas de puntos que marcan el ritmo
            self.fija(6, i, i % 2 == 0)
            self.fija(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (lado - 4, 3), (3, lado - 4)):  # los tres cuadros
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < lado and 0 <= y < lado:
                        self.fija(x, y, max(abs(dx), abs(dy)) not in (2, 4))
        posiciones = _posiciones_alineacion(self.version)
        ultima = len(posiciones) - 1
        for i, cx in enumerate(posiciones):
            for j, cy in enumerate(posiciones):
                if (i, j) in ((0, 0), (0, ultima), (ultima, 0)):
                    continue  # ahí ya están los cuadros grandes
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.fija(cx + dx, cy + dy, max(abs(dx), abs(dy)) != 1)
        self.formato(0)  # reserva su sitio; el bueno se pone al final
        if self.version >= 7:
            resto = self.version
            for _ in range(12):
                resto = (resto << 1) ^ ((resto >> 11) * 0x1F25)
            bits = self.version << 12 | resto
            for i in range(18):
                negro = (bits >> i) & 1 == 1
                a, b = lado - 11 + i % 3, i // 3
                self.fija(a, b, negro)
                self.fija(b, a, negro)

    def formato(self, mascara: int) -> None:
        datos = _BITS_NIVEL_M << 3 | mascara
        resto = datos
        for _ in range(10):
            resto = (resto << 1) ^ ((resto >> 9) * 0x537)
        bits = (datos << 10 | resto) ^ 0x5412

        def bit(i: int) -> bool:
            return (bits >> i) & 1 == 1

        lado = self.lado
        for i in range(6):
            self.fija(8, i, bit(i))
        self.fija(8, 7, bit(6))
        self.fija(8, 8, bit(7))
        self.fija(7, 8, bit(8))
        for i in range(9, 15):
            self.fija(14 - i, 8, bit(i))
        for i in range(8):
            self.fija(lado - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.fija(8, lado - 15 + i, bit(i))
        self.fija(8, lado - 8, True)  # el cuadrito que siempre va negro

    def datos(self, palabras: list[int]) -> None:
        """En zigzag de dos columnas, de abajo arriba y de arriba abajo,
        saltándose las marcas fijas y la columna del ritmo."""
        lado = self.lado
        total = len(palabras) * 8
        i = 0
        derecha = lado - 1
        while derecha >= 1:
            if derecha == 6:
                derecha = 5
            for paso in range(lado):
                for j in range(2):
                    x = derecha - j
                    subiendo = ((derecha + 1) & 2) == 0
                    y = lado - 1 - paso if subiendo else paso
                    if not self.fijo[y][x] and i < total:
                        self.negro[y][x] = (palabras[i >> 3] >> (7 - (i & 7))) & 1 == 1
                        i += 1
            derecha -= 2

    def enmascara(self, mascara: int) -> None:
        cumple = _MASCARAS[mascara]
        for y in range(self.lado):
            for x in range(self.lado):
                if not self.fijo[y][x] and cumple(x, y):
                    self.negro[y][x] = not self.negro[y][x]

    def castigo(self) -> int:
        """Lo difícil que se lo pone el dibujo a una cámara. La máscara que
        lo deja más bajo es la buena. Las cuatro reglas de la norma."""
        lado = self.lado
        filas = self.negro
        columnas = [[filas[y][x] for y in range(lado)] for x in range(lado)]
        puntos = 0
        parecido_a_cuadro = ((1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0),
                             (0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1))
        for linea in (*filas, *columnas):
            racha = 1
            for i in range(1, lado + 1):  # 1: rachas de cinco o más iguales
                if i < lado and linea[i] == linea[i - 1]:
                    racha += 1
                    continue
                if racha >= 5:
                    puntos += racha - 2
                racha = 1
            # 3: trozos que se confunden con los cuadros de las esquinas,
            # contando el margen blanco de fuera como blanco.
            con_margen = [0] * 4 + [int(v) for v in linea] + [0] * 4
            for i in range(len(con_margen) - 10):
                if tuple(con_margen[i:i + 11]) in parecido_a_cuadro:
                    puntos += 40
        for y in range(lado - 1):  # 2: cuadrados de 2×2 del mismo color
            for x in range(lado - 1):
                if filas[y][x] == filas[y][x + 1] == filas[y + 1][x] == filas[y + 1][x + 1]:
                    puntos += 3
        # 4: diez puntos por cada 5 % que se aparte de mitad negro, mitad blanco.
        # (El lado es impar, así que nunca sale justo la mitad.)
        negros = sum(map(sum, filas))
        total = lado * lado
        puntos += ((abs(negros * 20 - total * 10) + total - 1) // total - 1) * 10
        return puntos


def matriz(texto: str) -> list[list[bool]]:
    """La cuadrícula del QR: True es negro. Sin el margen blanco de fuera."""
    datos = texto.encode("utf-8")
    version = _version_para(datos)
    palabras = _palabras(datos, version)
    mejor, mejor_castigo = None, None
    for mascara in range(len(_MASCARAS)):
        lienzo = _Lienzo(version)
        lienzo.marcas_fijas()
        lienzo.datos(palabras)
        lienzo.enmascara(mascara)
        lienzo.formato(mascara)
        castigo = lienzo.castigo()
        if mejor_castigo is None or castigo < mejor_castigo:
            mejor, mejor_castigo = lienzo, castigo
    return mejor.negro


def png(texto: str, tamano_modulo: int = 6, margen: int = 4) -> bytes:
    """El QR en PNG, negro sobre blanco siempre (también con el tema oscuro:
    las cámaras leen mal un QR claro sobre oscuro) y con su margen blanco
    alrededor, que sin él muchos lectores no lo encuentran."""
    cuadricula = matriz(texto)
    lado = len(cuadricula) + 2 * margen
    filas = []
    for y in range(lado):
        fila = bytearray([0])  # sin filtro
        for x in range(lado):
            dentro = margen <= x < lado - margen and margen <= y < lado - margen
            negro = dentro and cuadricula[y - margen][x - margen]
            fila.extend([0 if negro else 255] * tamano_modulo)
        filas.extend([bytes(fila)] * tamano_modulo)
    ancho = lado * tamano_modulo

    def trozo(etiqueta: bytes, datos: bytes) -> bytes:
        return (struct.pack(">I", len(datos)) + etiqueta + datos
                + struct.pack(">I", zlib.crc32(etiqueta + datos) & 0xFFFFFFFF))

    # Escala de grises de 8 bits: con un canal sobra para blanco y negro.
    cabecera = struct.pack(">IIBBBBB", ancho, ancho, 8, 0, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", cabecera)
            + trozo(b"IDAT", zlib.compress(b"".join(filas))) + trozo(b"IEND", b""))
