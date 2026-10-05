"""Publica una versión nueva de ContaXcell para que les llegue sola a todos.

    python publicar.py --crear-llave        una sola vez, la primera
    python publicar.py "Lo que trae de nuevo"

Lo segundo, paso a paso:

1. Comprueba que la versión de `contaxcell/ventana.py` (VERSION) es más nueva
   que la publicada. Si no, para: hay que subirla antes, o nadie la vería.
2. Fabrica el programa con empaquetar.py.
3. Escribe la nota (`version.json`: versión, archivo, tamaño y SHA-256 del
   zip) y la firma con tu llave.
4. Sube a /descargas/ del servidor el zip, la nota y su firma. El zip va
   también como ContaXcell-windows.zip, la descarga de siempre.

Al abrir el programa, cada uno ve «Hay una versión nueva… ¿Actualizar ahora?».

LA LLAVE DE FIRMAR es lo único delicado. Vive en tu carpeta de usuario
(~/.contaxcell/llave-actualizaciones.json), nunca en el repositorio ni en el
servidor, y es lo que impide que nadie más pueda colar una actualización.
Haz una copia (gestor de contraseñas, pendrive): si se pierde no se pueden
publicar más actualizaciones, y habría que repartir el programa a mano otra
vez con una llave nueva. Si alguien te la quita, lo mismo, y cuanto antes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, str(RAIZ))

from contaxcell import actualizar, firma  # noqa: E402

LLAVE_PRIVADA = Path.home() / ".contaxcell" / "llave-actualizaciones.json"
LLAVE_PUBLICA = RAIZ / "contaxcell" / "llave_publica.py"
ZIP = RAIZ / "dist" / "ContaXcell-windows.zip"
LLAVE_SSH = Path.home() / ".ssh" / "contaxcell.pem"


def crear_llave() -> int:
    if LLAVE_PRIVADA.exists():
        print(f"Ya hay una llave en {LLAVE_PRIVADA}. No la piso: si la cambias,\n"
              "los programas repartidos dejarán de aceptar tus actualizaciones.")
        return 1
    print("Generando la llave (unos segundos)…")
    llave = firma.generar_llave()
    LLAVE_PRIVADA.parent.mkdir(parents=True, exist_ok=True)
    LLAVE_PRIVADA.write_text(json.dumps({k: str(v) for k, v in llave.items()}), encoding="utf-8")
    escribir_publica(llave["n"], llave["e"])
    print(f"\nLlave privada: {LLAVE_PRIVADA}\n"
          "  HAZ UNA COPIA y no se la pases a nadie.\n"
          f"Llave pública: {LLAVE_PUBLICA.relative_to(RAIZ)} (esa sí va al repositorio)")
    return 0


def escribir_publica(n: int, e: int) -> None:
    trozos = [str(n)[i:i + 72] for i in range(0, len(str(n)), 72)]
    LLAVE_PUBLICA.write_text(
        '"""La mitad pública de la llave con la que se firman las actualizaciones.\n\n'
        "La escribe `python publicar.py --crear-llave`. Sirve para comprobar firmas,\n"
        "no para hacerlas: puede ir en el repositorio sin miedo. La privada vive\n"
        'solo en el ordenador de quien publica (ver publicar.py).\n"""\n\n'
        "LLAVE_PUBLICA = (\n    int(\n"
        + "".join(f'        "{t}"\n' for t in trozos)
        + f"    ),\n    {e},\n)\n",
        encoding="utf-8")


def leer_llave() -> dict:
    datos = json.loads(LLAVE_PRIVADA.read_text(encoding="utf-8"))
    return {k: int(v) for k, v in datos.items()}


def maquina_del_servidor() -> tuple[str, str]:
    from contaxcell.sincronia import servidor_de_fabrica
    servidor = servidor_de_fabrica()
    return servidor, urllib.parse.urlparse(servidor).hostname or ""


