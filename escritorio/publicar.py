"""Publica una versión nueva de ContaXcell para que les llegue sola a todos.

    python publicar.py --crear-llave        una sola vez, la primera
    python publicar.py "Lo que trae de nuevo"

Lo segundo, paso a paso:

1. Comprueba que la versión de `contaxcell/ventana.py` (VERSION) es más nueva
   que la publicada. Si no, para: hay que subirla antes, o nadie la vería.
2. Fabrica el programa con empaquetar.py.
3. Escribe la nota (`version.json`: versión, archivo, tamaño y SHA-256 del
   zip, más el historial de cambios de las últimas versiones y el enlace a
   GitHub con el código) y la firma con tu llave. El historial sale de los
   mensajes de git entre las marcas v1.1.4, v1.1.5… que deja cada
   publicación: así cada programa enseña justo lo que le falta, venga de la
   versión que venga. Por eso hay que tener todo guardado y subido antes.
4. Sube a server/actualizaciones/ de la máquina el zip, la nota y su firma,
   y marca el commit en git con la versión (v1.1.5) y la sube a GitHub.
   Eso lo reparte la API, y solo a las cuentas aceptadas y sin vetar. El zip
   va también a /descargas/ContaXcell-windows.zip, la descarga pública para
   instalarlo la primera vez.

Al abrir el programa, cada uno ve «Hay una versión nueva… ¿Actualizar ahora?».

    python publicar.py --tambien-viejas "…"

Lo mismo, y además deja la nota en /descargas/, el sitio público donde
miraban las versiones hasta la 1.1.2. Sirvió una vez, para que esas pasaran
a la que ya pregunta con cuenta. No hace falta volver a usarlo.

    python publicar.py --condiciones

Sube solo las condiciones de uso (server/textos/condiciones.md) al
servidor. Se ven al momento, sin reiniciar nada ni publicar versión.

    python publicar.py --android "Descargas/ContaXcell-android (6)/app-debug.apk" "lo nuevo"

Publica la app del móvil que ha compilado GitHub: la carpeta del artifact
trae, junto al APK, compilacion.json (su número y su commit). La firma, la
sube, la pone también en el QR de descarga y marca el commit en git
(android-48). Al abrir la app, a cada cuenta aceptada le sale «Hay una
versión nueva de la app» y, con un toque en «Instalar», queda puesta.

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
import re
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
CONDICIONES = RAIZ.parent / "server" / "textos" / "condiciones.md"
LLAVE_ANDROID = (RAIZ.parent / "android" / "app" / "src" / "main" / "java" / "com" / "contaxcell"
                 / "app" / "data" / "update" / "UpdateKey.kt")
# Cuántas versiones atrás guarda el historial de la nota.
VERSIONES_EN_HISTORIAL = 8
# Las últimas que solo saben leer «cambios» y no el historial. Para ellas,
# «cambios» lleva todo lo posterior, con la versión delante de cada cosa.
ULTIMA_SIN_HISTORIAL = "1.1.4"


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
    # La misma, para la app del móvil.
    trozos = [str(n)[i:i + 90] for i in range(0, len(str(n)), 90)]
    cuerpo = " +\n".join(f'        "{t}"' for t in trozos)
    LLAVE_ANDROID.write_text(
        "package com.contaxcell.app.data.update\n\n"
        "/**\n"
        " * La mitad pública de la llave con la que se firman las actualizaciones: la\n"
        " * misma que comprueba el programa del ordenador (escritorio/contaxcell/\n"
        " * llave_publica.py). La escribe `python publicar.py --crear-llave`; no se toca\n"
        " * a mano. Sirve para comprobar firmas, no para hacerlas.\n"
        " */\n"
        "internal object UpdateKey {\n"
        "    const val MODULUS: String =\n"
        f"{cuerpo}\n"
        f"    const val EXPONENT: Long = {e}L\n"
        "}\n",
        encoding="utf-8")


def leer_llave() -> dict:
    datos = json.loads(LLAVE_PRIVADA.read_text(encoding="utf-8"))
    return {k: int(v) for k, v in datos.items()}


def maquina_del_servidor() -> tuple[str, str]:
    from contaxcell.sincronia import servidor_de_fabrica
    servidor = servidor_de_fabrica()
    return servidor, urllib.parse.urlparse(servidor).hostname or ""


def nota_publicada(ssh: list[str], destino: str, carpeta: str = "actualizaciones",
                   nota: str = "version.json") -> tuple[bytes, bytes] | None:
    """La nota y la firma que hay ahora en el servidor, leídas por ssh (las
    de la API piden cuenta, y esto no tiene por qué ir con una). None si no
    hay ninguna todavía."""
    partes = []
    for nombre in (nota, nota + ".firma"):
        leido = subprocess.run(["ssh", *ssh, destino, f"cat server/{carpeta}/{nombre}"],
                               capture_output=True)
        if leido.returncode != 0:
            return None
        partes.append(leido.stdout)
    return partes[0], partes[1]


def version_de(nota: bytes) -> str:
    return str(json.loads(nota.decode("utf-8"))["version"])


def git(*argumentos: str) -> str:
    return subprocess.run(["git", *argumentos], cwd=RAIZ, capture_output=True,
                          text=True, encoding="utf-8").stdout


# Lo que no le interesa a quien lee los cambios: las firmas de coautoría.
LINEAS_QUE_SOBRAN = ("co-authored-by:", "signed-off-by:")
MAXIMO_CAMBIOS = 80


def desenvolver(lineas: list[str]) -> str:
    """Los mensajes de git van cortados a unos 72 caracteres; en la ventana
    se leen mejor como párrafos. Una línea en blanco separa párrafos y una
    que empieza por guion o punto es un elemento de lista: esas se respetan."""
    parrafos: list[str] = []
    seguir = False
    for linea in lineas:
        if not linea:
            seguir = False
            continue
        if seguir and not linea.startswith(("-", "•", "*")):
            parrafos[-1] += " " + linea
        else:
            parrafos.append(linea)
        seguir = True
    return "\n".join(parrafos)


def leer_cambios(salida_de_git: str) -> list[dict]:
    """De `git log --format=%s%x1f%b%x1e` a [{titulo, detalle}], del más
    nuevo al más viejo."""
    cambios = []
    for registro in salida_de_git.split("\x1e"):
        if "\x1f" not in registro:
            continue
        titulo, cuerpo = registro.split("\x1f", 1)
        lineas = [linea.strip() for linea in cuerpo.strip().splitlines()
                  if not linea.strip().lower().startswith(LINEAS_QUE_SOBRAN)]
        detalle = desenvolver(lineas)
        # «Versión 1.1.5» solo sube el número: no es un cambio que contar.
        if titulo.strip() and not re.fullmatch(r"Versi[oó]n \d+(\.\d+)*\.?", titulo.strip()):
            cambios.append({"titulo": titulo.strip(), "detalle": detalle[:2000]})
    return cambios[:MAXIMO_CAMBIOS]


def enlace_codigo(remoto: str, desde: str, hasta: str) -> str:
    """La página de GitHub que compara dos commits, o "" si no es GitHub."""
    remoto = remoto.strip()
    for prefijo in ("https://github.com/", "git@github.com:"):
        if remoto.startswith(prefijo) and desde and hasta:
            repositorio = remoto[len(prefijo):].removesuffix(".git").strip("/")
            return f"https://github.com/{repositorio}/compare/{desde[:12]}...{hasta[:12]}"
    return ""


def versiones_publicadas() -> list[tuple[str, str]]:
    """(versión, commit) de cada publicación, de la más vieja a la más nueva.
    Salen de las marcas v1.2.3 que pone `publicar` en git."""
    marcas = []
    for linea in git("tag", "-l", "v*", "--format=%(refname:short) %(objectname)").splitlines():
        nombre, _, commit = linea.partition(" ")
        if nombre[1:2].isdigit() and commit:
            # Una marca anotada apunta a sí misma: se pide el commit de verdad.
            marcas.append((nombre[1:], git("rev-list", "-n", "1", nombre).strip() or commit))
    return sorted(marcas, key=lambda m: actualizar.version_en_numeros(m[0]))


def cambios_entre(desde: str, hasta: str) -> list[dict]:
    return leer_cambios(git("log", f"{desde}..{hasta}", "--no-merges",
                            "--format=%s%x1f%b%x1e"))


def historial(version: str, cuantas: int | None = VERSIONES_EN_HISTORIAL) -> list[dict]:
    """Lo que trae cada una de las últimas versiones, la nueva la primera:
    [{version, fecha, desde, hasta, cambios}]. «desde» y «hasta» son los
    commits, para el enlace al código. Con `cuantas=None`, todas, y la
    primera de todas sale también, sin cambios (no hay nada antes)."""
    anteriores = [m for m in versiones_publicadas() if actualizar.es_mas_nueva(version, m[0])]
    if cuantas is not None:
        anteriores = anteriores[-cuantas:]
    puntos = anteriores + [(version, git("rev-parse", "HEAD").strip())]
    entradas = [{"version": v, "fecha": fecha_de(c), "desde": puntos[i - 1][1], "hasta": c,
                 "cambios": cambios_entre(puntos[i - 1][1], c)}
                for i, (v, c) in enumerate(puntos) if i > 0]
    if cuantas is None and puntos:
        primera, commit = puntos[0]
        entradas.insert(0, {"version": primera, "fecha": fecha_de(commit), "desde": "",
                            "hasta": commit, "cambios": []})
    return entradas[::-1]


def fecha_de(commit: str) -> str:
    """El día del commit, AAAA-MM-DD. El de HEAD es hoy: se publica ahora."""
    if commit == git("rev-parse", "HEAD").strip():
        import datetime
        return datetime.date.today().isoformat()
    return git("log", "-1", "--format=%cs", commit).strip()


HISTORIAL_EN_EL_PROGRAMA = RAIZ / "contaxcell" / "historial_versiones.py"


def escribir_historial(version: str) -> None:
    """Mete en el programa todas las versiones publicadas, para Ayuda ▸
    Historial de versiones. No va a git: se escribe cada vez que se publica."""
    entradas = [{k: e[k] for k in ("version", "fecha", "cambios")}
                for e in historial(version, cuantas=None)]
    HISTORIAL_EN_EL_PROGRAMA.write_text(
        '"""Las versiones publicadas. Lo escribe publicar.py; no se toca a mano."""\n\n'
        f"HISTORIAL = {json.dumps(entradas, ensure_ascii=False, indent=1)}\n",
        encoding="utf-8")


def repositorio() -> str:
    """https://github.com/dueño/nombre, o "" si no es GitHub."""
    enlace = enlace_codigo(git("remote", "get-url", "origin"), "x", "x")
    return enlace.split("/compare/")[0] if enlace else ""


