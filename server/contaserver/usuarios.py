"""Quién tiene cuenta en el servidor y quién lo usa.

Se mira desde la propia máquina, entrando por ssh:

    ./usuarios                                      (en la carpeta server/)
    docker compose exec api python -m contaserver.usuarios   (lo mismo, a mano)

Si el servidor acepta las cuentas a mano (CONTAXCELL_ACEPTAR_CUENTAS=1), las
nuevas salen las primeras, marcadas «EN ESPERA», y se deciden aquí:

    ./usuarios aceptar NOMBRE      ya puede sincronizar; lo suyo se sube solo
    ./usuarios rechazar NOMBRE     se borra la cuenta en espera

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
    esperando = sum(1 for f in filas if f.get("en_espera"))
    cabecera = (
        f"{total} usuario{'s' if total != 1 else ''} "
        f"registrado{'s' if total != 1 else ''} · "
        f"{activos} activo{'s' if activos != 1 else ''} "
        f"en los últimos {DIAS_ACTIVO} días"
    )
    if esperando:
        cabecera += f" · {esperando} en espera"
    if vetados:
        cabecera += f" · {vetados} vetado{'s' if vetados != 1 else ''}"

    titulos = ("USUARIO", "CREADO", "ÚLTIMO USO", "SUBIDAS", "LIBRO", "CONDICIONES", "CORREO")
    renglones = [
        (
            f["usuario"] + ("  (EN ESPERA)" if f.get("en_espera") else "")
            + ("  (VETADO)" if f.get("vetado") else ""),
            f["creado"].astimezone(ZONA).strftime("%Y-%m-%d") if f["creado"] else "—",
            cuando(f["ultimo_uso"], ahora),
            str(f["subidas"]),
            tamano(f["tamano"]),
            # Si aceptó las condiciones de uso al crearla. Las cuentas de
            # antes de haberlas, o hechas con un programa viejo, dicen «no».
            "aceptadas" if f.get("condiciones") else "no",
            # Las cuentas de antes de pedir el correo no lo tienen.
            f.get("correo") or "—",
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
        *(["EN ESPERA: ./usuarios aceptar NOMBRE  o  ./usuarios rechazar NOMBRE"]
          if esperando else []),
    ])


def nombre_normalizado(nombre: str) -> str:
    """El nombre como lo guarda el servidor: igual que
    `aplicacion._normalizar_usuario`, para que «Ana» encuentre a «ana»."""
    return unicodedata.normalize("NFC", nombre).casefold().strip()


USO = ("Uso:  ./usuarios                    la tabla de usuarios\n"
       "      ./usuarios aceptar NOMBRE     dejar entrar a una cuenta en espera\n"
       "      ./usuarios rechazar NOMBRE    borrar una cuenta en espera\n"
       "      ./usuarios rechazar-todas     borrar de golpe todas las que esperan\n"
       "      ./usuarios vetar NOMBRE       que no pueda entrar ni sincronizar\n"
       "      ./usuarios readmitir NOMBRE   quitarle el veto\n"
       "      ./usuarios ayuda              esto mismo")


def ejecutar(almacen, argumentos: list[str], ahora: datetime,
             preguntar=input) -> tuple[int, str]:
    """Hace lo pedido y devuelve (código de salida, lo que hay que decir).
    Separado de `main` para poder probarlo sin Postgres (y sin teclado:
    `preguntar` es quien contesta las confirmaciones)."""
    if not argumentos:
        return 0, informe(almacen.resumen_usuarios(), ahora)
    orden = argumentos[0]
    if orden in ("ayuda", "-h", "--help"):
        return 0, USO + "\n\nO, más fácil, con números: menu"
    if orden == "rechazar-todas" and len(argumentos) == 1:
        return _rechazar_todas(almacen, preguntar)
    if orden not in ("aceptar", "rechazar", "vetar", "readmitir") or len(argumentos) != 2:
        return 2, USO
    nombre = nombre_normalizado(argumentos[1])
    if orden in ("aceptar", "rechazar"):
        return _decidir(almacen, orden, nombre)
    if not almacen.vetar(nombre, orden == "vetar"):
        return 1, f"No hay ningún usuario «{nombre}». Mira los nombres con ./usuarios"
    if orden == "vetar":
        return 0, (f"«{nombre}» queda vetado: ya no puede entrar ni sincronizar.\n"
                   f"Su libro sigue guardado. Para deshacerlo: ./usuarios readmitir {nombre}")
    return 0, f"«{nombre}» vuelve a poder entrar. Tendrá que poner su contraseña otra vez."


def _rechazar_todas(almacen, preguntar) -> tuple[int, str]:
    """Para cuando alguien se ha puesto a crear cuentas basura: borra todas
    las que esperan, de una vez, enseñándolas antes y preguntando. Las
    aceptadas no se tocan, que `rechazar` no puede con ellas."""
    esperando = [f for f in almacen.resumen_usuarios() if f["en_espera"]]
    if not esperando:
        return 0, "No hay ninguna cuenta en espera."
    lista = "\n".join(f"  {f['usuario']}  {f.get('correo') or ''}".rstrip() for f in esperando)
    print(f"Están en espera {len(esperando)}:\n{lista}\n")
    try:
        respuesta = preguntar("¿Borrarlas todas? Escribe «si» para seguir: ")
    except EOFError:
        respuesta = ""
    if respuesta.strip().lower() not in ("si", "sí"):
        return 1, "No se ha borrado nada."
    borradas = sum(1 for f in esperando if almacen.rechazar(f["usuario"]))
    return 0, (f"Borradas {borradas} cuentas en espera. Si siguen apareciendo, cambia el "
               "código de invitación (CONTAXCELL_CODIGO_REGISTRO en el .env).")


def _decidir(almacen, orden: str, nombre: str) -> tuple[int, str]:
    """Aceptar o rechazar una cuenta en espera."""
    fila = next((f for f in almacen.resumen_usuarios() if f["usuario"] == nombre), None)
    if fila is None:
        return 1, f"No hay ningún usuario «{nombre}». Mira los nombres con ./usuarios"
    if orden == "aceptar":
        if not fila["en_espera"]:
            return 0, f"«{nombre}» ya estaba aceptado."
        almacen.aceptar(nombre)
        return 0, (f"«{nombre}» aceptado: ya puede sincronizar. Lo que tenga en su "
                   "aparato se subirá solo la próxima vez que su app mire.")
    if not fila["en_espera"]:
        # Rechazar borra la cuenta: solo para las que nunca han guardado nada.
        return 1, (f"«{nombre}» ya está aceptado y no se rechaza, que eso borraría "
                   f"su cuenta. Para echarlo: ./usuarios vetar {nombre}")
    almacen.rechazar(nombre)
    return 0, (f"«{nombre}» rechazado: su cuenta en espera se ha borrado. Si vuelve "
               f"a crearla una y otra vez, mejor ./usuarios vetar {nombre}.")


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
