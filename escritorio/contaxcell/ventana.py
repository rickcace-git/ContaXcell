"""La ventana principal: cabecera, pestañas y el pegamento entre ellas.

Aquí vive el único `Libro` de la aplicación. Las vistas no lo modifican por su
cuenta: llaman a `app.cambiar(...)`, que aplica el cambio, lo guarda en disco
y avisa a todas las pestañas de que se han quedado anticuadas. Así nunca se
enseña algo que en realidad no se ha llegado a grabar.
"""

from __future__ import annotations

import json
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import calculos, dialogos, formato, tema, widgets
from .almacen import Almacen
from .modelo import Libro

VERSION = "1.0.0"
ARCHIVO_VENTANA = "ventana.json"


def carpeta_de_recursos() -> Path:
    """Dónde están el icono y demás archivos que acompañan al programa.

    Empaquetado con PyInstaller, los datos se descomprimen en una carpeta
    temporal que el propio ejecutable anuncia en `sys._MEIPASS`.
    """
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", ".")) / "recursos"
    return Path(__file__).resolve().parent.parent / "recursos"


def _preparar_pantalla() -> float:
    """Le dice a Windows que la aplicación sabe de pantallas de alta
    resolución. Sin esto el sistema la escala a lo bruto y todo sale borroso.
    Devuelve el factor por el que hay que multiplicar el tamaño de la letra."""
    if sys.platform != "win32":
        return 1.0
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            return 1.0
    try:
        return max(1.0, ctypes.windll.user32.GetDpiForSystem() / 96.0)
    except (AttributeError, OSError):
        return 1.0