def para_las_de_antes(entradas: list[dict]) -> tuple[list[dict], str]:
    """«cambios» y «codigo» para los programas que no leen el historial (la
    1.1.3 y la 1.1.4): todo lo posterior a ellas, con la versión delante."""
    nuevas = [e for e in entradas if actualizar.es_mas_nueva(e["version"], ULTIMA_SIN_HISTORIAL)
              or e["version"] == ULTIMA_SIN_HISTORIAL]
    cambios = [{"titulo": f"{e['version']} · {c['titulo']}", "detalle": c["detalle"]}
               for e in nuevas for c in e["cambios"]][:MAXIMO_CAMBIOS]
    codigo = ""
    if nuevas:
        codigo = enlace_codigo(git("remote", "get-url", "origin"),
                               nuevas[-1]["desde"], nuevas[0]["hasta"])
    return cambios, codigo


def todo_guardado_y_subido() -> str:
    """"" si se puede publicar; si no, qué falta."""
    if git("status", "--porcelain", "--untracked-files=no").strip():
        return ("Hay cambios sin guardar en git. La lista de novedades sale de git, así que\n"
                "haz antes commit (con VERSION ya subida) y git push.")
    if git("rev-list", "@{u}..HEAD").strip():
        return ("Hay commits sin subir a GitHub, y el enlace al código no funcionaría.\n"
                "Haz antes git push.")
    return ""


