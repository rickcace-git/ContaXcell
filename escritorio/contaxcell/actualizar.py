"""Actualizar ContaXcell solo, desde el servidor.

Cómo va, de punta a punta:

1. Quien administra ContaXcell ejecuta `python publicar.py` en su ordenador.
   Eso fabrica el zip, lo firma con su llave y deja en el servidor el zip,
   una nota `version.json` (qué versión es, qué archivo y su resumen SHA-256)
   y la firma de esa nota.
2. Al abrir el programa, se pide la nota y su firma a /api/actualizacion/,
   con la ficha de la sesión: solo las cuentas aceptadas y sin vetar reciben
   versiones nuevas (sin cuenta, o en espera, el programa sigue funcionando
   en local, pero no se actualiza). Si la firma no es de su llave, no se hace
   nada más: se avisa y punto. Si lo es y la versión es más nueva, se
   pregunta antes de tocar nada.
3. Si se acepta, se baja el zip y se comprueba que su SHA-256 es el de la
   nota (que va firmada: así el zip queda firmado también, sin firmarlo aparte).
4. Se descomprime en una carpeta temporal y se lanza un PowerShell pequeño que
   espera a que el programa se cierre, copia lo nuevo encima de la carpeta del
   programa y lo vuelve a abrir. Hace falta así: Windows no deja reemplazar
   un .exe mientras está abierto. Mientras, ese mismo PowerShell enseña un
   cartelito («Reiniciando ContaXcell…») hasta que la ventana nueva aparece,
   para que nadie crea que se ha cerrado sin más.

La nota trae también el historial de cambios de las últimas versiones (los
mensajes de git, que `publicar.py` recoge) y con qué commits empieza y
acaba cada una, para el enlace a GitHub con el código. Cada programa
enseña solo las versiones que le faltan: quien salta de la 1.1.3 a la
1.1.6 ve lo de la 1.1.4, la 1.1.5 y la 1.1.6. Va dentro de la nota firmada,
así que tampoco se puede cambiar por el camino.

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
import re
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

RUTA_BASE = "/api/actualizacion/"
RUTA_NOTA = RUTA_BASE + "version.json"
RUTA_FIRMA = RUTA_BASE + "version.json.firma"
NOMBRE_EXE = "ContaXcell.exe"
SEGUNDOS = 15
# Un tope por si algo no cuadra: el zip pesa unos 11 MB.
TAMANO_MAXIMO = 200 * 1024 * 1024
# El enlace al código solo se abre si va aquí: aunque la nota venga firmada,
# el navegador no tiene por qué ir a ningún otro sitio desde el programa.
ENLACE_CODIGO = "https://github.com/"


class ActualizacionNoFiable(Exception):
    """Lo que hay en el servidor no viene firmado por quien administra
    ContaXcell, o el archivo no es el que dice la nota. No se instala."""


class SinActualizaciones(Exception):
    """No se ha podido preguntar: sin red, o el servidor no contesta."""


class SinPermiso(SinActualizaciones):
    """El servidor no da versiones nuevas a esta cuenta: está en espera de
    que la acepten, vetada, o la sesión ha caducado."""


@dataclass
class Novedad:
    version: str
    archivo: str      # la ruta en el servidor, p. ej. /api/actualizacion/ContaXcell-windows-1.1.0.zip
    sha256: str
    tamano: int
    notas: str = ""
    # (título, detalle) de cada cambio, del más nuevo al más viejo. Es lo
    # que leían la 1.1.3 y la 1.1.4; las de después usan el historial.
    cambios: tuple[tuple[str, str], ...] = ()
    codigo: str = ""  # el enlace a GitHub con lo cambiado, o ""
    # (versión, cambios, commit desde, commit hasta), la más nueva primero.
    historial: tuple[tuple[str, tuple[tuple[str, str], ...], str, str], ...] = ()
    repositorio: str = ""  # https://github.com/dueño/nombre

    def cambios_para(self, version_actual: str) -> list[tuple[str, tuple[tuple[str, str], ...]]]:
        """Lo que le falta a quien tiene `version_actual`: [(versión, cambios)],
        la más nueva primero. Sin historial (una nota de antes), lo que haya."""
        if self.historial:
            return [(v, c) for v, c, _d, _h in self.historial
                    if c and es_mas_nueva(v, version_actual)]
        return [(self.version, self.cambios)] if self.cambios else []

    def codigo_para(self, version_actual: str) -> str:
        """El enlace a GitHub con el código cambiado desde `version_actual`."""
        faltan = [h for h in self.historial if es_mas_nueva(h[0], version_actual)]
        if faltan and self.repositorio:
            return f"{self.repositorio}/compare/{faltan[-1][2][:12]}...{faltan[0][3][:12]}"
        return self.codigo


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


def _bajar(abrir_url, url: str, token: str) -> bytes:
    peticion = urllib.request.Request(url)
    peticion.add_header("Authorization", f"Bearer {token}")
    try:
        with abrir_url(peticion, timeout=SEGUNDOS) as respuesta:
            return respuesta.read(TAMANO_MAXIMO + 1)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise SinPermiso(f"el servidor ha contestado {error.code}") from None
        raise
    except (urllib.error.URLError, OSError) as error:
        raise SinActualizaciones(str(error)) from None


def buscar(servidor: str, version_actual: str, abrir_url=urllib.request.urlopen,
           publica: tuple[int, int] = LLAVE_PUBLICA, token: str = "") -> Novedad | None:
    """La versión nueva si la hay; None si no hay o si ya se tiene esa.

    Si el servidor todavía no ha publicado nada (404), es que no hay. Si hay
    nota pero la firma no cuadra, se lanza ActualizacionNoFiable: eso no es
    normal y merece decirse. Si la cuenta no tiene permiso, SinPermiso."""
    base = servidor.rstrip("/")
    try:
        nota = _bajar(abrir_url, base + RUTA_NOTA, token)
        firma_nota = _bajar(abrir_url, base + RUTA_FIRMA, token)
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
                          notas=str(datos.get("notas") or ""),
                          cambios=_cambios(datos.get("cambios")),
                          codigo=_codigo(datos.get("codigo")),
                          historial=_historial(datos.get("historial")),
                          repositorio=_codigo(datos.get("repositorio")).rstrip("/"))
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ActualizacionNoFiable("La nota de la actualización está mal escrita.") from None
    if not novedad.archivo.startswith(RUTA_BASE):
        raise ActualizacionNoFiable("La actualización apunta fuera de su sitio.")
    return novedad if es_mas_nueva(novedad.version, version_actual) else None


def _cambios(crudo) -> tuple[tuple[str, str], ...]:
    """La lista de cambios de la nota. Las notas de antes no la traen."""
    if not crudo:
        return ()
    return tuple((str(c.get("titulo") or "").strip(), str(c.get("detalle") or "").strip())
                 for c in crudo if str(c.get("titulo") or "").strip())


COMMIT = re.compile(r"[0-9a-f]{7,40}")


def _historial(crudo) -> tuple:
    """El historial de la nota. Una entrada con commits raros se queda sin
    enlace, no se tira: los cambios se pueden leer igual."""
    if not crudo:
        return ()
    entradas = []
    for e in crudo:
        desde, hasta = str(e.get("desde") or ""), str(e.get("hasta") or "")
        if not (COMMIT.fullmatch(desde) and COMMIT.fullmatch(hasta)):
            desde = hasta = ""
        entradas.append((str(e["version"]), _cambios(e.get("cambios")), desde, hasta))
    return tuple(entradas)


def _codigo(crudo) -> str:
    enlace = str(crudo or "").strip()
    return enlace if enlace.startswith(ENLACE_CODIGO) else ""


def descargar(servidor: str, novedad: Novedad, carpeta: Path,
              abrir_url=urllib.request.urlopen, token: str = "") -> Path:
    """Baja el zip y comprueba que es justo el de la nota. Si no, lo borra."""
    carpeta.mkdir(parents=True, exist_ok=True)
    destino = carpeta / f"ContaXcell-{novedad.version}.zip"
    try:
        datos = _bajar(abrir_url, servidor.rstrip("/") + novedad.archivo, token)
    except urllib.error.HTTPError as error:
        raise SinActualizaciones(f"el servidor ha contestado {error.code}") from None
    if len(datos) != novedad.tamano or hashlib.sha256(datos).hexdigest() != novedad.sha256:
        raise ActualizacionNoFiable(
            "El archivo descargado no es el que anuncia la actualización. "
            "No se ha instalado nada.")
    destino.write_bytes(datos)
    return destino


def preparar(zip_nuevo: Path, instalacion: Path, pid: int, trabajo: Path,
             centro: tuple[int, int] | None = None) -> Path:
    """Descomprime y escribe el PowerShell que hará el cambio. Devuelve su ruta.

    `centro` es dónde poner el cartel de «Reiniciando…» (el centro de la
    ventana del programa, que puede estar en la segunda pantalla). Sin él,
    sale en el centro de la principal.

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

    # El programa cuenta en píxeles de verdad (se declara «DPI aware») y
    # PowerShell, si no se le dice, en píxeles escalados: con la pantalla al
    # 125 % el cartel saldría en otro sitio. Por eso se declara igual, y el
    # tamaño se escala a mano.
    if centro is None:
        sitio = "$cartel.StartPosition = 'CenterScreen'\n"
    else:
        x, y = (int(c) for c in centro)
        sitio = ("$cartel.StartPosition = 'Manual'\n"
                 f"$cartel.Location = New-Object Drawing.Point([int]({x} - $ancho / 2), "
                 f"[int]({y} - $alto / 2))\n")

    guion = trabajo / "actualizar.ps1"
    # Con BOM: es lo que necesita PowerShell 5 para leer bien una ruta con
    # tildes o eñes (C:\Users\Begoña\…).
    guion.write_text(
        "# Cambia ContaXcell por la versión nueva y lo vuelve a abrir.\n"
        "# El cartel: entre que se cierra el programa y se abre el nuevo pasan\n"
        "# unos segundos sin nada en pantalla, y así se sabe que va.\n"
        "$cartel = $null\n"
        "try {\n"
        "    Add-Type -AssemblyName System.Windows.Forms, System.Drawing\n"
        "    Add-Type -Name Pantalla -Namespace ContaXcell -MemberDefinition "
        "'[DllImport(\"user32.dll\")] public static extern bool SetProcessDPIAware();'\n"
        "    [void][ContaXcell.Pantalla]::SetProcessDPIAware()\n"
        "    $escala = [Drawing.Graphics]::FromHwnd([IntPtr]::Zero).DpiX / 96\n"
        "    $ancho = [int](340 * $escala); $alto = [int](90 * $escala)\n"
        "    $cartel = New-Object Windows.Forms.Form\n"
        "    $cartel.FormBorderStyle = 'None'\n"
        "    $cartel.Size = New-Object Drawing.Size($ancho, $alto)\n"
        "    $cartel.TopMost = $true\n"
        "    $cartel.ShowInTaskbar = $false\n"
        "    $cartel.BackColor = [Drawing.Color]::FromArgb(150, 150, 150)\n"
        "    $cartel.Padding = New-Object Windows.Forms.Padding(1)\n"
        + "".join("    " + linea + "\n" for linea in sitio.splitlines())
        + "    $letrero = New-Object Windows.Forms.Label\n"
        "    $letrero.Dock = 'Fill'\n"
        "    $letrero.BackColor = [Drawing.Color]::White\n"
        "    $letrero.TextAlign = 'MiddleCenter'\n"
        "    $letrero.Font = New-Object Drawing.Font('Segoe UI', 11)\n"
        "    $letrero.Text = \"Reiniciando ContaXcell…`nSe abrirá solo en unos segundos.\"\n"
        "    $cartel.Controls.Add($letrero)\n"
        "    $cartel.Show()\n"
        "    [Windows.Forms.Application]::DoEvents()\n"
        "} catch { $cartel = $null }\n"
        f"Wait-Process -Id {int(pid)} -Timeout 120 -ErrorAction SilentlyContinue\n"
        "Start-Sleep -Milliseconds 500\n"
        f"robocopy {comillas(origen)} {comillas(instalacion)} /E /R:5 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null\n"
        f"$nuevo = Start-Process -FilePath {comillas(instalacion / NOMBRE_EXE)} -PassThru\n"
        "# El cartel se va cuando aparece la ventana nueva (o a los 30 s, por si acaso).\n"
        "for ($i = 0; $cartel -and $i -lt 150; $i++) {\n"
        "    [Windows.Forms.Application]::DoEvents()\n"
        "    if (-not $nuevo) { break }\n"
        "    $nuevo.Refresh()\n"
        "    if ($nuevo.HasExited -or $nuevo.MainWindowHandle -ne 0) { break }\n"
        "    Start-Sleep -Milliseconds 200\n"
        "}\n"
        "if ($cartel) { $cartel.Close() }\n"
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
