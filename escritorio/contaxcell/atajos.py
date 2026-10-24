"""Los atajos de teclado, con la tecla de mando de cada sistema.

Viven aparte porque los usan dos: la ventana, que los ata, y la guía de uso,
que los cuenta. Así se escriben en un solo sitio y la guía no dice «Ctrl+H»
en un Mac. No importa tkinter: son solo textos.
"""

from __future__ import annotations

import sys
from typing import NamedTuple

ES_MAC = sys.platform == "darwin"


class Atajo(NamedTuple):
    evento: str      # lo que se le pasa a `bind_all`
    acelerador: str  # lo que se pone en el menú
    texto: str       # cómo se escribe para quien lo lee


def atajo(tecla: str, con_shift_en_mac: bool = False) -> Atajo:
    """En el Mac lo que en Windows va con Control va con ⌘. En el menú basta
    con escribir «Command-E»: el Tk del Mac ya lo dibuja como ⌘E."""
    if not ES_MAC:
        return Atajo(f"<Control-Key-{tecla}>", f"Ctrl+{tecla.upper()}", f"Ctrl+{tecla.upper()}")
    if con_shift_en_mac:
        # Con mayúsculas pulsada, Tk recibe la letra ya en mayúscula.
        return Atajo(f"<Command-Shift-Key-{tecla.upper()}>",
                     f"Shift-Command-{tecla.upper()}", f"⇧⌘{tecla.upper()}")
    return Atajo(f"<Command-Key-{tecla}>", f"Command-{tecla.upper()}", f"⌘{tecla.upper()}")


def pestana(numero: int) -> Atajo:
    """Ctrl+1 (⌘1 en el Mac) es la primera pestaña, y así hasta la octava."""
    return atajo(str(numero))


# ⌘H, en el Mac, es «Ocultar ContaXcell»: el sistema se lo queda antes de que
# llegue a la ventana. Por eso allí ocultar los importes lleva mayúsculas.
OCULTAR = atajo("h", con_shift_en_mac=True)