def firmar_nota(version: str, datos: bytes, archivo: str, notas: str, llave: dict,
                entradas: list[dict] | None = None) -> tuple[bytes, bytes]:
    """La nota de una versión y su firma."""
    entradas = entradas or []
    cambios, codigo = para_las_de_antes(entradas)
    nota = json.dumps({
        "version": version,
        "archivo": archivo,
        "tamano": len(datos),
        "sha256": hashlib.sha256(datos).hexdigest(),
        "notas": notas.strip(),
        "historial": entradas,
        "repositorio": repositorio(),
        "cambios": cambios,
        "codigo": codigo,
    }, ensure_ascii=False, indent=2).encode("utf-8")
    return nota, firma.firmar(nota, llave)


def publicar(notas: str, llave_ssh: Path, tambien_viejas: bool = False) -> int:
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

    falta = todo_guardado_y_subido()
    if falta:
        print(falta)
        return 1

    servidor, maquina = maquina_del_servidor()
    print(f"Servidor: {servidor}\nVersión a publicar: {VERSION}")
    ssh = ["-i", str(llave_ssh), "-o", "BatchMode=yes"]
    destino = f"ubuntu@{maquina}"
    if subprocess.run(["ssh", *ssh, destino, "mkdir -p server/actualizaciones"]).returncode != 0:
        print(f"No se ha podido entrar en el servidor por ssh. ¿Está la llave en {llave_ssh}?")
        return 1
    publicada = nota_publicada(ssh, destino)
    if publicada is not None and not actualizar.es_mas_nueva(VERSION, version_de(publicada[0])):
        print(f"\nEn el servidor ya está la {version_de(publicada[0])}. Sube VERSION en "
              "contaxcell/ventana.py (por ejemplo a la siguiente) y vuelve a lanzar esto.")
        return 1
    entradas = historial(VERSION)
    for entrada in entradas:
        print(f"\nLa {entrada['version']} trae {len(entrada['cambios'])} cambios:")
        for cambio in entrada["cambios"]:
            print(f"  · {cambio['titulo']}")

    escribir_historial(VERSION)
    print("\nFabricando el programa…")
    if subprocess.run([sys.executable, str(RAIZ / "empaquetar.py")], cwd=RAIZ).returncode != 0:
        print("No se ha podido fabricar. Si dice «Acceso denegado», cierra el ContaXcell "
              "que tengas abierto desde dist/ y vuelve a probar.")
        return 1

    datos = ZIP.read_bytes()
    nombre = f"ContaXcell-windows-{VERSION}.zip"
    salida = RAIZ / "dist" / "publicar"
    salida.mkdir(parents=True, exist_ok=True)
    nota, firma_nota = firmar_nota(VERSION, datos, actualizar.RUTA_BASE + nombre, notas, llave,
                                   entradas)
    (salida / "version.json").write_bytes(nota)
    (salida / "version.json.firma").write_bytes(firma_nota)

    print("\nSubiendo al servidor…")
    # Primero el zip; la nota y su firma, al final y de golpe (se suben con
    # otro nombre y se renombran juntas), para que nadie vea una nota que
    # apunte a un zip que aún no está.
    pasos = [
        ["scp", *ssh, str(ZIP), f"{destino}:server/actualizaciones/{nombre}"],
        ["scp", *ssh, str(salida / "version.json"),
         f"{destino}:server/actualizaciones/.version.json"],
        ["scp", *ssh, str(salida / "version.json.firma"),
         f"{destino}:server/actualizaciones/.version.json.firma"],
        ["ssh", *ssh, destino,
         f"cd server && cp actualizaciones/{nombre} descargas/ContaXcell-windows.zip"
         " && cd actualizaciones && mv .version.json.firma version.json.firma"
         " && mv .version.json version.json"],
    ]
    if tambien_viejas:
        # Las de antes (hasta la 1.1.2) miran en /descargas/, sin cuenta, y
        # solo aceptan un zip de ahí.
        vieja, firma_vieja = firmar_nota(VERSION, datos, f"/descargas/{nombre}", notas, llave,
                                         entradas)
        (salida / "vieja.json").write_bytes(vieja)
        (salida / "vieja.json.firma").write_bytes(firma_vieja)
        pasos += [
            ["scp", *ssh, str(salida / "vieja.json"), f"{destino}:server/descargas/.version.json"],
            ["scp", *ssh, str(salida / "vieja.json.firma"),
             f"{destino}:server/descargas/.version.json.firma"],
            ["ssh", *ssh, destino,
             f"cd server/descargas && cp ../actualizaciones/{nombre} {nombre}"
             " && mv .version.json.firma version.json.firma && mv .version.json version.json"],
        ]
    for paso in pasos:
        if subprocess.run(paso).returncode != 0:
            print("Ha fallado la subida. Lo de antes sigue publicado tal cual.")
            return 1

    comprobada = nota_publicada(ssh, destino)
    if (comprobada is None or comprobada[0] != nota
            or not firma.comprobar(comprobada[0], comprobada[1], PUBLICA)):
        print("Subido, pero al volver a mirar no sale la versión nueva. Revísalo.")
        return 1
    # La marca en git: de aquí sale el historial de la próxima vez.
    git("tag", "-f", f"v{VERSION}")
    if subprocess.run(["git", "push", "-f", "origin", f"v{VERSION}"], cwd=RAIZ).returncode != 0:
        print(f"Ojo: no se ha podido subir la marca v{VERSION} a GitHub. Hazlo con:\n"
              f"    git push origin v{VERSION}")
    print(f"\nPublicada la {VERSION}. Les saldrá al abrir ContaXcell con internet,\n"
          "a los que tengan la cuenta aceptada.")
    return 0


