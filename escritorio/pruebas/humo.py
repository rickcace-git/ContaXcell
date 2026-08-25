"""Arranca la ventana de verdad, la pasea por todas las pestañas y la cierra.

No comprueba que se vea bonito: comprueba que no revienta. Es lo que se lanza
después de tocar la interfaz, porque los errores de tkinter no aparecen hasta
que el widget se construye o se dibuja.

    python pruebas/humo.py [--datos ruta.json] [--captura carpeta]
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

# Las pruebas no tienen cuenta ni servidor: la aplicación a pelo, todo local.
os.environ["CONTAXCELL_SIN_CUENTA"] = "1"

from contaxcell import almacen, ventana  # noqa: E402


def main() -> int:
    analizador = argparse.ArgumentParser()
    analizador.add_argument("--datos", help="JSON con el que arrancar")
    analizador.add_argument("--espera", type=int, default=350,
                            help="milisegundos en cada pestaña")
    argumentos = analizador.parse_args()

    # Nunca tocamos los datos reales del usuario al hacer pruebas.
    carpeta = Path(tempfile.mkdtemp(prefix="contaxcell-humo-"))
    if argumentos.datos:
        destino = carpeta / almacen.NOMBRE_ARCHIVO
        destino.write_text(Path(argumentos.datos).read_text(encoding="utf-8"),
                           encoding="utf-8")
    almacen.carpeta_de_datos = lambda: carpeta

    fallos: list[str] = []
    app = ventana.Aplicacion()

    claves = list(app._claves)
    paso = {"indice": 0}

    def siguiente():
        if paso["indice"] >= len(claves):
            app.after(argumentos.espera, app.destroy)
            return
        clave = claves[paso["indice"]]
        paso["indice"] += 1
        try:
            app.ir_a(clave)
            app.update_idletasks()
            app.update()
            print(f"  pestaña «{clave}» dibujada")
        except Exception:
            fallos.append(f"pestaña {clave}:\n{traceback.format_exc()}")
        app.after(argumentos.espera, siguiente)

    def al_error(_tipo, valor, rastro):
        fallos.append("".join(traceback.format_exception(_tipo, valor, rastro)))

    app.report_callback_exception = al_error
    app.after(argumentos.espera, siguiente)

    try:
        app.mainloop()
    except Exception:
        fallos.append(traceback.format_exc())

    if fallos:
        print("\nFALLOS:")
        for fallo in fallos:
            print(fallo)
        return 1
    print("\nHUMO OK: la ventana arranca y todas las pestañas se dibujan.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
