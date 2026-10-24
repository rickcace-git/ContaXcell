"""Convierte ContaXcell en un programa que se puede repartir.

    python empaquetar.py

Hace el del sistema en el que se ejecuta: PyInstaller no sabe construir para
otro. En Windows deja en `dist/` una carpeta con el .exe y todo lo que
necesita, y un .zip de esa carpeta listo para enviar. En el Mac deja
`ContaXcell.app` y un .dmg con ella dentro, que es como se reparten allí los
programas: se abre y se arrastra a Aplicaciones.

Se empaqueta en carpeta y no en un único archivo (`--onefile`) a propósito. Un
.exe de un solo archivo se descomprime en una carpeta temporal cada vez que se
abre, que es exactamente lo que hace el software malicioso, y por eso los
antivirus lo marcan mucho más a menudo. La carpeta arranca antes y da bastantes
menos disgustos al mandársela a alguien. (Una .app del Mac es también una
carpeta, aunque el Finder la enseñe como un solo archivo.)
"""

from __future__ import annotations

import argparse
import os
import plistlib
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import NamedTuple

RAIZ = Path(__file__).resolve().parent
NOMBRE = "ContaXcell"
ES_MAC = sys.platform == "darwin"
# Windows quiere el icono en .ico y el Mac en .icns. Además de ese, que es el
# del archivo, va dentro el de la ventana: el .ico en Windows y en el Mac el
# PNG, que es el que Tk sabe poner en el Dock.
ICONO = RAIZ / "recursos" / ("icono.icns" if ES_MAC else "icono.ico")
ICONO_VENTANA = RAIZ / "recursos" / ("icono.png" if ES_MAC else "icono.ico")
# Con qué nombre la conoce el Mac por dentro. Va al revés, como las direcciones
# de internet, y lo único que pide es no coincidir con el de otro programa.
IDENTIFICADOR_MAC = "es.contaxcell.ContaXcell"
# La dirección del servidor, que es distinta en cada despliegue y no está en el
# repositorio. Va dentro del programa para que quien lo reciba no tenga que
# escribirla: sin ella, el ejecutable saldría apuntando a localhost, o sea, a
# ningún sitio útil para quien no seas tú.
ENV = RAIZ / ".env"

# Lo que PyInstaller podría meter de más si lo encuentra instalado. Fuera
# hace la carpeta bastante más pequeña y el arranque más rápido.
SOBRAN = [
    "numpy", "pandas", "matplotlib", "scipy", "PIL", "PyQt5", "PyQt6",
    "PySide2", "PySide6", "IPython", "pytest", "setuptools", "pip",
    "lxml", "defusedxml", "et_xmlfile.tests",
]


def comprobar_pyinstaller() -> bool:
    try:
        import PyInstaller  # noqa: F401
        return True
    except ImportError:
        print("Falta PyInstaller, que es lo que crea el ejecutable.\n"
              "Instálalo con:\n\n    pip install pyinstaller\n")
        return False


def comprobar_env() -> bool:
    """Sin `.env` no se empaqueta: es el fallo que no se ve hasta que alguien
    abre el programa en su casa y no puede entrar."""
    if ENV.exists():
        return True
    print(f"Falta {ENV.name}, que es donde va la dirección del servidor.\n"
          "Sin él, el programa saldría apuntando a este mismo ordenador y\n"
          "quien lo reciba no podría entrar. Créalo con:\n\n"
          "    cp .env.ejemplo .env\n\n"
          "y pon dentro la dirección de tu servidor.\n")
    return False


def preparar_icono() -> None:
    if ICONO.exists() and ICONO_VENTANA.exists():
        return
    print("No estaba el icono; lo genero…")
    subprocess.run([sys.executable, str(RAIZ / "recursos" / "hacer_icono.py")],
                   check=True, cwd=RAIZ)


def limpiar() -> None:
    for carpeta in ("build", "dist"):
        ruta = RAIZ / carpeta
        if ruta.exists():
            shutil.rmtree(ruta)
    especificacion = RAIZ / f"{NOMBRE}.spec"
    if especificacion.exists():
        especificacion.unlink()


