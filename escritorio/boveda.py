"""Todas las llaves de ContaXcell en un solo archivo cifrado, para llevarlas
de un ordenador a otro (por Google Drive, por ejemplo).

    python boveda.py guardar     en el ordenador que ya las tiene
    python boveda.py abrir       en el otro, con el archivo en Descargas

Una sola contraseña, que eliges tú al guardar y que no se apunta en ningún
sitio: sin ella, el archivo no sirve de nada aunque alguien lo encuentre. Al
abrir, cada cosa vuelve a su sitio sola.

Lo que va dentro:

- La llave para entrar en el servidor (~/.ssh/contaxcell.pem).
- La llave para firmar las actualizaciones (~/.contaxcell/llave-actualizaciones.json).
- La llave para firmar la app del móvil (~/ContaXcell-firma/).
- La dirección del servidor (escritorio/.env de este proyecto).
- Una copia de los secretos del servidor (el .env de la máquina), por si un
  día hay que montarlo de nuevo. Se deja en ~/.contaxcell/servidor.env.

Cómo se cifra, para quien lo revise: la contraseña pasa por scrypt (lento a
propósito, para que probar contraseñas a lo bruto salga carísimo) y da dos
llaves; con una se cifra (HMAC-SHA256 en modo contador) y con la otra se
sella el resultado (HMAC-SHA256). Todo de la biblioteca estándar de Python:
no hay que instalar nada en el otro ordenador.
"""

from __future__ import annotations

import getpass
import hashlib
import hmac
import io
import os
import secrets
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
CASA = Path.home()
ARCHIVO = CASA / "Downloads" / "ContaXcell-llaves.cxb"
CABECERA = b"CXBOVEDA1"
CONTRASENA_MINIMA = 10

# Dónde vive cada cosa: nombre dentro del archivo → sitio en el ordenador.
SITIOS = {
    "ssh/contaxcell.pem": CASA / ".ssh" / "contaxcell.pem",
    "contaxcell/llave-actualizaciones.json": CASA / ".contaxcell" / "llave-actualizaciones.json",
    "escritorio/.env": RAIZ / ".env",
}
CARPETA_FIRMA_MOVIL = CASA / "ContaXcell-firma"
COPIA_SERVIDOR = CASA / ".contaxcell" / "servidor.env"


# --- el cifrado -----------------------------------------------------------------

def _llaves(contrasena: str, sal: bytes) -> tuple[bytes, bytes]:
    material = hashlib.scrypt(contrasena.encode("utf-8"), salt=sal, n=2 ** 15, r=8, p=1,
                              maxmem=64 * 1024 * 1024, dklen=64)
    return material[:32], material[32:]


