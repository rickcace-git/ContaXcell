"""Los iconos de las pestañas y de la guía (y el ojo de la contraseña),
dibujados aquí mismo.

Igual que el icono de la aplicación (`recursos/hacer_icono.py`), sin Pillow ni
archivos de imagen: cada icono es una lista de trazos sobre una cuadrícula de
24 × 24, se rasteriza en Python con varias muestras por píxel para que los
bordes salgan suaves, y se entrega a tkinter como un PNG con transparencia.

Lo caro es calcular qué parte de cada píxel tapa el dibujo, y eso no depende
del color: se hace una vez por icono y tamaño, y pintarlo de otro color (al
cambiar de tema, o para la pestaña elegida) ya es gratis.
"""

from __future__ import annotations

import base64
import math
import struct
import tkinter as tk
import zlib
from functools import lru_cache

# Grosor del trazo, en unidades de la cuadrícula de 24.
TRAZO = 2.0

# Cada trazo: (forma, *medidas). Las formas son:
#   «linea»  x1 y1 x2 y2           un segmento con los extremos redondeados
#   «aro»    cx cy r                una circunferencia
#   «arco»   cx cy r desde hasta    un trozo de circunferencia (grados; como
#                                   la y crece hacia abajo, van en el sentido
#                                   de las agujas del reloj)
#   «punto»  cx cy r                un círculo relleno
#   «triangulo» x1 y1 x2 y2 x3 y3   relleno
#   «engranaje» cx cy r_hueco r_diente r_base dientes   relleno
DIBUJOS: dict[str, tuple[tuple, ...]] = {
    # Un lápiz sobre la línea donde escribe.
    "apuntar": (
        ("linea", 6.5, 15.5, 16, 6), ("linea", 8.5, 17.5, 18, 8),
        ("linea", 16, 6, 18, 8),
        ("linea", 6.5, 15.5, 5, 19), ("linea", 8.5, 17.5, 5, 19),
        ("linea", 12, 20, 20, 20),
    ),
    # Una lista.
    "movimientos": (
        ("punto", 5, 7, 1.4), ("punto", 5, 12, 1.4), ("punto", 5, 17, 1.4),
        ("linea", 9, 7, 20, 7), ("linea", 9, 12, 20, 12), ("linea", 9, 17, 20, 17),
    ),
    # Dos flechas dando la vuelta: lo que vuelve solo.
    "periodicos": (
        ("arco", 12, 12, 7.5, 200, 340), ("triangulo", 17.5, 4.5, 21.5, 10, 15, 10.5),
        ("arco", 12, 12, 7.5, 20, 160), ("triangulo", 6.5, 19.5, 2.5, 14, 9, 13.5),
    ),
    # Ida y vuelta: lo que te deben y lo que debes.
    "deudas": (
        ("linea", 4, 8, 19, 8), ("linea", 15, 4.5, 19, 8), ("linea", 15, 11.5, 19, 8),
        ("linea", 5, 16, 20, 16), ("linea", 9, 12.5, 5, 16), ("linea", 9, 19.5, 5, 16),
    ),
    # Barras, como en el icono de la aplicación.
    "resumen": (
        ("linea", 6, 20, 6, 14), ("linea", 12, 20, 12, 9), ("linea", 18, 20, 18, 4),
    ),
    # Un quesito: el reparto de lo que hay para gastar.
    "presupuesto": (
        ("aro", 12, 12, 8.5), ("linea", 12, 12, 12, 3.5), ("linea", 12, 12, 19.4, 16.2),
    ),
    # Una gráfica que sube.
    "inversiones": (
        ("linea", 3, 18, 9, 12), ("linea", 9, 12, 13, 16), ("linea", 13, 16, 20, 8),
        ("linea", 15, 8, 20, 8), ("linea", 20, 8, 20, 13),
    ),
    "ajustes": (
        ("engranaje", 12, 12, 3.8, 9.3, 7.0, 8),
    ),
    # Solo en la guía: «Para empezar» y «Tu cuenta y el móvil».
    "empezar": (
        ("aro", 12, 12, 9), ("triangulo", 10, 8, 10, 16, 16.5, 12),
    ),
    "cuenta": (
        ("aro", 12, 8.5, 3.8), ("arco", 12, 21.5, 7.5, 195, 345),
    ),
    # Solo en la ventana de entrada: enseñar u ocultar la contraseña. Los dos
    # párpados son trozos de un aro grande que se cruzan en los lagrimales.
    "ojo": (
        ("arco", 12, 21, 13.45, 222, 318), ("arco", 12, 3, 13.45, 42, 138),
        ("punto", 12, 12, 3),
    ),
    "ojo_tachado": (
        ("arco", 12, 21, 13.45, 222, 318), ("arco", 12, 3, 13.45, 42, 138),
        ("punto", 12, 12, 3), ("linea", 4, 4, 20, 20),
    ),
}

# Muestras por lado de cada píxel: 4 × 4 = 16 por píxel. Con menos, las
# diagonales del lápiz salen dentadas a 16 píxeles.
MUESTRAS = 4