def construir(consola: bool) -> Path:
    orden = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--onedir",
        # Sin ventana negra de fondo: es una aplicación con interfaz. En el
        # Mac, además, es lo que hace que salga una .app.
        "--console" if consola else "--windowed",
        "--name", NOMBRE,
        "--icon", str(ICONO),
        # El icono también va dentro, para la ventana y la barra de tareas.
        "--add-data", f"{ICONO_VENTANA}{os.pathsep}recursos",
        # Y la dirección del servidor, que si no el programa no sabría con
        # quién hablar en el ordenador de quien lo reciba.
        "--add-data", f"{ENV}{os.pathsep}recursos",
        str(RAIZ / "ejecutar.py"),
    ]
    if ES_MAC:
        orden += ["--osx-bundle-identifier", IDENTIFICADOR_MAC]
    else:
        # Todo lo accesorio en una subcarpeta: así lo primero que se ve al
        # abrir la carpeta es el ejecutable y no cien archivos sueltos. La
        # .app del Mac ya lo esconde todo dentro de sí misma.
        orden += ["--contents-directory", "recursos-internos"]
    for modulo in SOBRAN:
        orden += ["--exclude-module", modulo]

    print("Construyendo… esto tarda un par de minutos.\n")
    subprocess.run(orden, check=True, cwd=RAIZ)
    if ES_MAC and not consola:
        return RAIZ / "dist" / f"{NOMBRE}.app"
    return RAIZ / "dist" / NOMBRE


class RequisitosMac(NamedTuple):
    macos: str                    # la versión mínima, «26.0»
    procesadores: frozenset[str]  # «arm64» (chip de Apple), «x86_64» (Intel)


# Cómo empieza un binario del Mac: de 64 y 32 bits, y los «gordos», que llevan
# dentro el código de más de un procesador.
_MAGIAS_MACH_O = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe",
                  b"\xca\xfe\xba\xbe", b"\xca\xfe\xba\xbf"}


def requisitos_mac(aplicacion: Path) -> RequisitosMac:
    """Desde qué macOS y en qué procesadores funciona la .app, leído de los
    binarios que lleva dentro.

    No es el Mac en el que se construye: el Python de Homebrew, por ejemplo,
    viene compilado solo para el chip de Apple y para el último macOS. Manda
    el más exigente de todos, que con uno solo que no cargue ya no arranca.
    """
    minima, procesadores = (0,), None
    for archivo in sorted(aplicacion.rglob("*")):
        if archivo.is_symlink() or not archivo.is_file():
            continue
        with archivo.open("rb") as binario:
            if binario.read(4) not in _MAGIAS_MACH_O:
                continue
        suyos = frozenset(_salida(["lipo", "-archs", str(archivo)]).split())
        procesadores = suyos if procesadores is None else procesadores & suyos
        cargas = _salida(["otool", "-arch", "all", "-l", str(archivo)])
        # Los modernos lo dicen en «minos»; los antiguos, en su propia orden.
        versiones = re.findall(r"minos (\d[\d.]*)", cargas) + re.findall(
            r"LC_VERSION_MIN_MACOSX\n\s+cmdsize \d+\n\s+version (\d[\d.]*)", cargas)
        for version in versiones:
            minima = max(minima, tuple(int(trozo) for trozo in version.split(".")))
    return RequisitosMac(".".join(map(str, minima)), procesadores or frozenset())


def _salida(orden: list[str]) -> str:
    return subprocess.run(orden, check=True, capture_output=True, text=True).stdout


def completar_info(aplicacion: Path, requisitos: RequisitosMac) -> None:
    """PyInstaller deja la .app diciendo que es la versión 0.0.0, que es lo que
    luego enseña el Finder, y sin decir qué macOS necesita: en uno anterior no
    llegaría ni a dar un error que se entienda. Se corrige a mano y se vuelve a
    firmar: la firma cubre el Info.plist, y con la firma rota el Mac no la abre.

    La firma es la «ad hoc», la que no dice quién lo ha hecho. Es lo que
    PyInstaller ya hacía por su cuenta; la de verdad, la que quita el aviso
    de la primera vez, es de pago (ver el README).
    """
    from contaxcell.ventana import VERSION

    info = aplicacion / "Contents" / "Info.plist"
    with info.open("rb") as archivo:
        datos = plistlib.load(archivo)
    datos["CFBundleShortVersionString"] = VERSION
    datos["CFBundleVersion"] = VERSION
    datos["LSMinimumSystemVersion"] = requisitos.macos
    # Que el Mac la sepa en español: así los cuadros que pinta él (abrir y
    # guardar archivos, sobre todo) salen en castellano y no en inglés.
    datos["CFBundleDevelopmentRegion"] = "es"
    datos["CFBundleLocalizations"] = ["es"]
    with info.open("wb") as archivo:
        plistlib.dump(datos, archivo)
    subprocess.run(["codesign", "--force", "--sign", "-", str(aplicacion)], check=True)


