"""Colores y estilos de la ventana.

Tkinter no trae tema oscuro, así que se define aquí la paleta entera y se le
enchufa a ttk. Es la misma que usaba la versión web, para que las dos se
parezcan.
"""

from __future__ import annotations

import sys
import tkinter as tk
from dataclasses import dataclass
from tkinter import font as tkfont
from tkinter import ttk


@dataclass(frozen=True)
class Paleta:
    """Los colores de la ventana.

    Los cuatro grises van en escalera y cada escalón se tiene que notar:
    `fondo` (la página) es el más oscuro, encima va `tarjeta`, dentro de ella
    `hundido` para las casillas, y `boton` más marcado todavía para que un
    botón se distinga de lo que tiene detrás sin necesidad de mirarlo dos
    veces. Si dos escalones se acercan demasiado, todo se vuelve una masa
    blanca y no se sabe qué se puede pulsar.

    Los grises tiran ligeramente a azul, hacia el color de acento, para que
    parezcan elegidos y no un gris de fábrica.
    """

    fondo: str
    tarjeta: str
    hundido: str
    boton: str
    boton_encima: str
    texto: str
    suave: str
    borde: str
    gasto: str
    ingreso: str
    inversion: str
    acento: str
    aviso: str
    seleccion: str
    campo: str
    oscuro: bool


CLARA = Paleta(
    fondo="#d6dae2",
    tarjeta="#f8f9fb",
    hundido="#e9ecf1",
    boton="#dbdfe7",
    boton_encima="#c8ced9",
    texto="#1a1d21",
    suave="#5c6470",
    borde="#c3c9d4",
    gasto="#c02f2f",
    ingreso="#15733f",
    inversion="#6836ad",
    acento="#2f6feb",
    aviso="#96680a",
    seleccion="#cddffb",
    campo="#ffffff",
    oscuro=False,
)

OSCURA = Paleta(
    fondo="#15181c",
    tarjeta="#1e2228",
    hundido="#262b32",
    boton="#333a44",
    boton_encima="#414954",
    texto="#eceef1",
    suave="#9aa2ad",
    borde="#3a414b",
    gasto="#f0736f",
    ingreso="#4cc98a",
    inversion="#b492e8",
    acento="#6c9bff",
    aviso="#e0b84c",
    seleccion="#2c3a54",
    campo="#1a1e23",
    oscuro=True,
)


