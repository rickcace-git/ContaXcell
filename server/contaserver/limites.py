"""Contar intentos para que nadie se ponga a probar contraseñas a lo bruto.

Una sola pieza: un contador de intentos por clave (una IP, un nombre de
usuario) dentro de una ventana de tiempo que va corriendo. Se apunta la hora
de cada intento y se olvidan los que ya se han salido de la ventana, así que
diez fallos seguidos bloquean, pero pasado el rato la cuenta vuelve a cero
sola: nadie se queda encerrado para siempre por equivocarse una tarde.

Todo con la biblioteca estándar y con un candado delante, porque el servidor
atiende varias peticiones a la vez. El reloj se puede cambiar al construirlo,
que es lo que permite probarlo sin esperar quince minutos de verdad.
"""

from __future__ import annotations

import threading
import time


class Limitador:
    """Cuántos intentos lleva cada clave en los últimos ``ventana`` segundos.

    ``maximo`` es el número de intentos que se permiten dentro de la ventana:
    al llegar a esa cifra, ``bloqueado`` empieza a decir que sí.
    """

    def __init__(self, maximo: int, ventana: float, reloj=time.monotonic):
        self.maximo = maximo
        self.ventana = ventana
        self._reloj = reloj
        self._intentos: dict[str, list[float]] = {}
        self._candado = threading.Lock()

    def bloqueado(self, clave: str) -> bool:
        """¿Esa clave ya ha gastado todos sus intentos?"""
        with self._candado:
            return len(self._vigentes(clave)) >= self.maximo

    def apunta(self, clave: str) -> None:
        """Un intento más para esa clave, con la hora de ahora."""
        with self._candado:
            vigentes = self._vigentes(clave)
            vigentes.append(self._reloj())
            self._intentos[clave] = vigentes
            self._barrer()

    def olvida(self, clave: str) -> None:
        """Borra la cuenta de esa clave. Se usa al acertar la contraseña."""
        with self._candado:
            self._intentos.pop(clave, None)

    # --- por dentro ----------------------------------------------------------

    def _vigentes(self, clave: str) -> list[float]:
        """Los intentos de esa clave que aún caen dentro de la ventana."""
        desde = self._reloj() - self.ventana
        return [cuando for cuando in self._intentos.get(clave, ()) if cuando > desde]

    def _barrer(self) -> None:
        """Tira las claves sin intentos vigentes, para no crecer sin fin.

        Sin esto, cada IP que pasa por aquí dejaría su entrada en el
        diccionario para siempre.
        """
        desde = self._reloj() - self.ventana
        caducadas = [
            clave
            for clave, horas in self._intentos.items()
            if not any(cuando > desde for cuando in horas)
        ]
        for clave in caducadas:
            del self._intentos[clave]