def publicar(notas: str, llave_ssh: Path) -> int:
    from contaxcell.ventana import VERSION

    if not LLAVE_PRIVADA.exists():
        print("Falta la llave de firmar. Créala una vez con:\n\n"
              "    python publicar.py --crear-llave\n")
        return 1
    llave = leer_llave()
    from contaxcell.llave_publica import LLAVE_PUBLICA as PUBLICA
    if (llave["n"], llave["e"]) != PUBLICA:
        print("La llave de firmar no es la que conoce el programa (llave_publica.py).\n"
              "Lo que publicaras no lo aceptaría nadie. Revisa cuál es la buena.")
        return 1

    servidor, maquina = maquina_del_servidor()
    print(f"Servidor: {servidor}\nVersión a publicar: {VERSION}")
    try:
        publicada = actualizar.buscar(servidor, "0")
    except actualizar.SinActualizaciones as error:
        print(f"No se ha podido preguntar al servidor ({error}).")
        return 1
    if publicada is not None and not actualizar.es_mas_nueva(VERSION, publicada.version):
        print(f"\nEn el servidor ya está la {publicada.version}. Sube VERSION en "
              "contaxcell/ventana.py (por ejemplo a la siguiente) y vuelve a lanzar esto.")
        return 1

    print("\nFabricando el programa…")
    if subprocess.run([sys.executable, str(RAIZ / "empaquetar.py")], cwd=RAIZ).returncode != 0:
        print("No se ha podido fabricar. Si dice «Acceso denegado», cierra el ContaXcell "
              "que tengas abierto desde dist/ y vuelve a probar.")
        return 1

    datos = ZIP.read_bytes()
    nombre = f"ContaXcell-windows-{VERSION}.zip"
    nota = json.dumps({
        "version": VERSION,
        "archivo": f"/descargas/{nombre}",
        "tamano": len(datos),
        "sha256": hashlib.sha256(datos).hexdigest(),
        "notas": notas.strip(),
    }, ensure_ascii=False, indent=2).encode("utf-8")
    salida = RAIZ / "dist" / "publicar"
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "version.json").write_bytes(nota)
    (salida / "version.json.firma").write_bytes(firma.firmar(nota, llave))

    print("\nSubiendo al servidor…")
    ssh = ["-i", str(llave_ssh), "-o", "BatchMode=yes"]
    destino = f"ubuntu@{maquina}"
    # Primero el zip; la nota y su firma, al final y de golpe (se suben con
    # otro nombre y se renombran juntas), para que nadie vea una nota que
    # apunte a un zip que aún no está.
    pasos = [
        ["scp", *ssh, str(ZIP), f"{destino}:server/descargas/{nombre}"],
        ["scp", *ssh, str(salida / "version.json"), f"{destino}:server/descargas/.version.json"],
        ["scp", *ssh, str(salida / "version.json.firma"), f"{destino}:server/descargas/.version.json.firma"],
        ["ssh", *ssh, destino,
         "cd server/descargas && cp " + nombre + " ContaXcell-windows.zip"
         " && mv .version.json.firma version.json.firma && mv .version.json version.json"],
    ]
    for paso in pasos:
        if subprocess.run(paso).returncode != 0:
            print("Ha fallado la subida. Lo de antes sigue publicado tal cual.")
            return 1

    comprobada = actualizar.buscar(servidor, "0")
    if comprobada is None or comprobada.version != VERSION:
        print("Subido, pero al volver a preguntar no sale la versión nueva. Revísalo.")
        return 1
    print(f"\nPublicada la {VERSION}. Les saldrá al abrir ContaXcell con internet.")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__,
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
    analizador.add_argument("notas", nargs="?", default="",
                            help="lo que trae de nuevo, en una frase (se enseña al preguntar)")
    analizador.add_argument("--crear-llave", action="store_true",
                            help="crea la llave de firmar (solo la primera vez)")
    analizador.add_argument("--llave-ssh", type=Path, default=LLAVE_SSH,
                            help=f"la llave .pem del servidor (por defecto {LLAVE_SSH})")
    argumentos = analizador.parse_args()
    if argumentos.crear_llave:
        return crear_llave()
    return publicar(argumentos.notas, argumentos.llave_ssh)


if __name__ == "__main__":
    raise SystemExit(main())
