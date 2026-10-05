"""Quién tiene cuenta en el servidor y quién lo usa.

Se mira desde la propia máquina, entrando por ssh:

    ./usuarios                                      (en la carpeta server/)
    docker compose exec api python -m contaserver.usuarios   (lo mismo, a mano)

Y desde aquí se veta a alguien, o se le quita el veto:

    ./usuarios vetar NOMBRE        no puede entrar ni sincronizar, al momento
    ./usuarios readmitir NOMBRE    vuelve a poder, con su libro como estaba

Vetar no borra nada: su libro se queda en el servidor tal cual, y en su
ordenador sigue teniendo su contabilidad (es suya). Lo que pierde es la
cuenta: ni sincronizar, ni otro aparato, ni cotizaciones.

No hay ruta en la API para esto, y es a propósito: una puerta menos que
guardar en Internet. Solo lo ve quien puede entrar en la máquina con la llave.

Tampoco enseña nada de dentro de los libros: cuándo y cuánto, nunca qué. Las
cuentas de cada uno son suyas.
"""

from __future__ import annotations

import os
import sys
import unicodedata
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
    vetados = sum(1 for f in filas if f.get("vetado"))
    cabecera = (
        f"{total} usuario{'s' if total != 1 else ''} "
        f"registrado{'s' if total != 1 else ''} · "
        f"{activos} activo{'s' if activos != 1 else ''} "
        f"en los últimos {DIAS_ACTIVO} días"
    )
    if vetados:
        cabecera += f" · {vetados} vetado{'s' if vetados != 1 else ''}"

    titulos = ("USUARIO", "CREADO", "ÚLTIMO USO", "SUBIDAS", "LIBRO")
    renglones = [
        (
            f["usuario"] + ("  (VETADO)" if f.get("vetado") else ""),
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


def nombre_normalizado(nombre: str) -> str:
    """El nombre como lo guarda el servidor: igual que
    `aplicacion._normalizar_usuario`, para que «Ana» encuentre a «ana»."""
    return unicodedata.normalize("NFC", nombre).casefold().strip()


USO = ("Uso:  ./usuarios                    la tabla de usuarios\n"
       "      ./usuarios vetar NOMBRE       que no pueda entrar ni sincronizar\n"
       "      ./usuarios readmitir NOMBRE   quitarle el veto")


def ejecutar(almacen, argumentos: list[str], ahora: datetime) -> tuple[int, str]:
    """Hace lo pedido y devuelve (código de salida, lo que hay que decir).
    Separado de `main` para poder probarlo sin Postgres."""
    if not argumentos:
        return 0, informe(almacen.resumen_usuarios(), ahora)
    orden = argumentos[0]
    if orden not in ("vetar", "readmitir") or len(argumentos) != 2:
        return 2, USO
    nombre = nombre_normalizado(argumentos[1])
    if not almacen.vetar(nombre, orden == "vetar"):
        return 1, f"No hay ningún usuario «{nombre}». Mira los nombres con ./usuarios"
    if orden == "vetar":
        return 0, (f"«{nombre}» queda vetado: ya no puede entrar ni sincronizar.\n"
                   f"Su libro sigue guardado. Para deshacerlo: ./usuarios readmitir {nombre}")
    return 0, f"«{nombre}» vuelve a poder entrar. Tendrá que poner su contraseña otra vez."


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
    codigo, texto = ejecutar(almacen, sys.argv[1:], datetime.now(timezone.utc))
    print(texto, file=sys.stderr if codigo else sys.stdout)
    return codigo


if __name__ == "__main__":
    sys.exit(main())
