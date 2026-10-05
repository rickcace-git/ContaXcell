"""Quién tiene cuenta en el servidor y quién lo usa.

Se mira desde la propia máquina, entrando por ssh:

    ./usuarios                                      (en la carpeta server/)
    docker compose exec api python -m contaserver.usuarios   (lo mismo, a mano)

No hay ruta en la API para esto, y es a propósito: una puerta menos que
guardar en Internet. Solo lo ve quien puede entrar en la máquina con la llave.

Tampoco enseña nada de dentro de los libros: cuándo y cuánto, nunca qué. Las
cuentas de cada uno son suyas.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone

from . import almacen as modulo_almacen

# Quien ha usado el servidor en estos días cuenta como «activo».
DIAS_ACTIVO = 7


def _zona():
    """La hora de España. Si la máquina no trae las zonas horarias, UTC."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo("Europe/Madrid")
    except Exception:
        return timezone.utc


ZONA = _zona()


def cuando(momento: datetime | None, ahora: datetime) -> str:
    """«hoy 09:41», «ayer 22:10», «hace 3 días» o la fecha, si es de lejos."""
    if momento is None:
        return "nunca"
    local = momento.astimezone(ZONA)
    dias = (ahora.astimezone(ZONA).date() - local.date()).days
    if dias <= 0:
        return f"hoy {local:%H:%M}"
    if dias == 1:
        return f"ayer {local:%H:%M}"
    if dias < 30:
        return f"hace {dias} días"
    return f"{local:%Y-%m-%d}"


def tamano(octetos: int) -> str:
    """Los bytes del libro, en algo que se lea de un vistazo."""
    if octetos <= 0:
        return "—"
    if octetos < 1024:
        return f"{octetos} B"
    if octetos < 1024 * 1024:
        return f"{round(octetos / 1024)} KB"
    return f"{octetos / (1024 * 1024):.1f} MB".replace(".", ",")


def informe(filas: list[dict], ahora: datetime) -> str:
    """La tabla entera, lista para imprimir."""
    if not filas:
        return "Todavía no hay nadie registrado."

    total = len(filas)
    activos = sum(
        1 for f in filas
        if f["ultimo_uso"] and ahora - f["ultimo_uso"] < timedelta(days=DIAS_ACTIVO)
    )
    cabecera = (
        f"{total} usuario{'s' if total != 1 else ''} "
        f"registrado{'s' if total != 1 else ''} · "
        f"{activos} activo{'s' if activos != 1 else ''} "
        f"en los últimos {DIAS_ACTIVO} días"
    )

    titulos = ("USUARIO", "CREADO", "ÚLTIMO USO", "SUBIDAS", "LIBRO")
    renglones = [
        (
            f["usuario"],
            f["creado"].astimezone(ZONA).strftime("%Y-%m-%d") if f["creado"] else "—",
            cuando(f["ultimo_uso"], ahora),
            str(f["subidas"]),
            tamano(f["tamano"]),
        )
        for f in filas
    ]
    anchos = [max(len(r[i]) for r in [titulos, *renglones]) for i in range(len(titulos))]
    # Los números, pegados a la derecha; el texto, a la izquierda.
    a_la_derecha = {3, 4}

    def linea(valores) -> str:
        return "   ".join(
            v.rjust(anchos[i]) if i in a_la_derecha else v.ljust(anchos[i])
            for i, v in enumerate(valores)
        ).rstrip()

    return "\n".join([
        cabecera,
        "",
        linea(titulos),
        *(linea(r) for r in renglones),
        "",
        "SUBIDAS: las veces que ha guardado su libro en el servidor.",
    ])


def main() -> int:
    url = os.environ.get("CONTAXCELL_BASE_DATOS", "").strip()
    if not url:
        # Sin base de datos no hay a quién preguntar: un SQLite en memoria
        # diría «nadie registrado», que sería mentira.
        print("No sé dónde está la base de datos (falta CONTAXCELL_BASE_DATOS).\n"
              "Lánzalo dentro del servidor: docker compose exec api "
              "python -m contaserver.usuarios", file=sys.stderr)
        return 1
    almacen = modulo_almacen.AlmacenPostgres(url)
    print(informe(almacen.resumen_usuarios(), datetime.now(timezone.utc)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