def sistema_en_oscuro() -> bool:
    """Si Windows está en modo oscuro. Fuera de Windows asumimos claro."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        clave = winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        )
        with clave:
            usar_claro, _ = winreg.QueryValueEx(clave, "AppsUseLightTheme")
        return usar_claro == 0
    except OSError:
        return False


def paleta_para(preferencia: str) -> Paleta:
    if preferencia == "claro":
        return CLARA
    if preferencia == "oscuro":
        return OSCURA
    return OSCURA if sistema_en_oscuro() else CLARA


# --- fuentes ---------------------------------------------------------------

FAMILIA = "Segoe UI" if sys.platform == "win32" else "TkDefaultFont"


class Fuentes:
    """Se crean una sola vez y se reutilizan; crear fuentes en cada repintado
    consume recursos del sistema y acaba dando errores raros."""

    def __init__(self, escala: float = 1.0):
        def tam(puntos: int) -> int:
            return max(7, round(puntos * escala))

        self.normal = tkfont.Font(family=FAMILIA, size=tam(10))
        self.pequena = tkfont.Font(family=FAMILIA, size=tam(9))
        self.diminuta = tkfont.Font(family=FAMILIA, size=tam(8))
        self.negrita = tkfont.Font(family=FAMILIA, size=tam(10), weight="bold")
        self.titulo = tkfont.Font(family=FAMILIA, size=tam(9), weight="bold")
        self.cifra = tkfont.Font(family=FAMILIA, size=tam(15), weight="bold")
        self.cifra_grande = tkfont.Font(family=FAMILIA, size=tam(17), weight="bold")
        self.importe = tkfont.Font(family=FAMILIA, size=tam(22), weight="bold")


def aplicar(raiz: tk.Misc, paleta: Paleta, fuentes: Fuentes) -> ttk.Style:
    """Deja todos los widgets ttk con los colores de la paleta.

    Se usa el tema 'clam' porque es el único de los que trae tkinter que
    permite cambiar de verdad los colores; los nativos de Windows ignoran casi
    todo lo que se les pide.
    """
    estilo = ttk.Style(raiz)
    estilo.theme_use("clam")
    p = paleta

    raiz.configure(background=p.fondo)

    estilo.configure(".", background=p.fondo, foreground=p.texto,
                     font=fuentes.normal, borderwidth=0, focuscolor=p.acento)

    estilo.configure("TFrame", background=p.fondo)
    estilo.configure("Tarjeta.TFrame", background=p.tarjeta)
    estilo.configure("Hundido.TFrame", background=p.hundido)

    for nombre, fondo in (("TLabel", p.fondo), ("Tarjeta.TLabel", p.tarjeta),
                          ("Hundido.TLabel", p.hundido)):
        estilo.configure(nombre, background=fondo, foreground=p.texto, font=fuentes.normal)

    # Variantes de texto. El sufijo dice el color; el prefijo, sobre qué fondo.
    for prefijo, fondo in (("", p.fondo), ("Tarjeta.", p.tarjeta), ("Hundido.", p.hundido)):
        for sufijo, color, fuente in (
            ("Suave", p.suave, fuentes.pequena),
            ("Titulo", p.suave, fuentes.titulo),
            ("Ingreso", p.ingreso, fuentes.normal),
            ("Gasto", p.gasto, fuentes.normal),
            ("Inversion", p.inversion, fuentes.normal),
            ("Aviso", p.aviso, fuentes.normal),
            ("Negrita", p.texto, fuentes.negrita),
            ("Cifra", p.texto, fuentes.cifra),
        ):
            estilo.configure(f"{prefijo}{sufijo}.TLabel",
                             background=fondo, foreground=color, font=fuente)

    # Los importes grandes de las tarjetas de cifras, con su color.
    for sufijo, color in (("", p.texto), ("Ingreso", p.ingreso),
                          ("Gasto", p.gasto), ("Inversion", p.inversion),
                          ("Suave", p.suave)):
        estilo.configure(f"Hundido.Grande{sufijo}.TLabel",
                         background=p.hundido, foreground=color, font=fuentes.cifra)

    _botones(estilo, p, fuentes)
    _entradas(estilo, p, fuentes)
    _tablas(estilo, p, fuentes)
    _pestanas(estilo, p, fuentes)

    estilo.configure("TSeparator", background=p.borde)
    estilo.configure("Vertical.TScrollbar", background=p.hundido, troughcolor=p.fondo,
                     bordercolor=p.fondo, arrowcolor=p.suave, relief="flat")
    estilo.map("Vertical.TScrollbar", background=[("active", p.borde)])
    estilo.configure("Horizontal.TScrollbar", background=p.hundido, troughcolor=p.fondo,
                     bordercolor=p.fondo, arrowcolor=p.suave, relief="flat")
    estilo.map("Horizontal.TScrollbar", background=[("active", p.borde)])

    return estilo


def _botones(estilo: ttk.Style, p: Paleta, fuentes: Fuentes) -> None:
    # Un botón normal tiene color propio y borde marcado: es lo que lo separa
    # de la tarjeta que tiene detrás y lo que dice que se puede pulsar.
    estilo.configure("TButton", background=p.boton, foreground=p.texto,
                     font=fuentes.normal, relief="flat", padding=(12, 6),
                     borderwidth=1, bordercolor=p.borde,
                     lightcolor=p.boton, darkcolor=p.boton)
    estilo.map("TButton",
               background=[("pressed", p.boton_encima), ("active", p.boton_encima),
                           ("disabled", p.hundido)],
               lightcolor=[("pressed", p.boton_encima), ("active", p.boton_encima)],
               darkcolor=[("pressed", p.boton_encima), ("active", p.boton_encima)],
               bordercolor=[("active", p.suave)],
               foreground=[("disabled", p.suave)])

    estilo.configure("Principal.TButton", background=p.acento, foreground="#ffffff",
                     font=fuentes.negrita, padding=(12, 9), bordercolor=p.acento,
                     lightcolor=p.acento, darkcolor=p.acento)
    estilo.map("Principal.TButton",
               background=[("pressed", p.acento), ("active", p.acento), ("disabled", p.borde)],
               foreground=[("disabled", p.suave)])

    estilo.configure("Peligro.TButton", background=p.boton, foreground=p.gasto,
                     lightcolor=p.boton, darkcolor=p.boton)
    estilo.map("Peligro.TButton",
               background=[("active", p.gasto), ("pressed", p.gasto)],
               lightcolor=[("active", p.gasto), ("pressed", p.gasto)],
               darkcolor=[("active", p.gasto), ("pressed", p.gasto)],
               bordercolor=[("active", p.gasto), ("pressed", p.gasto)],
               foreground=[("active", "#ffffff"), ("pressed", "#ffffff")])

    # Botones-icono de la barra superior: cuadrados y sin relleno.
    estilo.configure("Icono.TButton", background=p.tarjeta, foreground=p.suave,
                     padding=(8, 5), bordercolor=p.borde)
    estilo.map("Icono.TButton",
               background=[("active", p.boton), ("pressed", p.boton)],
               foreground=[("active", p.texto)])

    # Los dos botones Gasto / Ingreso del formulario de apuntar.
    for nombre, color in (("Gasto", p.gasto), ("Ingreso", p.ingreso)):
        estilo.configure(f"{nombre}Apagado.TButton", background=p.boton,
                         foreground=p.suave, font=fuentes.negrita, padding=(12, 9),
                         bordercolor=p.borde, borderwidth=2,
                         lightcolor=p.boton, darkcolor=p.boton)
        estilo.map(f"{nombre}Apagado.TButton",
                   background=[("active", p.boton_encima)],
                   lightcolor=[("active", p.boton_encima)],
                   darkcolor=[("active", p.boton_encima)],
                   bordercolor=[("active", color)],
                   foreground=[("active", color)])
        estilo.configure(f"{nombre}Encendido.TButton", background=color,
                         foreground="#ffffff", font=fuentes.negrita, padding=(12, 9),
                         bordercolor=color, borderwidth=2)
        estilo.map(f"{nombre}Encendido.TButton",
                   background=[("active", color), ("pressed", color)],
                   foreground=[("active", "#ffffff")])

    estilo.configure("Enlace.TButton", background=p.tarjeta, foreground=p.acento,
                     font=fuentes.pequena, padding=(4, 2), borderwidth=0)
    estilo.map("Enlace.TButton", background=[("active", p.tarjeta)],
               foreground=[("active", p.texto)])


def _entradas(estilo: ttk.Style, p: Paleta, fuentes: Fuentes) -> None:
    campo = p.campo
    estilo.configure("TEntry", fieldbackground=campo, background=campo,
                     foreground=p.texto, insertcolor=p.texto, bordercolor=p.borde,
                     lightcolor=p.borde, darkcolor=p.borde, borderwidth=1,
                     padding=(7, 5), relief="flat")
    estilo.map("TEntry",
               bordercolor=[("focus", p.acento)],
               lightcolor=[("focus", p.acento)],
               darkcolor=[("focus", p.acento)])

    estilo.configure("Importe.TEntry", padding=(8, 9))

    estilo.configure("TCombobox", fieldbackground=campo, background=campo,
                     foreground=p.texto, arrowcolor=p.suave, bordercolor=p.borde,
                     lightcolor=p.borde, darkcolor=p.borde, borderwidth=1,
                     padding=(7, 5), relief="flat", selectbackground=campo,
                     selectforeground=p.texto)
    estilo.map("TCombobox",
               fieldbackground=[("readonly", campo), ("disabled", p.hundido)],
               foreground=[("disabled", p.suave)],
               bordercolor=[("focus", p.acento)],
               lightcolor=[("focus", p.acento)],
               darkcolor=[("focus", p.acento)])

    estilo.configure("TCheckbutton", background=p.tarjeta, foreground=p.texto,
                     indicatorcolor=campo, font=fuentes.normal)
    estilo.map("TCheckbutton", background=[("active", p.tarjeta)],
               indicatorcolor=[("selected", p.acento)])


def _tablas(estilo: ttk.Style, p: Paleta, fuentes: Fuentes) -> None:
    estilo.configure("Treeview", background=p.tarjeta, fieldbackground=p.tarjeta,
                     foreground=p.texto, font=fuentes.normal, borderwidth=0,
                     rowheight=int(fuentes.normal.metrics("linespace") * 1.75))
    estilo.map("Treeview",
               background=[("selected", p.seleccion)],
               foreground=[("selected", p.texto)])

    estilo.configure("Treeview.Heading", background=p.hundido, foreground=p.suave,
                     font=fuentes.titulo, relief="flat", padding=(6, 6),
                     borderwidth=0)
    estilo.map("Treeview.Heading", background=[("active", p.borde)])


def _pestanas(estilo: ttk.Style, p: Paleta, fuentes: Fuentes) -> None:
    estilo.configure("TNotebook", background=p.tarjeta, borderwidth=0, tabmargins=(10, 0, 0, 0))
    estilo.configure("TNotebook.Tab", background=p.tarjeta, foreground=p.suave,
                     font=fuentes.normal, padding=(16, 9), borderwidth=0)
    estilo.map("TNotebook.Tab",
               background=[("selected", p.tarjeta), ("active", p.tarjeta)],
               foreground=[("selected", p.acento), ("active", p.texto)],
               font=[("selected", fuentes.negrita)])