def _distancia_a_linea(px, py, x1, y1, x2, y2) -> float:
    dx, dy = x2 - x1, y2 - y1
    largo = dx * dx + dy * dy
    t = 0.0 if largo == 0 else max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / largo))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _en_arco(px, py, cx, cy, r, desde, hasta) -> bool:
    if abs(math.hypot(px - cx, py - cy) - r) > TRAZO / 2:
        # Fuera del aro, salvo por las puntas redondeadas.
        for angulo in (desde, hasta):
            a = math.radians(angulo)
            if math.hypot(px - (cx + r * math.cos(a)), py - (cy + r * math.sin(a))) <= TRAZO / 2:
                return True
        return False
    angulo = math.degrees(math.atan2(py - cy, px - cx)) % 360
    return (angulo - desde) % 360 <= (hasta - desde) % 360


def _en_triangulo(px, py, x1, y1, x2, y2, x3, y3) -> bool:
    def lado(ax, ay, bx, by):
        return (px - bx) * (ay - by) - (ax - bx) * (py - by)
    d1, d2, d3 = lado(x1, y1, x2, y2), lado(x2, y2, x3, y3), lado(x3, y3, x1, y1)
    negativo = d1 < 0 or d2 < 0 or d3 < 0
    positivo = d1 > 0 or d2 > 0 or d3 > 0
    return not (negativo and positivo)


def _en_engranaje(px, py, cx, cy, hueco, diente, base, dientes) -> bool:
    r = math.hypot(px - cx, py - cy)
    if r < hueco:
        return False
    angulo = math.atan2(py - cy, px - cx)
    # Dientes de lados rectos: mitad del recorrido arriba, mitad abajo.
    arriba = math.cos(dientes * angulo) > 0.0
    return r <= (diente if arriba else base)


def _tapa(trazos, px, py) -> bool:
    for forma, *m in trazos:
        if forma == "linea":
            if _distancia_a_linea(px, py, *m) <= TRAZO / 2:
                return True
        elif forma == "aro":
            if abs(math.hypot(px - m[0], py - m[1]) - m[2]) <= TRAZO / 2:
                return True
        elif forma == "arco":
            if _en_arco(px, py, *m):
                return True
        elif forma == "punto":
            if math.hypot(px - m[0], py - m[1]) <= m[2]:
                return True
        elif forma == "triangulo":
            if _en_triangulo(px, py, *m):
                return True
        elif forma == "engranaje":
            if _en_engranaje(px, py, *m):
                return True
    return False


@lru_cache(maxsize=None)
def cobertura(nombre: str, lado: int) -> tuple[tuple[int, ...], ...]:
    """Cuánto tapa el dibujo cada píxel, de 0 a 255. No depende del color."""
    trazos = DIBUJOS[nombre]
    escala = 24 / lado
    paso = 1 / MUESTRAS
    total = MUESTRAS * MUESTRAS
    filas = []
    for y in range(lado):
        fila = []
        for x in range(lado):
            dentro = 0
            for sy in range(MUESTRAS):
                py = (y + (sy + 0.5) * paso) * escala
                for sx in range(MUESTRAS):
                    if _tapa(trazos, (x + (sx + 0.5) * paso) * escala, py):
                        dentro += 1
            fila.append(round(255 * dentro / total))
        filas.append(tuple(fila))
    return tuple(filas)


def _png(filas_rgba) -> bytes:
    """Un PNG de color con transparencia, sin librerías."""
    alto, ancho = len(filas_rgba), len(filas_rgba[0]) // 4
    crudo = bytearray()
    for fila in filas_rgba:
        crudo.append(0)  # sin filtro
        crudo.extend(fila)

    def trozo(etiqueta: bytes, datos: bytes) -> bytes:
        return (struct.pack(">I", len(datos)) + etiqueta + datos
                + struct.pack(">I", zlib.crc32(etiqueta + datos) & 0xFFFFFFFF))

    cabecera = struct.pack(">IIBBBBB", ancho, alto, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", cabecera)
            + trozo(b"IDAT", zlib.compress(bytes(crudo))) + trozo(b"IEND", b""))


def png(nombre: str, lado: int, color: str) -> bytes:
    """El icono en PNG, del color pedido («#rrggbb») y con fondo transparente."""
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    filas = []
    for fila in cobertura(nombre, lado):
        bytes_fila = bytearray()
        for alfa in fila:
            bytes_fila.extend((r, g, b, alfa))
        filas.append(bytes(bytes_fila))
    return _png(filas)


def imagen(maestro, nombre: str, lado: int, color: str) -> tk.PhotoImage:
    """Una PhotoImage lista para tkinter.

    Ojo: hay que guardar la referencia mientras se use. Si Python la tira,
    tkinter deja el hueco del icono en blanco sin avisar.
    """
    datos = base64.b64encode(png(nombre, lado, color))
    return tk.PhotoImage(master=maestro, data=datos, format="png")
