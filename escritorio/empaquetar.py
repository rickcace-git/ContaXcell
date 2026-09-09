"""Convierte ContaXcell en un programa de Windows que se puede repartir.

    python empaquetar.py

Deja en `dist/` una carpeta con el .exe y todo lo que necesita, y un .zip de
esa carpeta listo para enviar.

Se empaqueta en carpeta y no en un único archivo (`--onefile`) a propósito. Un
.exe de un solo archivo se descomprime en una carpeta temporal cada vez que se
abre, que es exactamente lo que hace el software malicioso, y por eso los
antivirus lo marcan mucho más a menudo. La carpeta arranca antes y da bastantes
menos disgustos al mandársela a alguien.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
NOMBRE = "ContaXcell"
ICONO = RAIZ / "recursos" / "icono.ico"
PLANTILLA = RAIZ / "recursos" / "plantilla.xlsx"
# La dirección del servidor, que es distinta en cada despliegue y no está en el
# repositorio. Va dentro del programa para que quien lo reciba no tenga que
# escribirla: sin ella, el ejecutable saldría apuntando a localhost, o sea, a
# ningún sitio útil para quien no seas tú.
ENV = RAIZ / ".env"

# openpyxl arrastra dependencias opcionales que no usamos. Fuera hacen la
# carpeta bastante más pequeña y el arranque más rápido.
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
    if ICONO.exists():
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
        # Sin ventana negra de fondo: es una aplicación con interfaz.
        "--console" if consola else "--windowed",
        "--name", NOMBRE,
        "--icon", str(ICONO),
        # El icono también va dentro, para la ventana y la barra de tareas,
        # y la plantilla de Excel, que es lo que rellena la exportación.
        "--add-data", f"{ICONO}{';' if sys.platform == 'win32' else ':'}recursos",
        "--add-data", f"{PLANTILLA}{';' if sys.platform == 'win32' else ':'}recursos",
        # Y la dirección del servidor, que si no el programa no sabría con
        # quién hablar en el ordenador de quien lo reciba.
        "--add-data", f"{ENV}{';' if sys.platform == 'win32' else ':'}recursos",
        # Todo lo accesorio en una subcarpeta: así lo primero que se ve al
        # abrir la carpeta es el ejecutable y no cien archivos sueltos.
        "--contents-directory", "recursos-internos",
        str(RAIZ / "ejecutar.py"),
    ]
    for modulo in SOBRAN:
        orden += ["--exclude-module", modulo]

    print("Construyendo… esto tarda un par de minutos.\n")
    subprocess.run(orden, check=True, cwd=RAIZ)
    return RAIZ / "dist" / NOMBRE


def comprimir(carpeta: Path) -> Path:
    destino = RAIZ / "dist" / f"{NOMBRE}-windows.zip"
    print(f"\nComprimiendo en {destino.name}…")
    with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zip_:
        for archivo in sorted(carpeta.rglob("*")):
            if archivo.is_file():
                zip_.write(archivo, Path(NOMBRE) / archivo.relative_to(carpeta))
    return destino


def escribir_instrucciones(carpeta: Path) -> None:
    """Un LÉEME dentro de la carpeta, para quien la reciba sin más contexto."""
    (carpeta / "LÉEME.txt").write_text(
        "ContaXcell\n"
        "==========\n\n"
        "Contabilidad personal para Windows: ingresos, gastos e inversión,\n"
        "con la cartera, las deudas y los recibos que se repiten solos.\n\n\n"
        "ABRIRLO\n"
        "-------\n\n"
        "Doble clic en ContaXcell.exe\n\n"
        "La primera vez, Windows puede avisar de que no reconoce el programa.\n"
        "Es normal: significa que no está firmado por una empresa registrada,\n"
        "no que tenga nada malo. Pulsa «Más información» y luego\n"
        "«Ejecutar de todas formas».\n\n"
        "No muevas ni borres la carpeta «recursos-internos»: el programa\n"
        "la necesita para funcionar. Si quieres un acceso directo en el\n"
        "escritorio, haz clic derecho en ContaXcell.exe y elige\n"
        "«Enviar a» → «Escritorio (crear acceso directo)».\n\n\n"
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
        "Se guardan en tu carpeta de usuario (%APPDATA%\\ContaXcell), no\n"
        "aquí dentro. El menú «Archivo → Abrir la carpeta de mis datos» te\n"
        "la abre, y ahí mismo tienes «Guardar copia de seguridad» y\n"
        "«Restaurar una copia…».\n\n"
        "Con la cuenta abierta, cada cambio sube además una copia al\n"
        "servidor. A esa copia se llega con tu usuario y tu contraseña, y\n"
        "«Ayuda → Acerca de ContaXcell» te dice en todo momento dónde están\n"
        "tus datos y a dónde van.\n\n\n"
        "ACTUALIZARLO\n"
        "------------\n\n"
        "Descomprime la versión nueva y borra la carpeta vieja. Como los\n"
        "datos no viven aquí dentro, no se pierde nada.\n\n\n"
        "DUDAS\n"
        "-----\n\n"
        "Pregunta a quien te lo haya pasado. Lo han escrito\n"
        "Cáceres García, Ricardo y Rodríguez Martín, Pablo.\n",
        encoding="utf-8")


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__)
    analizador.add_argument("--sin-zip", action="store_true",
                            help="no comprimir al terminar")
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

    escribir_instrucciones(carpeta)
    tamano = sum(f.stat().st_size for f in carpeta.rglob("*") if f.is_file())
    print(f"\nListo: {carpeta}  ({tamano / 1024 / 1024:.0f} MB)")

    if not argumentos.sin_zip:
        comprimido = comprimir(carpeta)
        print(f"Para repartir: {comprimido}  "
              f"({comprimido.stat().st_size / 1024 / 1024:.0f} MB)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
