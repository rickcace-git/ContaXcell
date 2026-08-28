"""Contraseñas y fichas de sesión, todo con la biblioteca estándar.

Dos piezas y nada más:

- Las contraseñas se guardan pasadas por scrypt con una sal aleatoria por
  usuario. En la base de datos nunca hay una contraseña, solo el resultado
  del amasado, que no tiene vuelta atrás.

- Las fichas (tokens) son texto firmado con HMAC:
  ``usuario_id.generacion.expira.firma``. El servidor no necesita guardarlas
  en ningún sitio: al recibir una basta con recalcular la firma y comparar.
  Si alguien cambia el id, la generación o la fecha, la firma deja de cuadrar.

La *generación* es un contador que vive en la fila del usuario y sube en uno
cada vez que cambia la contraseña. La ficha lleva dentro la generación con la
que se emitió, así que al cambiar la contraseña todas las fichas de antes
dejan de valer de golpe: es la forma de echar a la calle una sesión robada
sin tener que guardar la lista de fichas vivas en ninguna parte.
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

# Un secreto más corto que esto no vale: con pocos caracteres se puede probar
# hasta acertar y quien acierte se fabrica las fichas que quiera.
SECRETO_MINIMO = 32


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

    Si está puesta pero es corta, el servidor no arranca. Es mejor negarse
    que dejar el servidor en pie con una cerradura de juguete.
    """
    valor = os.environ.get("CONTAXCELL_SECRETO", "").strip()
    if valor:
        if len(valor) < SECRETO_MINIMO:
            raise RuntimeError(
                f"CONTAXCELL_SECRETO es demasiado corto: tiene {len(valor)} "
                f"caracteres y hacen falta al menos {SECRETO_MINIMO}. Genera "
                "uno con «openssl rand -hex 32» (o, sin openssl, con "
                "«python -c \"import secrets; print(secrets.token_hex(32))\"») "
                "y ponlo en el archivo .env."
            )
        return valor.encode("utf-8"), False
    return secrets.token_bytes(32), True


def _firma(secreto: bytes, usuario_id: int, generacion: int, expira: int) -> str:
    mensaje = f"{usuario_id}.{generacion}.{expira}".encode("utf-8")
    return hmac.new(secreto, mensaje, hashlib.sha256).hexdigest()


def crear_ficha(secreto: bytes, usuario_id: int, generacion: int) -> str:
    """Una ficha nueva: 'usuario_id.generacion.expira.firma'."""
    expira = int(time.time()) + DIAS_DE_SESION * 24 * 60 * 60
    firma = _firma(secreto, usuario_id, generacion, expira)
    return f"{usuario_id}.{generacion}.{expira}.{firma}"


def _entero(texto: str) -> int | None:
    """El número que dice el texto, o None si no es un entero de los normales.

    Hay que ser tiquismiquis aquí: ``"²".isdigit()`` es True pero ``int("²")``
    revienta, y una ficha cualquiera venida de fuera no puede tumbar el
    servidor. Solo aceptamos dígitos ASCII y, aun así, el ``int()`` va
    envuelto: un número de miles de cifras también se queja, y eso cabe de
    sobra en una cabecera.
    """
    if not texto or not texto.isascii() or not texto.isdecimal():
        return None
    try:
        return int(texto)
    except ValueError:
        return None


def validar_ficha(secreto: bytes, ficha: str) -> tuple[int, int] | None:
    """(id de usuario, generación) si la ficha es buena; None si no lo es.

    Una ficha es mala por cualquiera de estas razones: no tiene la forma
    esperada, trae algo que no es un número donde va un número, la firma no
    cuadra, o ya ha caducado. No distinguimos entre ellas hacia fuera: todas
    son un 401. Las fichas del formato antiguo (tres trozos, sin generación)
    caen aquí también, y su dueño solo tiene que volver a entrar.
    """
    partes = str(ficha or "").split(".")
    if len(partes) != 4:
        return None
    id_texto, generacion_texto, expira_texto, firma_recibida = partes
    usuario_id = _entero(id_texto)
    generacion = _entero(generacion_texto)
    expira = _entero(expira_texto)
    if usuario_id is None or generacion is None or expira is None:
        return None
    esperada = _firma(secreto, usuario_id, generacion, expira)
    if not hmac.compare_digest(esperada, firma_recibida):
        return None
    if expira < int(time.time()):
        return None
    return usuario_id, generacion
