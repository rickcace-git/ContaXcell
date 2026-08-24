"""Arranca ContaXcell.

    python ejecutar.py

Es también el punto de entrada que usa PyInstaller al construir el ejecutable,
por eso está aquí fuera y no dentro del paquete: así funciona igual ejecutado
como archivo suelto que empaquetado.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from contaxcell.ventana import arrancar

if __name__ == "__main__":
    arrancar()
