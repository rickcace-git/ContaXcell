"""Abre la aplicación con datos de prueba, sin tocar los datos de verdad.

    python pruebas/ver.py                      abre con la carpeta de pruebas
    python pruebas/ver.py --excel libro.xlsx   arranca importando ese Excel
    python pruebas/ver.py --pestana resumen    empieza en esa pestaña
    python pruebas/ver.py --captura foto.png   hace una captura y se cierra

La última forma es la que se usa para revisar cómo queda cada pantalla sin
tener que abrirla a mano una por una.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from contaxcell import almacen, excel, ventana  # noqa: E402

CARPETA_PRUEBAS = Path(tempfile.gettempdir()) / "contaxcell-vista"


def main() -> int:
    analizador = argparse.ArgumentParser()
    analizador.add_argument("--excel", help="importa este .xlsx al arrancar")
    analizador.add_argument("--pestana", default="apuntar")
    analizador.add_argument("--captura", help="guarda una imagen y cierra")
    analizador.add_argument("--espera", type=int, default=1200,
                            help="milisegundos antes de la captura")
    analizador.add_argument("--tema", choices=("auto", "claro", "oscuro"))
    argumentos = analizador.parse_args()

    CARPETA_PRUEBAS.mkdir(parents=True, exist_ok=True)
    if argumentos.excel:
        libro, _ = excel.importar(argumentos.excel)
        (CARPETA_PRUEBAS / almacen.NOMBRE_ARCHIVO).write_text(
            json.dumps(libro.a_json(), indent=2, ensure_ascii=False), encoding="utf-8")

    almacen.carpeta_de_datos = lambda: CARPETA_PRUEBAS

    app = ventana.Aplicacion()
    if argumentos.tema:
        app.poner_tema(argumentos.tema)
    app.ir_a(argumentos.pestana)

    if argumentos.captura:
        app.after(argumentos.espera, lambda: _capturar(app, Path(argumentos.captura)))
    app.mainloop()
    return 0


def _capturar(app, destino: Path) -> None:
    """Fotografía la ventana usando las funciones de Windows.

    Se recorta a la ventana en vez de a la pantalla entera para que la imagen
    sirva aunque haya otras cosas abiertas por encima.
    """
    # Sin esto, cualquier ventana que el usuario tuviera abierta sale encima.
    app.attributes("-topmost", True)
    app.lift()
    app.focus_force()
    app.update_idletasks()
    app.update()
    destino.parent.mkdir(parents=True, exist_ok=True)

    try:
        x = app.winfo_rootx()
        y = app.winfo_rooty()
        ancho = app.winfo_width()
        alto = app.winfo_height()
        _copiar_pantalla(destino, x, y, ancho, alto)
        print(f"captura guardada en {destino}")
    except Exception as error:  # noqa: BLE001
        print(f"no se ha podido capturar: {error}")
    finally:
        app.destroy()


def _copiar_pantalla(destino: Path, x: int, y: int, ancho: int, alto: int) -> None:
    import subprocess
    guion = f"""
Add-Type -AssemblyName System.Drawing
$mapa = New-Object System.Drawing.Bitmap({ancho}, {alto})
$lienzo = [System.Drawing.Graphics]::FromImage($mapa)
$lienzo.CopyFromScreen({x}, {y}, 0, 0, $mapa.Size)
$mapa.Save('{destino.as_posix()}', [System.Drawing.Imaging.ImageFormat]::Png)
$lienzo.Dispose(); $mapa.Dispose()
"""
    subprocess.run(["powershell", "-NoProfile", "-Command", guion],
                   check=True, capture_output=True)


if __name__ == "__main__":
    raise SystemExit(main())
