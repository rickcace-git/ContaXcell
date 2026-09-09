"""Genera `icono.ico` sin depender de ninguna librería de imágenes.

Se dibuja a mano con matemáticas de píxeles y se guarda como PNG dentro de un
.ico, que es un formato que Windows admite desde Vista. Así el icono se puede
regenerar en cualquier ordenador con solo Python, sin instalar Pillow ni
arrastrar un binario que nadie sabe de dónde salió.

    python recursos/hacer_icono.py
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

# Los mismos colores que la aplicación: el azul de la marca y los tres con los
# que se pinta cada tipo de movimiento.
AZUL_CLARO = (74, 134, 255)
AZUL = (47, 111, 235)
BLANCO = (255, 255, 255)
ROJO = (240, 115, 111)    # gasto
MORADO = (180, 146, 232)  # inversión
VERDE = (76, 201, 138)    # ingreso

TAMANOS = (16, 24, 32, 48, 64, 128, 256)
# Se dibuja una sola vez en grande y se reduce por promedio: es la forma más
# barata de conseguir bordes suaves sin librerías. 768 no es un número
# cualquiera: es múltiplo de todos los tamaños de arriba, y así ninguno se
# reduce dejándose fuera la última tira de píxeles del dibujo.
LADO_MAESTRO = 768


def _mezcla(fondo, frente, alfa: float):
    return tuple(round(f + (d - f) * alfa) for f, d in zip(fondo, frente))


def _dentro_de_caja(x: float, y: float, x1: float, y1: float,
                    x2: float, y2: float, radio: float) -> bool:
    """Si el punto cae dentro de un rectángulo de esquinas redondeadas.

    Es la única forma que hace falta: el fondo, la hoja y cada barra son la
    misma caja con otro radio. Se mide la distancia al rectángulo encogido
    por el radio, que es la manera corta de redondear las cuatro esquinas sin
    tratar cada una por separado.
    """
    centro_x, centro_y = (x1 + x2) / 2, (y1 + y2) / 2
    dx = abs(x - centro_x) - (x2 - x1) / 2 + radio
    dy = abs(y - centro_y) - (y2 - y1) / 2 + radio
    fuera = math.hypot(max(dx, 0.0), max(dy, 0.0))
    return fuera + min(max(dx, dy), 0.0) <= radio


# Todo se mide en fracciones del lado, para que el dibujo salga igual en el
# icono de 16 píxeles y en el de 256.
HOJA = (0.16, 0.16, 0.84, 0.84)
RADIO_HOJA = 0.12
SUELO = 0.72
# Cada barra: desde, hasta y techo. De más baja a más alta, que así se lee de
# un vistazo lo que se busca: ingresar más de lo que se gasta.
BARRAS = (
    (0.26, 0.38, 0.55, ROJO),
    (0.44, 0.56, 0.42, MORADO),
    (0.62, 0.74, 0.28, VERDE),
)


def dibujar(lado: int) -> list[list[tuple[int, int, int, int]]]:
    """La hoja de cálculo, y dentro las tres cosas que se apuntan en ella.

    El icono cuenta de qué va el programa: sustituye a la hoja de toda la
    vida, y lo que lleva dentro son gastos, inversión e ingresos, cada uno
    con el color con el que la aplicación los pinta. Unas barras a secas
    valdrían para cualquier cosa con gráficos.
    """
    radio = lado * 0.23
    hoja = tuple(valor * lado for valor in HOJA)
    filas = []

    for fila_y in range(lado):
        fila = []
        y = fila_y + 0.5
        for columna_x in range(lado):
            x = columna_x + 0.5
            if not _dentro_de_caja(x, y, 0, 0, lado, lado, radio):
                fila.append((0, 0, 0, 0))
                continue

            # Degradado suave de arriba abajo en el fondo.
            color = _mezcla(AZUL_CLARO, AZUL, y / lado)
            if _dentro_de_caja(x, y, *hoja, RADIO_HOJA * lado):
                color = BLANCO
                for x1, x2, techo, color_barra in BARRAS:
                    # El radio es medio ancho: la barra acaba en semicírculo.
                    if _dentro_de_caja(x, y, x1 * lado, techo * lado, x2 * lado,
                                       SUELO * lado, (x2 - x1) * lado / 2):
                        color = color_barra
                        break
            fila.append((*color, 255))
        filas.append(fila)
    return filas


def reducir(maestro, lado_origen: int, lado_destino: int):
    """Promedia bloques cuadrados. Con esto salen los bordes suavizados."""
    factor = lado_origen // lado_destino
    salida = []
    for fila_y in range(lado_destino):
        fila = []
        for columna_x in range(lado_destino):
            suma = [0, 0, 0, 0]
            for dy in range(factor):
                origen = maestro[fila_y * factor + dy]
                for dx in range(factor):
                    pixel = origen[columna_x * factor + dx]
                    # Se premultiplica por el alfa para que los bordes no se
                    # oscurezcan al promediar con los píxeles transparentes.
                    alfa = pixel[3] / 255
                    suma[0] += pixel[0] * alfa
                    suma[1] += pixel[1] * alfa
                    suma[2] += pixel[2] * alfa
                    suma[3] += pixel[3]
            total = factor * factor
            alfa_medio = suma[3] / total
            if alfa_medio < 1:
                fila.append((0, 0, 0, 0))
                continue
            peso = suma[3] / 255
            fila.append((round(suma[0] / peso), round(suma[1] / peso),
                         round(suma[2] / peso), round(alfa_medio)))
        salida.append(fila)
    return salida


def a_png(filas) -> bytes:
    alto = len(filas)
    ancho = len(filas[0])
    crudo = bytearray()
    for fila in filas:
        crudo.append(0)  # sin filtro
        for pixel in fila:
            crudo.extend(pixel)

    def trozo(etiqueta: bytes, datos: bytes) -> bytes:
        return (struct.pack(">I", len(datos)) + etiqueta + datos
                + struct.pack(">I", zlib.crc32(etiqueta + datos) & 0xFFFFFFFF))

    cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n"
            + trozo(b"IHDR", cabecera)
            + trozo(b"IDAT", zlib.compress(bytes(crudo), 9))
            + trozo(b"IEND", b""))


def a_ico(imagenes: list[tuple[int, bytes]]) -> bytes:
    cabecera = struct.pack("<HHH", 0, 1, len(imagenes))
    entradas = bytearray()
    cuerpo = bytearray()
    desplazamiento = len(cabecera) + 16 * len(imagenes)

    for lado, png in imagenes:
        # En el formato .ico, 256 se escribe como 0.
        entradas.extend(struct.pack("<BBBBHHII", lado % 256, lado % 256, 0, 0, 1, 32,
                                    len(png), desplazamiento))
        cuerpo.extend(png)
        desplazamiento += len(png)

    return bytes(cabecera + entradas + cuerpo)


def main() -> None:
    print(f"dibujando a {LADO_MAESTRO}×{LADO_MAESTRO}…")
    maestro = dibujar(LADO_MAESTRO)

    imagenes = []
    for lado in TAMANOS:
        filas = maestro if lado == LADO_MAESTRO else reducir(maestro, LADO_MAESTRO, lado)
        imagenes.append((lado, a_png(filas)))
        print(f"  {lado}×{lado}")

    destino = Path(__file__).resolve().parent / "icono.ico"
    destino.write_bytes(a_ico(imagenes))
    print(f"escrito {destino} ({destino.stat().st_size / 1024:.1f} kB)")


if __name__ == "__main__":
    main()