def nombre_android(codigo: int) -> str:
    """El nombre de cada versión de la app, como lo pone android/app/build.gradle.kts."""
    return f"1.0.{codigo}"


def versiones_android() -> list[tuple[int, str]]:
    """(número, commit) de cada app publicada, de la más vieja a la más nueva.
    Salen de las marcas android-48 que pone `publicar --android`."""
    marcas = []
    for nombre in git("tag", "-l", "android-*").split():
        numero = nombre.removeprefix("android-")
        if numero.isdigit():
            marcas.append((int(numero), git("rev-list", "-n", "1", nombre).strip()))
    return sorted(marcas)


def cambios_android(desde: str, hasta: str) -> list[dict]:
    """Lo que cambió en la app (solo lo que toca android/) entre dos commits.
    Sin «desde» (la primera vez), los últimos cambios."""
    rango = [f"{desde}..{hasta}"] if desde else [hasta, "-n", "8"]
    return leer_cambios(git("log", *rango, "--no-merges", "--format=%s%x1f%b%x1e",
                            "--", "../android"))


def historial_android(codigo: int, commit: str, completo: bool = False) -> list[dict]:
    """Lo que trajo cada una de las últimas versiones de la app, la nueva la
    primera: [{versionCode, versionName, fecha, cambios}]. Con `completo`,
    todas, y la primera también (para Ajustes ▸ Ayuda ▸ Historial)."""
    anteriores = [m for m in versiones_android() if m[0] < codigo]
    if not completo:
        anteriores = anteriores[-VERSIONES_EN_HISTORIAL:]
    puntos = anteriores + [(codigo, commit)]
    entradas = []
    for i, (numero, hasta) in enumerate(puntos):
        if i == 0 and anteriores and not completo:
            continue  # la más vieja solo sirve de punto de partida
        desde = puntos[i - 1][1] if i > 0 else ""
        entradas.append({"versionCode": numero, "versionName": nombre_android(numero),
                         "fecha": fecha_de(hasta), "cambios": cambios_android(desde, hasta)})
    return entradas[::-1]