def crear_dmg(aplicacion: Path) -> Path:
    """El .dmg es el disco que se abre con doble clic. Lleva la aplicación,
    el LÉEME y un atajo a Aplicaciones para arrastrarla encima."""
    preparacion = RAIZ / "build" / "dmg"
    if preparacion.exists():
        shutil.rmtree(preparacion)
    preparacion.mkdir(parents=True)
    # `ditto` y no `shutil.copytree`: copia la .app sin romperle los enlaces
    # internos ni la firma.
    subprocess.run(["ditto", str(aplicacion), str(preparacion / aplicacion.name)],
                   check=True)
    shutil.copy2(aplicacion.parent / "LÉEME.txt", preparacion / "LÉEME.txt")
    (preparacion / "Aplicaciones").symlink_to("/Applications")

    destino = RAIZ / "dist" / f"{NOMBRE}-macos.dmg"
    print(f"\nCreando {destino.name}…")
    subprocess.run(["hdiutil", "create", "-volname", NOMBRE, "-srcfolder", str(preparacion),
                    "-ov", "-format", "UDZO", str(destino)],
                   check=True)
    return destino


def comprimir(carpeta: Path) -> Path:
    destino = RAIZ / "dist" / f"{NOMBRE}-windows.zip"
    print(f"\nComprimiendo en {destino.name}…")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zip_:
        for archivo in sorted(carpeta.rglob("*")):
            if archivo.is_file():
                zip_.write(archivo, Path(NOMBRE) / archivo.relative_to(carpeta))
    return destino


def escribir_instrucciones(carpeta: Path, mac: RequisitosMac | None = None) -> None:
    """Un LÉEME para quien reciba el programa sin más contexto. La cuenta y
    las dudas son iguales en los dos sistemas; abrirlo, dónde están los datos
    y cómo se actualiza, no. Sin requisitos del Mac, es el de Windows."""
    if mac is not None:
        sistema = "el Mac"
        abrirlo = (
            "Abre ContaXcell-macos.dmg y arrastra ContaXcell encima de la\n"
            "carpeta Aplicaciones. Luego ábrelo desde Aplicaciones o desde\n"
            "el Launchpad, como cualquier otro.\n\n"
            "La primera vez, el Mac dirá que no puede comprobar que esté libre\n"
            "de software malicioso. Es normal: significa que no lo ha revisado\n"
            "Apple, que cobra por hacerlo, no que tenga nada malo. Pulsa\n"
            "«Hecho» (no lo mandes a la papelera), ve a «Ajustes del Sistema →\n"
            "Privacidad y seguridad», baja hasta donde dice que se ha bloqueado\n"
            "ContaXcell y pulsa «Abrir igualmente». Solo hay que hacerlo la\n"
            "primera vez.\n\n"
            f"{_en_que_mac(mac)}\n\n\n")
        datos = ("Se guardan en tu carpeta de usuario (Librería → Application\n"
                 "Support → ContaXcell), no dentro de la aplicación. El menú\n")
        actualizarlo = (
            "Abre el .dmg nuevo, arrastra ContaXcell a Aplicaciones y elige\n"
            "«Reemplazar». Como los datos no viven dentro de la aplicación,\n"
            "no se pierde nada.\n\n\n")
    else:
        sistema = "Windows"
        abrirlo = (
            "Doble clic en ContaXcell.exe\n\n"
            "La primera vez, Windows puede avisar de que no reconoce el programa.\n"
            "Es normal: significa que no está firmado por una empresa registrada,\n"
            "no que tenga nada malo. Pulsa «Más información» y luego\n"
            "«Ejecutar de todas formas».\n\n"
            "No muevas ni borres la carpeta «recursos-internos»: el programa\n"
            "la necesita para funcionar. Si quieres un acceso directo en el\n"
            "escritorio, haz clic derecho en ContaXcell.exe y elige\n"
            "«Enviar a» → «Escritorio (crear acceso directo)».\n\n\n")
        datos = ("Se guardan en tu carpeta de usuario (%APPDATA%\\ContaXcell), no\n"
                 "aquí dentro. El menú ")
        actualizarlo = (
            "Se actualiza solo, en cuanto tu cuenta esté aceptada. Al abrirlo\n"
            "con internet, si hay una versión nueva te pregunta si quieres\n"
            "ponerla: se cierra un momento y se\n"
            "vuelve a abrir. También puedes mirarlo en «Ayuda → Buscar\n"
            "actualizaciones…». Solo instala lo que viene firmado por quien\n"
            "administra ContaXcell. Tus datos no viven aquí dentro, así que\n"
            "no se tocan.\n\n\n")

    (carpeta / "LÉEME.txt").write_text(
        "ContaXcell\n"
        "==========\n\n"
        f"Contabilidad personal para {sistema}: ingresos, gastos e inversión,\n"
        "con la cartera, las deudas y los recibos que se repiten solos.\n\n\n"
        "ABRIRLO\n"
        "-------\n\n"
        f"{abrirlo}"
        "LA CUENTA\n"
        "---------\n\n"
        "Lo primero que pide el programa es un usuario y una contraseña.\n"
        "La cuenta sirve para que tu contabilidad se guarde también en el\n"
        "servidor y puedas abrirla en otro ordenador: apuntas un gasto en\n"
        "el portátil y lo tienes en el de casa.\n\n"
        "Si todavía no tienes, pulsa «Crear cuenta». Puede que te pida un\n"
        "código de invitación: el servidor no está abierto a cualquiera,\n"
        "así que pídeselo a quien te haya pasado el programa.\n\n"
        "Apunta la contraseña donde no se te pierda. No hay correo de\n"
        "recuperación: si la olvidas, esa cuenta no se abre. Y cambiarla\n"
        "cierra la sesión en los demás ordenadores, que es justo lo que\n"
        "hace falta si alguna vez crees que alguien la sabe.\n\n"
        "Si sale que no se ha podido hablar con el servidor, casi nunca es\n"
        "culpa tuya: suele estar apagado o haber cambiado de dirección.\n"
        "Avisa a quien te pasó el programa. A partir de la segunda vez\n"
        "aparece además «Seguir sin conexión», que te deja trabajar con lo\n"
        "que ya tienes en este ordenador; lo apuntado se sube solo cuando\n"
        "el servidor vuelva.\n\n\n"
        "TUS DATOS\n"
        "---------\n\n"
        f"{datos}«Archivo → Abrir la carpeta de mis datos» te\n"
        "la abre, y ahí mismo tienes «Guardar copia de seguridad» y\n"
        "«Restaurar una copia…».\n\n"
        "Con la cuenta abierta, cada cambio sube además una copia al\n"
        "servidor. A esa copia se llega con tu usuario y tu contraseña, y\n"
        "«Ayuda → Acerca de ContaXcell» te dice en todo momento dónde están\n"
        "tus datos y a dónde van.\n\n\n"
        "ACTUALIZARLO\n"
        "------------\n\n"
        f"{actualizarlo}"
        "DUDAS\n"
        "-----\n\n"
        "Pregunta a quien te lo haya pasado. Lo han escrito\n"
        "Cáceres García, Ricardo y Rodríguez Martín, Pablo.\n",
        encoding="utf-8")


