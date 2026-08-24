"""Genera `icono.ico` sin depender de ninguna librería de imágenes.

Se dibuja a mano con matemáticas de píxeles y se guarda como PNG dentro de un
.ico, que es un formato que Windows admite desde Vista. Así el icono se puede
regenerar en cualquier ordenador con solo Python, sin instalar Pillow ni
arrastrar un binario que nadie sabe de dónde salió.

    python recursos/hacer_icono.py
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

# Los mismos colores que la aplicación.
AZUL_CLARO = (74, 134, 255)
AZUL = (47, 111, 235)
BLANCO = (255, 255, 255)
VERDE = (76, 201, 138)

TAMANOS = (16, 24, 32, 48, 64, 128, 256)
# Se dibuja una sola vez en grande y se reduce por promedio: es la forma más
# barata de conseguir bordes suaves sin librerías.
LADO_MAESTRO = 512


def _mezcla(fondo, frente, alfa: float):
    return tuple(round(f + (d - f) * alfa) for f, d in zip(fondo, frente))


def _dentro_del_redondeado(x: float, y: float, lado: float, radio: float) -> bool:
    """Si el punto cae dentro de un cuadrado de esquinas redondeadas."""
    izquierda = radio
    derecha = lado - radio
    if izquierda <= x <= derecha or izquierda <= y <= derecha:
        return 0 <= x <= lado and 0 <= y <= lado
    centro_x = izquierda if x < izquierda else derecha
    centro_y = izquierda if y < izquierda else derecha
    return (x - centro_x) ** 2 + (y - centro_y) ** 2 <= radio ** 2


def dibujar(lado: int) -> list[list[tuple[int, int, int, int]]]:
    """Un cuadrado azul redondeado con tres barras ascendentes."""
    radio = lado * 0.23
    filas = []

    # Las tres barras: la última en verde, porque es la que sube.
    margen = lado * 0.22
    ancho_util = lado - margen * 2
    ancho_barra = ancho_util * 0.22
    hueco = (ancho_util - ancho_barra * 3) / 2
    alturas = (0.30, 0.52, 0.76)
    colores = (BLANCO, BLANCO, VERDE)
    suelo = lado - margen
    radio_barra = ancho_barra / 2

    barras = []
    for indice, (altura, color) in enumerate(zip(alturas, colores)):
        x1 = margen + indice * (ancho_barra + hueco)
        barras.append((x1, x1 + ancho_barra, suelo - ancho_util * altura, color))

    for fila_y in range(lado):
        fila = []
        y = fila_y + 0.5
        for columna_x in range(lado):
            x = columna_x + 0.5
            if not _dentro_del_redondeado(x, y, lado, radio):
                fila.append((0, 0, 0, 0))
                continue

            # Degradado suave de arriba abajo en el fondo.
            color = _mezcla(AZUL_CLARO, AZUL, y / lado)
            for x1, x2, techo, color_barra in barras:
                if x1 <= x <= x2 and y >= techo:
                    # La barra tiene la punta redondeada.
                    centro_x = (x1 + x2) / 2
                    centro_y = techo + radio_barra
                    if y >= centro_y or (x - centro_x) ** 2 + (y - centro_y) ** 2 <= radio_barra ** 2:
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