def publicar_android(apk: Path, notas: str, llave_ssh: Path) -> int:
    """Firma y sube la app del móvil que ha compilado GitHub."""
    if not LLAVE_PRIVADA.exists():
        print("Falta la llave de firmar (~/.contaxcell/llave-actualizaciones.json).")
        return 1
    llave = leer_llave()
    from contaxcell.llave_publica import LLAVE_PUBLICA as PUBLICA
    if (llave["n"], llave["e"]) != PUBLICA:
        print("La llave de firmar no es la que conoce el programa (llave_publica.py).")
        return 1
    if not apk.is_file():
        print(f"No encuentro el APK en {apk}.")
        return 1
    datos_compilacion = apk.parent / "compilacion.json"
    if not datos_compilacion.is_file():
        print("Junto al APK falta compilacion.json, que dice qué número y qué commit es.\n"
              "Descarga el artifact entero de GitHub (Actions ▸ App Android ▸ Artifacts)\n"
              "y descomprímelo: vienen los dos.")
        return 1
    compilacion = json.loads(datos_compilacion.read_text(encoding="utf-8"))
    codigo, commit = int(compilacion["versionCode"]), str(compilacion["commit"])
    if not git("cat-file", "-t", commit).strip():
        print(f"Ese APK se compiló del commit {commit[:12]}, que no está en este ordenador.\n"
              "Haz antes git pull.")
        return 1

    servidor, maquina = maquina_del_servidor()
    ssh = ["-i", str(llave_ssh), "-o", "BatchMode=yes"]
    destino = f"ubuntu@{maquina}"
    print(f"Servidor: {servidor}\nApp a publicar: {nombre_android(codigo)} (compilación {codigo})")
    if subprocess.run(["ssh", *ssh, destino, "mkdir -p server/actualizaciones"]).returncode != 0:
        print(f"No se ha podido entrar en el servidor por ssh. ¿Está la llave en {llave_ssh}?")
        return 1
    publicada = nota_publicada(ssh, destino, nota="android.json")
    if publicada is not None:
        anterior = int(json.loads(publicada[0].decode("utf-8"))["versionCode"])
        if codigo <= anterior:
            print(f"\nEn el servidor ya está la compilación {anterior}. Esta es más vieja o la misma.")
            return 1

    entradas = historial_android(codigo, commit)
    for entrada in entradas:
        print(f"\nLa {entrada['versionName']} trae {len(entrada['cambios'])} cambios:")
        for cambio in entrada["cambios"]:
            print(f"  · {cambio['titulo']}")

    datos = apk.read_bytes()
    nombre = f"ContaXcell-android-{codigo}.apk"
    nota = json.dumps({
        "versionCode": codigo,
        "versionName": nombre_android(codigo),
        "archivo": actualizar.RUTA_BASE + nombre,
        "tamano": len(datos),
        "sha256": hashlib.sha256(datos).hexdigest(),
        "notas": notas.strip(),
        "historial": entradas,
        "repositorio": repositorio(),
    }, ensure_ascii=False, indent=2).encode("utf-8")
    salida = RAIZ / "dist" / "publicar"
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "android.json").write_bytes(nota)
    (salida / "android.json.firma").write_bytes(firma.firmar(nota, llave))

    print("\nSubiendo al servidor…")
    pasos = [
        ["scp", *ssh, str(apk), f"{destino}:server/actualizaciones/{nombre}"],
        ["scp", *ssh, str(salida / "android.json"), f"{destino}:server/actualizaciones/.android.json"],
        ["scp", *ssh, str(salida / "android.json.firma"),
         f"{destino}:server/actualizaciones/.android.json.firma"],
        # El del QR, para quien la instala por primera vez. Se copia con otro
        # nombre y se renombra: nadie se baja uno a medias.
        ["ssh", *ssh, destino,
         f"cd server && cp actualizaciones/{nombre} descargas/.ContaXcell.apk"
         " && mv descargas/.ContaXcell.apk descargas/ContaXcell.apk"
         " && cd actualizaciones && mv .android.json.firma android.json.firma"
         " && mv .android.json android.json"],
    ]
    for paso in pasos:
        if subprocess.run(paso).returncode != 0:
            print("Ha fallado la subida. Lo de antes sigue publicado tal cual.")
            return 1

    comprobada = nota_publicada(ssh, destino, nota="android.json")
    if (comprobada is None or comprobada[0] != nota
            or not firma.comprobar(comprobada[0], comprobada[1], PUBLICA)):
        print("Subido, pero al volver a mirar no sale la versión nueva. Revísalo.")
        return 1
    git("tag", "-f", f"android-{codigo}", commit)
    if subprocess.run(["git", "push", "-f", "origin", f"android-{codigo}"], cwd=RAIZ).returncode != 0:
        print(f"Ojo: no se ha podido subir la marca android-{codigo} a GitHub. Hazlo con:\n"
              f"    git push origin android-{codigo}")
    print(f"\nPublicada la app {nombre_android(codigo)}. Les saldrá al abrirla con internet,\n"
          "a los que tengan la cuenta aceptada. El QR de descarga ya da esta.")
    return 0


