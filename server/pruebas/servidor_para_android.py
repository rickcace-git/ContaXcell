"""Un servidor de verdad, en local, para la prueba de conexión de la app Android.

Arranca la misma API que en producción, pero con SQLite en memoria y un
secreto fijo, y la deja con una cuenta ya rellena con una contabilidad
hecha por el escritorio (sus mismas clases, su mismo `a_json`). Así la
prueba de Android comprueba lo que pasa en el móvil: entrar y descargar lo
que subió el ordenador. Lo usa `.github/workflows/android.yml`.

    python server/pruebas/servidor_para_android.py 8765

Cuando está listo escribe «listo» y se queda sirviendo hasta que lo maten.
"""

from __future__ import annotations

import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "server"))
sys.path.insert(0, str(RAIZ / "escritorio"))

import uvicorn  # noqa: E402

from contaserver import almacen, aplicacion  # noqa: E402
from contaxcell.modelo import (INVERSION, Activo, AportacionGratis, Categoria,  # noqa: E402
                               Libro, Movimiento, Periodico, Valoracion)

USUARIO = "escritorio"
CONTRASENA = "contrasena-de-prueba"


def libro_del_escritorio() -> dict:
    """Una contabilidad pequeña pero con de todo, como la guarda el escritorio."""
    libro = Libro.vacio()
    libro.categorias.append(Categoria("Fondos", INVERSION))
    gasto = next(c.nombre for c in libro.categorias if c.tipo != INVERSION)
    libro.activos.append(Activo("MSCI World", aportacion_inicial=1000, titulos_iniciales=10,
                                valor_mercado=1500, ultima_valoracion="2026-09-01"))
    libro.movimientos += [
        Movimiento("2026-08-05", "Compra", "Fondos", 100, activo="MSCI World", titulos=0.9),
        Movimiento("2026-08-10", "Mercadona", gasto, 45.3),
    ]
    libro.aportaciones_gratis.append(
        AportacionGratis("2026-08-12", "MSCI World", "Cashback", 5, titulos=0.04))
    libro.historico.append(Valoracion("2026-08-31", 1480))
    libro.periodicos.append(Periodico("Alquiler", gasto, 700, desde="2026-01-01"))
    return libro.a_json()


def _pedir(url: str, metodo: str, cuerpo: dict, ficha: str = "") -> dict:
    cabeceras = {"Content-Type": "application/json"}
    if ficha:
        cabeceras["Authorization"] = f"Bearer {ficha}"
    peticion = urllib.request.Request(url, data=json.dumps(cuerpo).encode(), method=metodo,
                                      headers=cabeceras)
    with urllib.request.urlopen(peticion, timeout=10) as respuesta:
        return json.load(respuesta)


def main() -> None:
    puerto = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    app = aplicacion.crear_aplicacion(almacen=almacen.AlmacenSQLite(), secreto=b"s" * 48,
                                      codigo_registro="", cliente_precios=None)
    servidor = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=puerto,
                                             log_level="warning"))
    hilo = threading.Thread(target=servidor.run, daemon=True)
    hilo.start()
    while not servidor.started:
        time.sleep(0.05)

    base = f"http://127.0.0.1:{puerto}"
    ficha = _pedir(f"{base}/api/cuentas/registro", "POST",
                   {"usuario": USUARIO, "contrasena": CONTRASENA})["token"]
    _pedir(f"{base}/api/libro", "PUT", {"revision_base": 0, "libro": libro_del_escritorio()}, ficha)
    print("listo", flush=True)
    hilo.join()


if __name__ == "__main__":
    main()
