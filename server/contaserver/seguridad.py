"""Contraseñas y fichas de sesión, todo con la biblioteca estándar.

Dos piezas y nada más:

- Las contraseñas se guardan pasadas por scrypt con una sal aleatoria por
  usuario. En la base de datos nunca hay una contraseña, solo el resultado
  del amasado, que no tiene vuelta atrás.

- Las fichas (tokens) son texto firmado con HMAC: ``usuario_id.expira.firma``.
  El servidor no necesita guardarlas en ningún sitio: al recibir una basta
  con recalcular la firma y comparar. Si alguien cambia el id o la fecha,
  la firma deja de cuadrar.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time

# Parámetros de scrypt. Los recomendados para contraseñas: 16 MiB de memoria
# por intento, que hace inviable probar millones de contraseñas por segundo.
_SCRYPT_N = 2 ** 14
_SCRYPT_R = 8
_SCRYPT_P = 1
# scrypt con estos parámetros necesita 16 MiB justos; le damos holgura para
# que ninguna implementación lo rechace por rozar el límite.
_SCRYPT_MAXMEM = 64 * 1024 * 1024

# Una ficha vale treinta días. Después hay que volver a entrar.
DIAS_DE_SESION = 30


# --- contraseñas -------------------------------------------------------------

def nueva_sal() -> str:
    """Sal aleatoria en hexadecimal, distinta para cada usuario."""
    return secrets.token_hex(16)


def amasar_contrasena(contrasena: str, sal: str) -> str:
    """El hash de la contraseña con su sal, en hexadecimal."""
    resultado = hashlib.scrypt(
        contrasena.encode("utf-8"),
        salt=bytes.fromhex(sal),
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        maxmem=_SCRYPT_MAXMEM,
    )
    return resultado.hex()


def contrasena_correcta(contrasena: str, sal: str, hash_guardado: str) -> bool:
    """Compara en tiempo constante, para no chivar por cuánto tarda."""
    calculado = amasar_contrasena(contrasena, sal)
    return hmac.compare_digest(calculado, hash_guardado)


# --- fichas de sesión ---------------------------------------------------------

def secreto_del_servidor() -> tuple[bytes, bool]:
    """El secreto con el que se firman las fichas.

    Sale de la variable de entorno CONTAXCELL_SECRETO. Si no está puesta se
    genera uno aleatorio para poder arrancar igualmente, pero devuelve
    ``generado=True`` para que quien arranca pueda avisar: con un secreto
    de usar y tirar, las sesiones mueren cada vez que se reinicia el servidor.
    """
    valor = os.environ.get("CONTAXCELL_SECRETO", "").strip()
    if valor:
        return valor.encode("utf-8"), False
    return secrets.token_bytes(32), True


def _firma(secreto: bytes, usuario_id: int, expira: int) -> str:
    mensaje = f"{usuario_id}.{expira}".encode("utf-8")
    return hmac.new(secreto, mensaje, hashlib.sha256).hexdigest()


def crear_ficha(secreto: bytes, usuario_id: int) -> str:
    """Una ficha nueva: 'usuario_id.expira.firma'."""
    expira = int(time.time()) + DIAS_DE_SESION * 24 * 60 * 60
    return f"{usuario_id}.{expira}.{_firma(secreto, usuario_id, expira)}"


def validar_ficha(secreto: bytes, ficha: str) -> int | None:
    """Devuelve el id del usuario si la ficha es buena; None si no lo es.

    Una ficha es mala por cualquiera de estas razones: no tiene la forma
    esperada, la firma no cuadra, o ya ha caducado. No distinguimos entre
    ellas hacia fuera: todas son un 401.
    """
    partes = str(ficha or "").split(".")
    if len(partes) != 3:
        return None
    id_texto, expira_texto, firma_recibida = partes
    if not id_texto.isdigit() or not expira_texto.isdigit():
        return None
    usuario_id = int(id_texto)
    expira = int(expira_texto)
    esperada = _firma(secreto, usuario_id, expira)
    if not hmac.compare_digest(esperada, firma_recibida):
        return None
    if expira < int(time.time()):
        return None
    return usuario_id