class Aplicacion(tk.Tk):
    def __init__(self):
        self.escala = _preparar_pantalla()
        super().__init__()

        self.almacen = Almacen()
        self.libro: Libro = self.almacen.cargar()
        formato.ocultar_importes(self.libro.ajustes.ocultar_importes)

        self.title("ContaXcell")
        self.minsize(940, 620)
        self._restaurar_geometria()
        self._poner_icono()

        self.fuentes = tema.Fuentes(self.escala)
        self.paleta = tema.paleta_para(self.libro.ajustes.tema)
        self.vistas: dict[str, object] = {}
        self._sucias: set[str] = set()
        self._temporizador_estado = None

        self._construir()
        self._atajos()
        self.protocol("WM_DELETE_WINDOW", self._al_cerrar)

        if self.almacen.aviso_de_arranque:
            self.after(300, lambda: dialogos.avisar(
                self, "Aviso al abrir tus datos", self.almacen.aviso_de_arranque))

    # --- montaje ---------------------------------------------------------

    def _construir(self) -> None:
        tema.aplicar(self, self.paleta, self.fuentes)
        widgets.usar(self.paleta, self.fuentes)

        self.raiz = ttk.Frame(self)
        self.raiz.pack(fill="both", expand=True)

        self._construir_cabecera()
        # La barra de estado se coloca antes que las pestañas: en tkinter el
        # primero que se empaqueta reserva su sitio, y el cuaderno se queda
        # con todo lo que sobre. Al revés, la barra se quedaría fuera.
        self._construir_estado()
        self._construir_pestanas()
        self._construir_menu()
        self.refrescar()

    def _construir_cabecera(self) -> None:
        cabecera = ttk.Frame(self.raiz, style="Tarjeta.TFrame")
        cabecera.pack(fill="x")

        fila = ttk.Frame(cabecera, style="Tarjeta.TFrame", padding=(20, 12, 16, 10))
        fila.pack(fill="x")

        marca = ttk.Label(fila, text="ContaXcell", style="Tarjeta.Negrita.TLabel")
        marca.pack(side="left")

        # A la derecha, y en este orden, para que el ojo quede pegado al saldo.
        self.boton_tema = widgets.BotonIcono(fila, "pantalla", self._siguiente_tema)
        self.boton_tema.pack(side="right", padx=(6, 0))
        self.boton_ojo = widgets.BotonIcono(fila, "ojo", self.alternar_ocultos)
        self.boton_ojo.pack(side="right", padx=(14, 0))

        self.etiqueta_saldo = ttk.Label(fila, text="—", style="Tarjeta.Cifra.TLabel")
        self.etiqueta_saldo.pack(side="right")
        ttk.Label(fila, text="Saldo del banco", style="Tarjeta.Suave.TLabel").pack(
            side="right", padx=(0, 10))

        tk.Frame(cabecera, background=self.paleta.borde, height=1).pack(fill="x")

    def _construir_pestanas(self) -> None:
        from .vistas import ajustes, apuntar, inversiones, movimientos, presupuesto, resumen

        self.cuaderno = ttk.Notebook(self.raiz)
        self.cuaderno.pack(fill="both", expand=True)

        definicion = [
            ("apuntar", "Apuntar", apuntar.VistaApuntar),
            ("movimientos", "Movimientos", movimientos.VistaMovimientos),
            ("resumen", "Resumen", resumen.VistaResumen),
            ("presupuesto", "Presupuesto", presupuesto.VistaPresupuesto),
            ("inversiones", "Inversiones", inversiones.VistaInversiones),
            ("ajustes", "Ajustes", ajustes.VistaAjustes),
        ]
        self._claves = [clave for clave, _, _ in definicion]

        for clave, titulo, Clase in definicion:
            marco = ttk.Frame(self.cuaderno)
            self.cuaderno.add(marco, text=titulo)
            self.vistas[clave] = Clase(marco, self)

        # Recién construidas están todas vacías: la primera vez que se abra
        # cada una tiene que pintarse.
        self.ensuciar()

        self.cuaderno.bind("<<NotebookTabChanged>>", lambda _e: self._cambio_de_pestana())

    def _construir_estado(self) -> None:
        barra = ttk.Frame(self.raiz, style="Tarjeta.TFrame")
        barra.pack(fill="x", side="bottom")
        tk.Frame(barra, background=self.paleta.borde, height=1).pack(fill="x")
        self.etiqueta_estado = ttk.Label(barra, text="", style="Tarjeta.Suave.TLabel",
                                         padding=(20, 6))
        self.etiqueta_estado.pack(side="left")

    def _construir_menu(self) -> None:
        barra = tk.Menu(self)

        archivo = tk.Menu(barra, tearoff=0)
        archivo.add_command(label="Importar desde Excel…\tCtrl+I",
                            command=lambda: self.vistas["ajustes"].importar_excel())
        archivo.add_command(label="Exportar a Excel…\tCtrl+E",
                            command=lambda: self.vistas["ajustes"].exportar_excel())
        archivo.add_separator()
        archivo.add_command(label="Guardar copia de seguridad",
                            command=lambda: self.vistas["ajustes"].guardar_copia())
        archivo.add_command(label="Restaurar una copia…",
                            command=lambda: self.vistas["ajustes"].restaurar_copia())
        archivo.add_separator()
        archivo.add_command(label="Abrir la carpeta de mis datos",
                            command=self.abrir_carpeta_datos)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self._al_cerrar)
        barra.add_cascade(label="Archivo", menu=archivo)

        ver = tk.Menu(barra, tearoff=0)
        ver.add_command(label="Ocultar o mostrar los importes\tCtrl+H",
                        command=self.alternar_ocultos)
        ver.add_separator()
        for nombre, valor in (("Como el sistema", "auto"), ("Claro", "claro"), ("Oscuro", "oscuro")):
            ver.add_command(label=f"Tema: {nombre}", command=lambda v=valor: self.poner_tema(v))
        barra.add_cascade(label="Ver", menu=ver)

        ayuda = tk.Menu(barra, tearoff=0)
        ayuda.add_command(label="Acerca de ContaXcell", command=self._acerca_de)
        barra.add_cascade(label="Ayuda", menu=ayuda)

        self.configure(menu=barra)

    def _atajos(self) -> None:
        self.bind_all("<Control-h>", lambda _e: self.alternar_ocultos())
        self.bind_all("<Control-i>", lambda _e: self.vistas["ajustes"].importar_excel())
        self.bind_all("<Control-e>", lambda _e: self.vistas["ajustes"].exportar_excel())
        for numero, clave in enumerate(self._claves, start=1):
            self.bind_all(f"<Control-Key-{numero}>", lambda _e, c=clave: self.ir_a(c))

    def _poner_icono(self) -> None:
        icono = carpeta_de_recursos() / "icono.ico"
        if icono.exists():
            try:
                self.iconbitmap(default=str(icono))
            except tk.TclError:
                pass

    # --- estado compartido -----------------------------------------------

    def cambiar(self, funcion, mensaje: str = "") -> bool:
        """Aplica un cambio al libro, lo guarda y refresca.

        `funcion` recibe el libro y lo modifica. Si lanza una excepción, el
        cambio no se guarda y el usuario ve el motivo.
        """
        try:
            funcion(self.libro)
        except Exception as error:  # noqa: BLE001 - el mensaje es para el usuario
            dialogos.error(self, "No se ha podido hacer el cambio", str(error))
            return False

        try:
            self.almacen.guardar()
        except OSError as error:
            dialogos.error(self, "No se han podido guardar los datos",
                           f"{error}\n\nEl cambio sigue en pantalla, pero no está grabado.")
            return False

        self.ensuciar()
        self.refrescar()
        if mensaje:
            self.estado(mensaje)
        return True

    def reemplazar_libro(self, libro: Libro, motivo: str, mensaje: str = "") -> None:
        """Para importar y restaurar: cambia la contabilidad entera dejando
        antes una copia de seguridad."""
        self.almacen.reemplazar(libro, motivo)
        self.libro = self.almacen.libro
        self.ensuciar()
        self.refrescar()
        if mensaje:
            self.estado(mensaje)

    def ensuciar(self) -> None:
        """Marca todas las pestañas como pendientes de repintar. Solo se
        repinta la que se está mirando; las demás, al abrirlas."""
        self._sucias = set(self.vistas)

    def refrescar(self) -> None:
        self.etiqueta_saldo.configure(text=formato.euros(calculos.saldo_banco(self.libro)))
        self._pintar_botones()
        self._refrescar_actual()

    def _refrescar_actual(self) -> None:
        clave = self.pestana_actual()
        vista = self.vistas.get(clave)
        if vista is None:
            return
        vista.refrescar()
        self._sucias.discard(clave)

    def _cambio_de_pestana(self) -> None:
        clave = self.pestana_actual()
        if clave in self._sucias:
            self._refrescar_actual()
        vista = self.vistas.get(clave)
        if vista is not None and hasattr(vista, "al_entrar"):
            vista.al_entrar()

    def pestana_actual(self) -> str:
        try:
            return self._claves[self.cuaderno.index(self.cuaderno.select())]
        except (tk.TclError, IndexError):
            return self._claves[0]

    def ir_a(self, clave: str) -> None:
        if clave in self._claves:
            self.cuaderno.select(self._claves.index(clave))

    def estado(self, mensaje: str, clase: str = "") -> None:
        """Un mensaje breve en la barra de abajo. Se borra solo."""
        colores = {"bien": self.paleta.ingreso, "malo": self.paleta.gasto}
        self.etiqueta_estado.configure(
            text=mensaje, foreground=colores.get(clase, self.paleta.suave))
        if self._temporizador_estado:
            self.after_cancel(self._temporizador_estado)
        self._temporizador_estado = self.after(
            6000, lambda: self.etiqueta_estado.configure(text=""))

    # --- ojo y tema -------------------------------------------------------

    def alternar_ocultos(self) -> None:
        nuevo = not self.libro.ajustes.ocultar_importes
        formato.ocultar_importes(nuevo)
        self.cambiar(lambda libro: setattr(libro.ajustes, "ocultar_importes", nuevo))

    def poner_tema(self, valor: str) -> None:
        if valor == self.libro.ajustes.tema:
            return
        self.libro.ajustes.tema = valor
        self.almacen.guardar()
        self.paleta = tema.paleta_para(valor)
        # Cambiar de tema toca colores de widgets que no se pueden repintar en
        # caliente, así que se rehace la ventana entera desde cero.
        actual = self.pestana_actual()
        self.raiz.destroy()
        self.vistas.clear()
        self._construir()
        self.ir_a(actual)

    def _siguiente_tema(self) -> None:
        orden = ["auto", "claro", "oscuro"]
        actual = self.libro.ajustes.tema
        siguiente = orden[(orden.index(actual) + 1) % len(orden)] if actual in orden else "claro"
        self.poner_tema(siguiente)

    def _pintar_botones(self) -> None:
        oculto = self.libro.ajustes.ocultar_importes
        self.boton_ojo.poner_icono("ojo-tachado" if oculto else "ojo")
        _consejo(self.boton_ojo,
                 "Mostrar los importes (Ctrl+H)" if oculto
                 else "Ocultar los importes (Ctrl+H)")

        iconos = {"auto": "pantalla", "claro": "sol", "oscuro": "luna"}
        nombres = {"auto": "como el sistema", "claro": "claro", "oscuro": "oscuro"}
        actual = self.libro.ajustes.tema
        self.boton_tema.poner_icono(iconos.get(actual, "pantalla"))
        _consejo(self.boton_tema, f"Tema: {nombres.get(actual, actual)}. Pulsa para cambiar.")

    # --- varios -----------------------------------------------------------

    def abrir_carpeta_datos(self) -> None:
        carpeta = self.almacen.carpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            import os
            os.startfile(carpeta)  # noqa: S606 - es una carpeta nuestra
        else:
            import subprocess
            subprocess.Popen(["xdg-open", str(carpeta)])

    def _acerca_de(self) -> None:
        dialogos.avisar(
            self,
            f"ContaXcell {VERSION}",
            "Contabilidad personal de escritorio.\n\n"
            "Tus datos no salen de este ordenador. Están en:\n"
            f"{self.almacen.carpeta}",
        )

    # --- tamaño de la ventana --------------------------------------------

    def _ruta_geometria(self) -> Path:
        return self.almacen.carpeta / ARCHIVO_VENTANA

    def _restaurar_geometria(self) -> None:
        ancho, alto = int(1180 * self.escala), int(800 * self.escala)
        try:
            guardado = json.loads(self._ruta_geometria().read_text(encoding="utf-8"))
            geometria = guardado.get("geometria", "")
            if geometria:
                self.geometry(geometria)
            if guardado.get("maximizada"):
                self.state("zoomed")
            return
        except (OSError, ValueError):
            pass

        # Primera vez: centrada y sin salirse de la pantalla.
        pantalla_ancho = self.winfo_screenwidth()
        pantalla_alto = self.winfo_screenheight()
        ancho = min(ancho, pantalla_ancho - 80)
        alto = min(alto, pantalla_alto - 120)
        x = (pantalla_ancho - ancho) // 2
        y = max(0, (pantalla_alto - alto) // 2 - 20)
        self.geometry(f"{ancho}x{alto}+{x}+{y}")

    def _guardar_geometria(self) -> None:
        try:
            maximizada = self.state() == "zoomed"
            datos = {
                "geometria": self.geometry() if not maximizada else "",
                "maximizada": maximizada,
            }
            self.almacen.carpeta.mkdir(parents=True, exist_ok=True)
            self._ruta_geometria().write_text(json.dumps(datos), encoding="utf-8")
        except (OSError, tk.TclError):
            pass  # El tamaño de la ventana no merece una queja.

    def _al_cerrar(self) -> None:
        self._guardar_geometria()
        self.destroy()


def _consejo(widget: tk.Widget, texto: str) -> None:
    """Un globo de ayuda al dejar el ratón encima."""
    if getattr(widget, "_consejo_texto", None) == texto:
        return
    widget._consejo_texto = texto

    if getattr(widget, "_consejo_atado", False):
        return
    widget._consejo_atado = True
    estado = {"ventana": None, "temporizador": None}

    def mostrar():
        if estado["ventana"] is not None:
            return
        globo = tk.Toplevel(widget)
        globo.wm_overrideredirect(True)
        globo.configure(background=widgets.PALETA.borde)
        tk.Label(globo, text=widget._consejo_texto, background=widgets.PALETA.tarjeta,
                 foreground=widgets.PALETA.texto, font=widgets.FUENTES.pequena,
                 padx=8, pady=4).pack(padx=1, pady=1)
        x = widget.winfo_rootx() + widget.winfo_width() // 2 - 80
        y = widget.winfo_rooty() + widget.winfo_height() + 6
        globo.wm_geometry(f"+{max(0, x)}+{y}")
        estado["ventana"] = globo

    def entrar(_evento=None):
        estado["temporizador"] = widget.after(550, mostrar)

    def salir(_evento=None):
        if estado["temporizador"]:
            widget.after_cancel(estado["temporizador"])
            estado["temporizador"] = None
        if estado["ventana"] is not None:
            estado["ventana"].destroy()
            estado["ventana"] = None

    widget.bind("<Enter>", entrar, add="+")
    widget.bind("<Leave>", salir, add="+")
    widget.bind("<ButtonPress>", salir, add="+")


def arrancar() -> None:
    Aplicacion().mainloop()
