"""Firmas de las actualizaciones: RSA con SHA-256, sin librerías.

El actualizador es una puerta para meter un programa nuevo en el ordenador
de cada uno, así que no se fía de nadie: ni del servidor ni de la red. Solo
instala lo que viene firmado con la llave de quien administra ContaXcell, que
vive en su ordenador y en ningún otro sitio (ni en el servidor ni en git).
Aquí dentro solo va la mitad pública, la que sirve para comprobar y no para
firmar: aunque alguien se colase en el servidor, no podría fabricar una
actualización que el programa aceptara.

Es RSA de manual (PKCS#1 v1.5 con SHA-256, el de toda la vida): firmar es
elevar a la llave privada, comprobar es elevar a la pública y mirar que salga
lo mismo. Python sabe hacer potencias de números enormes (`pow`), así que no
hace falta nada más. Generar la llave sí es más lento, pero se hace una vez.

Ni tkinter ni disco: se prueba entero sin ventana.
"""

from __future__ import annotations

import hashlib
import hmac
import math
import secrets

# Lo que dice «esto es un SHA-256» dentro de la firma (DigestInfo, RFC 8017).
_PREFIJO_SHA256 = bytes.fromhex("3031300d060960864801650304020105000420")
E = 65537
BITS = 3072


def _relleno(mensaje: bytes, largo: int) -> bytes:
    """El bloque que se firma: 00 01 FF…FF 00, la marca del SHA-256 y el
    resumen del mensaje, del largo exacto de la llave."""
    resumen = _PREFIJO_SHA256 + hashlib.sha256(mensaje).digest()
    if largo < len(resumen) + 11:
        raise ValueError("La llave es demasiado corta para firmar.")
    return b"\x00\x01" + b"\xff" * (largo - len(resumen) - 3) + b"\x00" + resumen


def _largo(n: int) -> int:
    return (n.bit_length() + 7) // 8


def firmar(mensaje: bytes, llave: dict) -> bytes:
    """Firma con la llave privada ({"n", "e", "d"}). Solo en publicar.py."""
    n, d = llave["n"], llave["d"]
    k = _largo(n)
    return pow(int.from_bytes(_relleno(mensaje, k), "big"), d, n).to_bytes(k, "big")


def comprobar(mensaje: bytes, firma: bytes, publica: tuple[int, int]) -> bool:
    """Si la firma es de la llave privada que va con esta pública."""
    n, e = publica
    k = _largo(n)
    if len(firma) != k:
        return False
    numero = int.from_bytes(firma, "big")
    if numero >= n:
        return False
    return hmac.compare_digest(pow(numero, e, n).to_bytes(k, "big"), _relleno(mensaje, k))


# --- la llave: una vez, en el ordenador de quien publica --------------------------

_PRIMOS_PEQUENOS = [p for p in range(3, 2000, 2) if all(p % q for q in range(3, int(p ** 0.5) + 1, 2))]


def _es_primo(n: int, rondas: int = 40) -> bool:
    """Miller-Rabin: con 40 rondas, la probabilidad de colar un compuesto es
    menor que la de que caiga un meteorito en el teclado mientras se genera."""
    if n < 2:
        return False
    for p in _PRIMOS_PEQUENOS:
        if n % p == 0:
            return n == p
    d, r = n - 1, 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for _ in range(rondas):
        x = pow(secrets.randbelow(n - 3) + 2, d, n)
        if x in (1, n - 1):
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True


def _primo(bits: int) -> int:
    while True:
        # Los dos bits de arriba puestos, para que p·q tenga el largo pedido.
        candidato = secrets.randbits(bits) | (0b11 << (bits - 2)) | 1
        if _es_primo(candidato):
            return candidato


def generar_llave(bits: int = BITS) -> dict:
    """Una llave nueva: {"n", "e", "d"}. La pública es (n, e)."""
    while True:
        p, q = _primo(bits // 2), _primo(bits - bits // 2)
        phi = (p - 1) * (q - 1)
        if p == q or math.gcd(E, phi) != 1:
            continue
        n = p * q
        if n.bit_length() == bits:
            return {"n": n, "e": E, "d": pow(E, -1, phi)}