def escribir_historial_android(destino: Path) -> int:
    """El historial que la app lleva dentro (assets/historial.json). Lo llama
    GitHub al compilarla: su número y su commit salen de GITHUB_RUN_NUMBER y
    GITHUB_SHA. Sin ellos (en local), el commit de ahora."""
    import os
    codigo = int(os.environ.get("GITHUB_RUN_NUMBER") or 0)
    commit = os.environ.get("GITHUB_SHA") or git("rev-parse", "HEAD").strip()
    entradas = historial_android(codigo, commit, completo=True)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(entradas, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Historial de la app: {len(entradas)} versiones en {destino}")
    return 0


def subir_condiciones(llave_ssh: Path) -> int:
    """Sube server/textos/condiciones.md y comprueba que el servidor da esa."""
    import urllib.request

    servidor, maquina = maquina_del_servidor()
    ssh = ["-i", str(llave_ssh), "-o", "BatchMode=yes"]
    destino = f"ubuntu@{maquina}"
    pasos = [["ssh", *ssh, destino, "mkdir -p server/textos"],
             ["scp", *ssh, str(CONDICIONES), f"{destino}:server/textos/condiciones.md"]]
    for paso in pasos:
        if subprocess.run(paso).returncode != 0:
            print("No se han podido subir las condiciones.")
            return 1
    with urllib.request.urlopen(servidor.rstrip("/") + "/api/condiciones", timeout=15) as r:
        recibidas = json.loads(r.read().decode("utf-8"))["texto"]
    if recibidas != CONDICIONES.read_text(encoding="utf-8"):
        print("Subidas, pero el servidor da otras. Revísalo.")
        return 1
    print("Condiciones subidas: el servidor ya da las nuevas. Las cuentas que se creen\n"
          "desde ahora aceptan estas.")
    return 0


def main() -> int:
    analizador = argparse.ArgumentParser(description=__doc__,
                                         formatter_class=argparse.RawDescriptionHelpFormatter)
    analizador.add_argument("notas", nargs="?", default="",
                            help="lo que trae de nuevo, en una frase (se enseña al preguntar)")
    analizador.add_argument("--crear-llave", action="store_true",
                            help="crea la llave de firmar (solo la primera vez)")
    analizador.add_argument("--tambien-viejas", action="store_true",
                            help="deja también la nota donde miraban las versiones "
                                 "hasta la 1.1.2 (una vez, para pasarlas a la nueva)")
    analizador.add_argument("--condiciones", action="store_true",
                            help="sube solo las condiciones de uso (server/textos/condiciones.md)")
    analizador.add_argument("--android", type=Path, metavar="APK",
                            help="publica la app del móvil: el app-debug.apk del artifact de GitHub")
    analizador.add_argument("--historial-android", type=Path, metavar="RUTA",
                            help="escribe el historial que lleva la app dentro (lo usa GitHub)")
    analizador.add_argument("--llave-ssh", type=Path, default=LLAVE_SSH,
                            help=f"la llave .pem del servidor (por defecto {LLAVE_SSH})")
    argumentos = analizador.parse_args()
    if argumentos.crear_llave:
        return crear_llave()
    if argumentos.condiciones:
        return subir_condiciones(argumentos.llave_ssh)
    if argumentos.historial_android:
        return escribir_historial_android(argumentos.historial_android)
    if argumentos.android:
        return publicar_android(argumentos.android, argumentos.notas, argumentos.llave_ssh)
    return publicar(argumentos.notas, argumentos.llave_ssh, argumentos.tambien_viejas)


if __name__ == "__main__":
    raise SystemExit(main())
