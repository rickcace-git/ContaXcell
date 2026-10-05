"""Actualizar ContaXcell solo, desde el servidor.

Cómo va, de punta a punta:

1. Quien administra ContaXcell ejecuta `python publicar.py` en su ordenador.
   Eso fabrica el zip, lo firma con su llave y deja en el servidor, en
   /descargas/, el zip, una nota `version.json` (qué versión es, qué archivo y
   su resumen SHA-256) y la firma de esa nota.
2. Al abrir el programa, se pide la nota y su firma. Si la firma no es de su
   llave, no se hace nada más: se avisa y punto. Si lo es y la versión es más
   nueva, se pregunta antes de tocar nada.
3. Si se acepta, se baja el zip y se comprueba que su SHA-256 es el de la
   nota (que va firmada: así el zip queda firmado también, sin firmarlo aparte).
4. Se descomprime en una carpeta temporal y se lanza un PowerShell pequeño que
   espera a que el programa se cierre, copia lo nuevo encima de la carpeta del
   programa y lo vuelve a abrir. Hace falta así: Windows no deja reemplazar
   un .exe mientras está abierto.

Los datos no se tocan nunca: viven en %APPDATA%\\ContaXcell, no en la carpeta
del programa. Lo que se cambia es solo el programa.

Solo actúa en el programa empaquetado (el .exe). Desde el código fuente
(`python ejecutar.py`) no hay nada que actualizar: eso se actualiza con git.

Este módulo no importa tkinter: la ventana lo llama desde un hilo y recoge
el resultado, igual que con la sincronización.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from . import firma
from .llave_publica import LLAVE_PUBLICA

RUTA_NOTA = "/descargas/version.json"
RUTA_FIRMA = "/descargas/version.json.firma"
NOMBRE_EXE = "ContaXcell.exe"
SEGUNDOS = 15
# Un tope por si algo no cuadra: el zip pesa unos 11 MB.
TAMANO_MAXIMO = 200 * 1024 * 1024


class ActualizacionNoFiable(Exception):
    """Lo que hay en el servidor no viene firmado por quien administra
    ContaXcell, o el archivo no es el que dice la nota. No se instala."""


class SinActualizaciones(Exception):
    """No se ha podido preguntar: sin red, o el servidor no contesta."""


@dataclass
class Novedad:
    version: str
    archivo: str      # la ruta en el servidor, p. ej. /descargas/ContaXcell-windows-1.1.0.zip
    sha256: str
    tamano: int
    notas: str = ""


def version_en_numeros(texto: str) -> tuple[int, ...]:
    """«1.10.2» → (1, 10, 2). Se compara así y no como texto: si no, 1.10 < 1.9."""
    partes = []
    for trozo in str(texto).strip().split("."):
        digitos = "".join(c for c in trozo if c.isdigit())
        partes.append(int(digitos) if digitos else 0)
    return tuple(partes)


def es_mas_nueva(remota: str, actual: str) -> bool:
    a, b = version_en_numeros(remota), version_en_numeros(actual)
    largo = max(len(a), len(b))
    return a + (0,) * (largo - len(a)) > b + (0,) * (largo - len(b))


def instalacion_actual() -> Path | None:
    """La carpeta del programa, si se está ejecutando el .exe; None desde el
    código fuente, que no se actualiza por aquí."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return None


def _bajar(abrir_url, url: str) -> bytes:
    try:
        with abrir_url(urllib.request.Request(url), timeout=SEGUNDOS) as respuesta:
            return respuesta.read(TAMANO_MAXIMO + 1)
    except urllib.error.HTTPError:
        raise
    except (urllib.error.URLError, OSError) as error:
        raise SinActualizaciones(str(error)) from None


