"""Dónde vive la contabilidad y cómo se guarda.

Todo está en un único archivo JSON dentro de la carpeta del usuario. El
programa nunca escribe en la carpeta donde está instalado, así que actualizar
la aplicación (o borrarla y volver a copiarla) no toca los datos.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from .modelo import Libro

NOMBRE_ARCHIVO = "datos.json"
CARPETA_COPIAS = "copias"
COPIAS_QUE_GUARDAMOS = 20


def carpeta_de_datos() -> Path:
    """%APPDATA%\\ContaXcell en Windows; una carpeta oculta en la home en
    cualquier otro sitio."""
    base = os.environ.get("APPDATA")
    if base:
        return Path(base) / "ContaXcell"
    return Path.home() / ".contaxcell"


class Almacen:
    def __init__(self, carpeta: Path | None = None):
        self.carpeta = Path(carpeta) if carpeta else carpeta_de_datos()
        self.ruta = self.carpeta / NOMBRE_ARCHIVO
        self.ruta_copias = self.carpeta / CARPETA_COPIAS
        self.libro = Libro.vacio()
        # Se rellena si al arrancar hubo que apartar un archivo ilegible, para
        # que la ventana pueda avisar en vez de tragárselo en silencio.
        self.aviso_de_arranque = ""

    # --- carga y guardado ---

    def cargar(self) -> Libro:
        try:
            texto = self.ruta.read_text(encoding="utf-8")
        except FileNotFoundError:
            # Primer arranque: empezamos en blanco y dejamos el archivo hecho.
            self.libro = Libro.vacio()
            self.guardar()
            return self.libro
        except OSError as error:
            self.aviso_de_arranque = f"No se ha podido leer el archivo de datos: {error}"
            self.libro = Libro.vacio()
            return self.libro

        try:
            self.libro = Libro.desde_json(json.loads(texto))
        except (ValueError, TypeError):
            # El archivo existe pero no se entiende. Antes de sobrescribirlo
            # lo apartamos: es preferible arrancar vacío a perder el original.
            apartado = self._apartar_ilegible()
            self.aviso_de_arranque = (
                "El archivo de datos estaba dañado y no se ha podido leer. "
                f"Se ha guardado una copia intacta en {apartado.name} y se ha "
                "empezado un libro nuevo."
            ) if apartado else "El archivo de datos estaba dañado y no se ha podido leer."
            self.libro = Libro.vacio()
            self.guardar()
        return self.libro

    def guardar(self) -> None:
        """Escritura en dos pasos: primero un archivo temporal completo y
        luego el cambio de nombre, que es atómico. Si se corta la luz a mitad,
        queda el archivo viejo entero o el nuevo entero, nunca uno partido."""
        self.carpeta.mkdir(parents=True, exist_ok=True)
        temporal = self.ruta.with_suffix(".tmp")
        temporal.write_text(
            json.dumps(self.libro.a_json(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(temporal, self.ruta)

    # --- copias de seguridad ---

    def copia_de_seguridad(self, motivo: str = "copia") -> Path | None:
        """Una copia fechada antes de cada operación que toca muchas filas de
        golpe: importar, restaurar, reemplazar."""
        if not self.ruta.exists():
            return None
        try:
            self.ruta_copias.mkdir(parents=True, exist_ok=True)
            sello = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            destino = self.ruta_copias / f"{sello}-{motivo}.json"
            shutil.copy2(self.ruta, destino)
            self._limpiar_copias()
            return destino
        except OSError:
            return None

    def _limpiar_copias(self) -> None:
        copias = self.listar_copias()
        # Están de más reciente a más antigua: sobran las del final.
        for vieja in copias[COPIAS_QUE_GUARDAMOS:]:
            try:
                vieja.unlink()
            except OSError:
                pass  # Limpiar copias es un lujo, no una obligación.

    def listar_copias(self) -> list[Path]:
        try:
            return sorted(self.ruta_copias.glob("*.json"), reverse=True)
        except OSError:
            return []

    # --- reemplazos completos ---

    def reemplazar(self, libro: Libro, motivo: str = "antes-de-reemplazar") -> None:
        self.copia_de_seguridad(motivo)
        self.libro = libro
        self.guardar()

    def restaurar(self, origen: Path) -> None:
        """Sustituye la contabilidad por la de otro archivo, dejando antes una
        copia de lo que había para poder dar marcha atrás."""
        datos = json.loads(Path(origen).read_text(encoding="utf-8"))
        nuevo = Libro.desde_json(datos)
        self.reemplazar(nuevo, "antes-de-restaurar")

    def _apartar_ilegible(self) -> Path | None:
        sello = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        destino = self.carpeta / f"datos-ilegible-{sello}.json"
        try:
            shutil.move(str(self.ruta), str(destino))
            return destino
        except OSError:
            return None