def _flujo(llave: bytes, largo: int) -> bytes:
    trozos = []
    for i in range((largo + 31) // 32):
        trozos.append(hmac.new(llave, i.to_bytes(8, "big"), hashlib.sha256).digest())
    return b"".join(trozos)[:largo]


def cifrar(datos: bytes, contrasena: str) -> bytes:
    sal = secrets.token_bytes(16)
    llave_cifrar, llave_sellar = _llaves(contrasena, sal)
    cifrado = bytes(a ^ b for a, b in zip(datos, _flujo(llave_cifrar, len(datos))))
    sello = hmac.new(llave_sellar, CABECERA + sal + cifrado, hashlib.sha256).digest()
    return CABECERA + sal + sello + cifrado


class ContrasenaMala(Exception):
    """La contraseña no es la buena, o el archivo está estropeado."""


def descifrar(archivo: bytes, contrasena: str) -> bytes:
    if not archivo.startswith(CABECERA) or len(archivo) < len(CABECERA) + 48:
        raise ContrasenaMala("Esto no es un archivo de llaves de ContaXcell.")
    sal = archivo[len(CABECERA):len(CABECERA) + 16]
    sello = archivo[len(CABECERA) + 16:len(CABECERA) + 48]
    cifrado = archivo[len(CABECERA) + 48:]
    llave_cifrar, llave_sellar = _llaves(contrasena, sal)
    esperado = hmac.new(llave_sellar, CABECERA + sal + cifrado, hashlib.sha256).digest()
    if not hmac.compare_digest(sello, esperado):
        raise ContrasenaMala("La contraseña no es la buena (o el archivo se ha estropeado).")
    return bytes(a ^ b for a, b in zip(cifrado, _flujo(llave_cifrar, len(cifrado))))


# --- guardar y abrir ---------------------------------------------------------------

def _secretos_del_servidor() -> bytes | None:
    """El .env de la máquina, por ssh. Si no se llega, se sigue sin él."""
    from contaxcell.sincronia import servidor_de_fabrica
    import urllib.parse
    maquina = urllib.parse.urlparse(servidor_de_fabrica()).hostname
    resultado = subprocess.run(
        ["ssh", "-i", str(SITIOS["ssh/contaxcell.pem"]), "-o", "BatchMode=yes",
         "-o", "ConnectTimeout=15", f"ubuntu@{maquina}", "cat server/.env"],
        capture_output=True)
    return resultado.stdout if resultado.returncode == 0 and resultado.stdout else None


def guardar() -> int:
    sys.path.insert(0, str(RAIZ))
    memoria = io.BytesIO()
    metido = []
    with zipfile.ZipFile(memoria, "w", zipfile.ZIP_DEFLATED) as z:
        for nombre, sitio in SITIOS.items():
            if sitio.is_file():
                z.write(sitio, nombre)
                metido.append(nombre)
            else:
                print(f"  (no está {sitio}: va sin ello)")
        if CARPETA_FIRMA_MOVIL.is_dir():
            for archivo in sorted(CARPETA_FIRMA_MOVIL.iterdir()):
                if archivo.is_file():
                    z.write(archivo, f"firma-movil/{archivo.name}")
            metido.append("firma-movil/")
        servidor = _secretos_del_servidor()
        if servidor:
            z.writestr("servidor/.env", servidor)
            metido.append("servidor/.env")
        else:
            print("  (no se ha podido leer el .env del servidor: va sin él)")

    print("\nElige una contraseña para el archivo. Que sea larga (una frase vale)\n"
          "y apúntala donde no se pierda: sin ella no se puede abrir, ni yo puedo.")
    while True:
        contrasena = getpass.getpass("Contraseña (no se ve al escribir): ")
        if len(contrasena) < CONTRASENA_MINIMA:
            print(f"Mejor de {CONTRASENA_MINIMA} caracteres o más.")
            continue
        if getpass.getpass("Repítela: ") != contrasena:
            print("No coinciden. Otra vez.")
            continue
        break
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    ARCHIVO.write_bytes(cifrar(memoria.getvalue(), contrasena))
    print(f"\nHecho: {ARCHIVO}\nLleva: {', '.join(metido)}\n\n"
          "Súbelo a Google Drive y, en el otro ordenador, bájalo a Descargas y:\n"
          "    python boveda.py abrir")
    return 0


def _poner(destino: Path, datos: bytes) -> str:
    if destino.is_file() and destino.read_bytes() == datos:
        return "ya estaba"
    destino.parent.mkdir(parents=True, exist_ok=True)
    nota = ""
    if destino.exists():
        destino.replace(destino.with_name(destino.name + ".antes"))
        nota = f" (el que había queda como {destino.name}.antes)"
    destino.write_bytes(datos)
    return "puesto" + nota


def _solo_para_mi(ruta: Path) -> None:
    """La llave del servidor, que solo la pueda leer su dueño: si no, el ssh
    de Windows se niega a usarla."""
    if os.name == "nt":
        subprocess.run(["icacls", str(ruta), "/inheritance:r", "/grant:r",
                        f"{os.environ.get('USERNAME', '')}:(R)"], capture_output=True)
    else:
        ruta.chmod(0o600)


def abrir(ruta: Path) -> int:
    if not ruta.is_file():
        print(f"No encuentro {ruta}. Bájalo de Google Drive a Descargas, o di dónde está:\n"
              "    python boveda.py abrir C:\\ruta\\al\\ContaXcell-llaves.cxb")
        return 1
    contrasena = getpass.getpass("Contraseña del archivo (no se ve al escribir): ")
    try:
        datos = descifrar(ruta.read_bytes(), contrasena)
    except ContrasenaMala as error:
        print(error)
        return 1
    with zipfile.ZipFile(io.BytesIO(datos)) as z:
        for nombre in z.namelist():
            if nombre in SITIOS:
                destino = SITIOS[nombre]
            elif nombre.startswith("firma-movil/"):
                destino = CARPETA_FIRMA_MOVIL / Path(nombre).name
            elif nombre == "servidor/.env":
                destino = COPIA_SERVIDOR
            else:
                continue
            print(f"  {destino}: {_poner(destino, z.read(nombre))}")
            if nombre == "ssh/contaxcell.pem":
                _solo_para_mi(destino)
    print("\nListo. Ya puedes entrar en el servidor y publicar desde este ordenador.\n"
          "Cuando acabes, borra el archivo de Descargas y de Google Drive si ya no lo\n"
          "necesitas allí.")
    return 0


def main() -> int:
    orden = sys.argv[1] if len(sys.argv) > 1 else ""
    if orden == "guardar":
        return guardar()
    if orden == "abrir":
        return abrir(Path(sys.argv[2]) if len(sys.argv) > 2 else ARCHIVO)
    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
