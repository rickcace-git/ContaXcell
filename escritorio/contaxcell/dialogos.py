"""Ventanas emergentes: formularios y confirmaciones.

Los formularios se construyen a partir de una lista de campos en vez de a
mano, porque casi todos piden lo mismo (un texto, un importe, una fecha, una
opción de una lista) y así todos validan igual y se ven igual.

Las confirmaciones usan los diálogos nativos de Windows a propósito: cuando se
va a borrar algo conviene que se note que lo pregunta el sistema.
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass, field
from tkinter import messagebox, ttk

from . import widgets
from .formato import texto_a_fecha, texto_a_numero


# --- descripción de los campos ---------------------------------------------

@dataclass
class Texto:
    clave: str
    etiqueta: str
    valor: str = ""
    pista: str = ""
    obligatorio: bool = False
    ayuda: str = ""


@dataclass
class Importe:
    clave: str
    etiqueta: str
    valor: float | None = None
    ayuda: str = ""
    permitir_cero: bool = True
    permitir_negativo: bool = False


@dataclass
class Fecha:
    clave: str
    etiqueta: str
    valor: str = ""
    ayuda: str = ""


@dataclass
class Opcion:
    clave: str
    etiqueta: str
    opciones: list[str] = field(default_factory=list)
    valor: str = ""
    ayuda: str = ""
    # Texto que se enseña en la lista cuando el valor es vacío.
    vacio: str | None = None


@dataclass
class Nota:
    """No pide nada: es una explicación dentro del formulario."""

    texto: str
    clave: str = ""


class Formulario(tk.Toplevel):
    """Ventana modal con campos. `mostrar()` devuelve un diccionario con los
    valores, o None si se cancela."""

    def __init__(self, padre, titulo: str, campos: list, aceptar: str = "Guardar",
                 al_cambiar=None, validar=None):
        super().__init__(padre)
        self.title(titulo)
        self.resizable(False, False)
        self.configure(background=widgets.PALETA.tarjeta)
        self.transient(padre)

        self.campos = campos
        self.al_cambiar = al_cambiar
        self.validar = validar
        self.resultado: dict | None = None
        self._variables: dict[str, tk.Variable] = {}
        self._controles: dict[str, tk.Widget] = {}
        self._bloques: dict[str, ttk.Frame] = {}
        self._orden: list[str] = []

        cuerpo = ttk.Frame(self, style="Tarjeta.TFrame", padding=18)
        cuerpo.pack(fill="both", expand=True)
        ttk.Label(cuerpo, text=titulo, style="Tarjeta.Negrita.TLabel").pack(anchor="w",
                                                                           pady=(0, 6))

        self.zona_campos = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
        self.zona_campos.pack(fill="x")
        for campo in campos:
            self._construir(campo)

        self.error = ttk.Label(cuerpo, text="", style="Tarjeta.Gasto.TLabel",
                               wraplength=340, justify="left")
        self.error.pack(anchor="w", pady=(8, 0))

        pie = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
        pie.pack(fill="x", pady=(14, 0))
        ttk.Button(pie, text="Cancelar", command=self._cancelar).pack(side="right")
        ttk.Button(pie, text=aceptar, style="Principal.TButton",
                   command=self._aceptar).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _e: self._aceptar())
        self.bind("<Escape>", lambda _e: self._cancelar())
        self.protocol("WM_DELETE_WINDOW", self._cancelar)

        if al_cambiar:
            al_cambiar(self, None)

    # --- construcción ---

    def _construir(self, campo) -> None:
        bloque = ttk.Frame(self.zona_campos, style="Tarjeta.TFrame")
        bloque.pack(fill="x")

        if isinstance(campo, Nota):
            ttk.Label(bloque, text=campo.texto, style="Tarjeta.Suave.TLabel",
                      wraplength=340, justify="left").pack(anchor="w", pady=(8, 0))
            if campo.clave:
                self._bloques[campo.clave] = bloque
                self._orden.append(campo.clave)
            return

        widgets.etiqueta_campo(bloque, campo.etiqueta)

        if isinstance(campo, Opcion):
            variable = tk.StringVar(value=campo.valor)
            valores = list(campo.opciones)
            if campo.vacio is not None:
                valores = [campo.vacio] + valores
                if not campo.valor:
                    variable.set(campo.vacio)
            control = ttk.Combobox(bloque, textvariable=variable, values=valores,
                                   state="readonly", width=30)
            control.pack(fill="x")
            control.bind("<<ComboboxSelected>>", lambda _e: self._cambio())
        elif isinstance(campo, Fecha):
            control = widgets.CampoFecha(bloque, campo.valor)
            control.pack(anchor="w")
            variable = control.variable
        else:
            inicial = ""
            if isinstance(campo, Importe) and campo.valor is not None:
                inicial = f"{campo.valor:.2f}".replace(".", ",")
            elif isinstance(campo, Texto):
                inicial = campo.valor
            variable = tk.StringVar(value=inicial)
            control = ttk.Entry(bloque, textvariable=variable, width=34)
            if isinstance(campo, Texto) and campo.pista:
                _pista(control, variable, campo.pista)
            control.pack(fill="x")

        if campo.ayuda:
            ttk.Label(bloque, text=campo.ayuda, style="Tarjeta.Suave.TLabel",
                      wraplength=340, justify="left").pack(anchor="w", pady=(3, 0))

        self._variables[campo.clave] = variable
        self._controles[campo.clave] = control
        self._bloques[campo.clave] = bloque
        self._orden.append(campo.clave)

    def _cambio(self) -> None:
        if self.al_cambiar:
            self.al_cambiar(self, None)

    # --- interfaz para quien lo usa ---

    def valor(self, clave: str) -> str:
        variable = self._variables.get(clave)
        if variable is None:
            return ""
        texto = variable.get()
        # El texto de ejemplo en gris no es algo que haya escrito el usuario.
        if getattr(self._controles.get(clave), "pista", None) == texto:
            return ""
        return texto

    def poner_opciones(self, clave: str, opciones: list[str], vacio: str | None = None) -> None:
        control = self._controles.get(clave)
        if not isinstance(control, ttk.Combobox):
            return
        valores = ([vacio] + list(opciones)) if vacio is not None else list(opciones)
        control.configure(values=valores)
        if self.valor(clave) not in valores:
            self._variables[clave].set(valores[0] if valores else "")

    def mostrar_campo(self, clave: str, visible: bool) -> None:
        """Enseña u oculta un campo sin perder su sitio en el orden."""
        bloque = self._bloques.get(clave)
        if bloque is None:
            return
        if visible and not bloque.winfo_ismapped():
            posicion = self._orden.index(clave)
            despues = None
            for siguiente in self._orden[posicion + 1:]:
                candidato = self._bloques.get(siguiente)
                if candidato is not None and candidato.winfo_ismapped():
                    despues = candidato
                    break
            if despues is not None:
                bloque.pack(fill="x", before=despues)
            else:
                bloque.pack(fill="x")
        elif not visible and bloque.winfo_ismapped():
            bloque.pack_forget()

    # --- validación y cierre ---

    def _recoger(self) -> dict | None:
        recogido: dict = {}
        for campo in self.campos:
            if isinstance(campo, Nota):
                continue
            crudo = self.valor(campo.clave)

            if isinstance(campo, Importe):
                numero = texto_a_numero(crudo)
                if numero is None:
                    return self._fallo(f"«{campo.etiqueta}» tiene que ser un número.")
                if not campo.permitir_negativo and numero < 0:
                    return self._fallo(f"«{campo.etiqueta}» no puede ser negativo. "
                                       "El signo lo decide la categoría, no el número.")
                if not campo.permitir_cero and numero == 0:
                    return self._fallo(f"«{campo.etiqueta}» tiene que ser mayor que cero.")
                recogido[campo.clave] = numero

            elif isinstance(campo, Fecha):
                iso = texto_a_fecha(crudo)
                if iso is None:
                    return self._fallo(f"«{campo.etiqueta}» no es una fecha válida. "
                                       "Escríbela como 24/08/2026.")
                recogido[campo.clave] = iso

            elif isinstance(campo, Opcion):
                recogido[campo.clave] = "" if crudo == campo.vacio else crudo

            else:
                texto = crudo.strip()
                if campo.obligatorio and not texto:
                    return self._fallo(f"«{campo.etiqueta}» no puede quedar vacío.")
                recogido[campo.clave] = texto

        if self.validar:
            problema = self.validar(recogido)
            if problema:
                return self._fallo(problema)
        return recogido

    def _fallo(self, mensaje: str) -> None:
        self.error.configure(text=mensaje)
        self.bell()
        return None

    def _aceptar(self) -> None:
        recogido = self._recoger()
        if recogido is None:
            return
        self.resultado = recogido
        self.destroy()

    def _cancelar(self) -> None:
        self.resultado = None
        self.destroy()

    def mostrar(self) -> dict | None:
        self.update_idletasks()
        _centrar(self)
        self.grab_set()
        primero = next((self._controles[c.clave] for c in self.campos
                        if not isinstance(c, Nota) and c.clave in self._controles), None)
        if primero is not None:
            primero.focus_set()
        self.wait_window()
        return self.resultado


def _pista(control: ttk.Entry, variable: tk.StringVar, texto: str) -> None:
    """Texto de ejemplo en gris que desaparece al escribir."""
    gris, normal = widgets.PALETA.suave, widgets.PALETA.texto

    def poner():
        if not variable.get():
            variable.set(texto)
            control.configure(foreground=gris)

    def quitar(_evento=None):
        if variable.get() == texto:
            variable.set("")
        control.configure(foreground=normal)

    def revisar(_evento=None):
        if not variable.get():
            poner()

    poner()
    control.bind("<FocusIn>", quitar)
    control.bind("<FocusOut>", revisar)
    # Lo que quede como pista no cuenta como valor escrito.
    control.pista = texto


def _centrar(ventana: tk.Toplevel) -> None:
    padre = ventana.master
    ancho, alto = ventana.winfo_width(), ventana.winfo_height()
    x = padre.winfo_rootx() + (padre.winfo_width() - ancho) // 2
    y = padre.winfo_rooty() + (padre.winfo_height() - alto) // 3
    ventana.geometry(f"+{max(0, x)}+{max(0, y)}")


# --- confirmaciones --------------------------------------------------------

def confirmar(padre, mensaje: str, detalle: str = "", titulo: str = "ContaXcell") -> bool:
    return messagebox.askyesno(titulo, mensaje, detail=detalle, parent=padre,
                               icon=messagebox.WARNING, default=messagebox.NO)


def avisar(padre, mensaje: str, detalle: str = "", titulo: str = "ContaXcell") -> None:
    messagebox.showinfo(titulo, mensaje, detail=detalle, parent=padre)


def error(padre, mensaje: str, detalle: str = "", titulo: str = "ContaXcell") -> None:
    messagebox.showerror(titulo, mensaje, detail=detalle, parent=padre)