def buscar(servidor: str, version_actual: str, abrir_url=urllib.request.urlopen,
           publica: tuple[int, int] = LLAVE_PUBLICA) -> Novedad | None:
    """La versión nueva si la hay; None si no hay o si ya se tiene esa.

    Si el servidor todavía no ha publicado nada (404), es que no hay. Si hay
    nota pero la firma no cuadra, se lanza ActualizacionNoFiable: eso no es
    normal y merece decirse."""
    base = servidor.rstrip("/")
    try:
        nota = _bajar(abrir_url, base + RUTA_NOTA)
        firma_nota = _bajar(abrir_url, base + RUTA_FIRMA)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise SinActualizaciones(f"el servidor ha contestado {error.code}") from None
    if not firma.comprobar(nota, firma_nota, publica):
        raise ActualizacionNoFiable(
            "La actualización del servidor no viene firmada por quien "
            "administra ContaXcell. No se ha instalado nada.")
    try:
        datos = json.loads(nota.decode("utf-8"))
        novedad = Novedad(version=str(datos["version"]), archivo=str(datos["archivo"]),
                          sha256=str(datos["sha256"]).lower(), tamano=int(datos["tamano"]),
                          notas=str(datos.get("notas") or ""))
    except (ValueError, KeyError, TypeError):
        raise ActualizacionNoFiable("La nota de la actualización está mal escrita.") from None
    if not novedad.archivo.startswith("/descargas/"):
        raise ActualizacionNoFiable("La actualización apunta fuera de las descargas.")
    return novedad if es_mas_nueva(novedad.version, version_actual) else None


def descargar(servidor: str, novedad: Novedad, carpeta: Path,
              abrir_url=urllib.request.urlopen) -> Path:
    """Baja el zip y comprueba que es justo el de la nota. Si no, lo borra."""
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"ContaXcell-{novedad.version}.zip"
    try:
        datos = _bajar(abrir_url, servidor.rstrip("/") + novedad.archivo)
    except urllib.error.HTTPError as error:
        raise SinActualizaciones(f"el servidor ha contestado {error.code}") from None
    if len(datos) != novedad.tamano or hashlib.sha256(datos).hexdigest() != novedad.sha256:
        raise ActualizacionNoFiable(
            "El archivo descargado no es el que anuncia la actualización. "
            "No se ha instalado nada.")
    destino.write_bytes(datos)
    return destino


def preparar(zip_nuevo: Path, instalacion: Path, pid: int, trabajo: Path) -> Path:
    """Descomprime y escribe el PowerShell que hará el cambio. Devuelve su ruta.

    El zip trae una carpeta ContaXcell/ con el .exe dentro; si no, no es un
    ContaXcell y no se sigue."""
    nueva = trabajo / "nueva"
    if nueva.exists():
        shutil.rmtree(nueva)
    with zipfile.ZipFile(zip_nuevo) as comprimido:
        for nombre in comprimido.namelist():
            # Nada que se salga de la carpeta (rutas con «..» o absolutas).
            destino = (nueva / nombre).resolve()
            if not str(destino).startswith(str(nueva.resolve())):
                raise ActualizacionNoFiable("El zip trae rutas raras. No se ha instalado nada.")
        comprimido.extractall(nueva)
    origen = nueva / "ContaXcell"
    if not (origen / NOMBRE_EXE).is_file():
        raise ActualizacionNoFiable("El zip no trae ContaXcell.exe. No se ha instalado nada.")

    def comillas(ruta: Path) -> str:
        return "'" + str(ruta).replace("'", "''") + "'"

    guion = trabajo / "actualizar.ps1"
    # Con BOM: es lo que necesita PowerShell 5 para leer bien una ruta con
    # tildes o eñes (C:\Users\Begoña\…).
    guion.write_text(
        "# Cambia ContaXcell por la versión nueva y lo vuelve a abrir.\n"
        f"Wait-Process -Id {int(pid)} -Timeout 120 -ErrorAction SilentlyContinue\n"
        "Start-Sleep -Milliseconds 500\n"
        f"robocopy {comillas(origen)} {comillas(instalacion)} /E /R:5 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null\n"
        f"Start-Process -FilePath {comillas(instalacion / NOMBRE_EXE)}\n"
        f"Remove-Item -Recurse -Force {comillas(nueva)} -ErrorAction SilentlyContinue\n"
        f"Remove-Item -Force {comillas(zip_nuevo)} -ErrorAction SilentlyContinue\n",
        encoding="utf-8-sig")
    return guion


def lanzar(guion: Path) -> None:
    """Arranca el PowerShell suelto y sin ventana: tiene que seguir vivo
    cuando el programa se cierre, que es justo lo que está esperando."""
    banderas = 0
    if os.name == "nt":
        # Sin ventana negra y en su propio grupo, para que cerrar el programa
        # no se lo lleve por delante. (DETACHED_PROCESS no: anula al otro.)
        banderas = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden",
         "-File", str(guion)],
        creationflags=banderas, close_fds=True)


def carpeta_de_trabajo() -> Path:
    return Path(tempfile.gettempdir()) / "contaxcell-actualizacion"