def _en_que_mac(requisitos: RequisitosMac) -> str:
    version = requisitos.macos.removesuffix(".0")
    if requisitos.procesadores >= {"arm64", "x86_64"}:
        procesador = "Vale para los Mac con chip de Apple\ny para los de Intel."
    elif "arm64" in requisitos.procesadores:
        procesador = ("Solo vale para los Mac\ncon chip de Apple (M1 o posterior), "
                      "no para los antiguos\ncon procesador Intel.")
    else:
        procesador = ("Está hecho para los Mac\ncon procesador Intel; en los de chip "
                      "de Apple funciona a\ntravés de Rosetta.")
    return f"Hace falta macOS {version} o posterior. {procesador}"


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--sin-zip", action="store_true",
                            help="no preparar el .zip (o el .dmg en el Mac) al terminar")
    analizador.add_argument("--con-consola", action="store_true",
                            help="deja una ventana de consola visible, para ver errores")
    argumentos = analizador.parse_args()

    if not comprobar_pyinstaller():
        return 1
    if not comprobar_env():
        return 1

    preparar_icono()
    limpiar()
    carpeta = construir(argumentos.con_consola)

    if not carpeta.exists():
        print("Algo ha ido mal: no se ha creado la carpeta de salida.")
        return 1

    # El LÉEME de la .app va al lado y no dentro: cualquier archivo nuevo ahí
    # dentro rompe la firma, y con la firma rota el Mac no la abre.
    es_app = carpeta.suffix == ".app"
    if es_app:
        requisitos = requisitos_mac(carpeta)
        completar_info(carpeta, requisitos)
        escribir_instrucciones(carpeta.parent, requisitos)
        print(f"\nPide macOS {requisitos.macos} o posterior, en: "
              f"{', '.join(sorted(requisitos.procesadores))}")
    elif not ES_MAC:
        escribir_instrucciones(carpeta)
    # Sin contar los enlaces: la .app los tiene por dentro y se contarían dos veces.
    tamano = sum(f.stat().st_size for f in carpeta.rglob("*")
                 if f.is_file() and not f.is_symlink())
    print(f"\nListo: {carpeta}  ({tamano / 1024 / 1024:.0f} MB)")

    if ES_MAC and not es_app:
        # Con consola no sale .app: es para buscar errores, no para repartir.
        print("Con --con-consola no se prepara el .dmg: ábrelo desde la terminal.")
    elif not argumentos.sin_zip:
        comprimido = crear_dmg(carpeta) if es_app else comprimir(carpeta)
        print(f"Para repartir: {comprimido}  "
              f"({comprimido.stat().st_size / 1024 / 1024:.0f} MB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
