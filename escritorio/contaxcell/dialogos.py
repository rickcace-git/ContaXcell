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
    # Si es opcional, dejarlo en blanco vale y devuelve None. Sirve para lo
    # que no se sabe todavía: «no lo sé» no es lo mismo que «vale cero», y
    # un cero devuelto aquí se confundiría con uno escrito a mano.
    opcional: bool = False


@dataclass
class Fecha:
    clave: str
    etiqueta: str
    valor: str = ""
    ayuda: str = ""
    # Si es opcional, dejarla en blanco vale y devuelve cadena vacía.
    opcional: bool = False


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
class Casilla:
    """Un sí o no. La etiqueta va al lado de la marca, no encima."""

    clave: str
    etiqueta: str
    valor: bool = False
    ayuda: str = ""


@dataclass
class Parrafo:
    """Un texto de varias líneas, para lo que no cabe en una casilla."""

    clave: str
    etiqueta: str
    valor: str = ""
    ayuda: str = ""
    obligatorio: bool = False
    lineas: int = 5


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
        # Qué campos están puestos. Se lleva a mano y no se le pregunta a
        # tkinter: mientras se construye el formulario la ventana todavía no
        # está dibujada y `winfo_ismapped` contesta que no a todo.
        self._visible: dict[str, bool] = {}

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
                self._visible[campo.clave] = True
            return

        if isinstance(campo, Casilla):
            variable = tk.BooleanVar(value=campo.valor)
            control = ttk.Checkbutton(bloque, text=campo.etiqueta, variable=variable,
                                      command=self._cambio)
            control.pack(anchor="w", pady=(10, 0))
            if campo.ayuda:
                ttk.Label(bloque, text=campo.ayuda, style="Tarjeta.Suave.TLabel",
                          wraplength=340, justify="left").pack(anchor="w", pady=(3, 0))
            self._variables[campo.clave] = variable
            self._controles[campo.clave] = control
            self._bloques[campo.clave] = bloque
            self._orden.append(campo.clave)
            self._visible[campo.clave] = True
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
        elif isinstance(campo, Parrafo):
            # `tk.Text` no es un widget con estilo: si no se le dicen la
            # fuente y los colores, sale con la letra de máquina de escribir y
            # un borde negro que no se parece en nada a las demás casillas. El
            # borde se hace con el «highlight» porque es el único que se puede
            # pintar del color de la paleta, y de paso se marca al escribir.
            control = tk.Text(bloque, height=campo.lineas, width=34, wrap="word",
                              font=widgets.FUENTES.normal,
                              relief="flat", borderwidth=0, padx=6, pady=5,
                              background=widgets.PALETA.campo,
                              foreground=widgets.PALETA.texto,
                              insertbackground=widgets.PALETA.texto,
                              highlightthickness=1,
                              highlightbackground=widgets.PALETA.borde,
                              highlightcolor=widgets.PALETA.acento)
            control.insert("1.0", campo.valor)
            control.pack(fill="x")
            # Dentro de un texto de varias líneas, Enter tiene que hacer una
            # línea nueva y no guardar el formulario. Se le quita la etiqueta
            # de la ventana en vez de atrapar la tecla, que eso impediría
            # también escribir el salto. Escape se vuelve a poner a mano.
            control.bindtags(tuple(t for t in control.bindtags() if t != str(self)))
            control.bind("<Escape>", lambda _e: self._cancelar())
            control.bind("<Tab>", _saltar_al_siguiente)
            variable = None
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
        self._visible[campo.clave] = True

    def _cambio(self) -> None:
        if self.al_cambiar:
            self.al_cambiar(self, None)

    # --- interfaz para quien lo usa ---

    def valor(self, clave: str) -> str:
        control = self._controles.get(clave)
        if isinstance(control, tk.Text):
            # Un texto de varias líneas no tiene variable detrás: se lee del
            # propio control, desde el principio hasta el último carácter.
            return control.get("1.0", "end-1c")
        variable = self._variables.get(clave)
        if variable is None:
            return ""
        # El texto de ejemplo en gris no es algo que haya escrito el usuario.
        # Se pregunta si está puesto, no se compara con lo escrito: si no,
        # teclear «Gimnasio» en un campo cuyo ejemplo es «Gimnasio» pasaría
        # por no haber escrito nada.
        if getattr(self._controles.get(clave), "pista_puesta", False):
            return ""
        return variable.get()

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
        if bloque is None or self._visible.get(clave, True) == visible:
            return
        self._visible[clave] = visible

        if not visible:
            bloque.pack_forget()
            return

        # Vuelve a su hueco, delante del primer campo visible que va después.
        posicion = self._orden.index(clave)
        despues = next((self._bloques[siguiente]
                        for siguiente in self._orden[posicion + 1:]
                        if siguiente in self._bloques and self._visible.get(siguiente)),
                       None)
        if despues is not None:
            bloque.pack(fill="x", before=despues)
        else:
            bloque.pack(fill="x")

    def campo_visible(self, clave: str) -> bool:
        return self._visible.get(clave, False)

    # --- validación y cierre ---

    def _recoger(self) -> dict | None:
        recogido: dict = {}
        for campo in self.campos:
            if isinstance(campo, Nota):
                continue
            crudo = self.valor(campo.clave)

            if isinstance(campo, Importe):
                if campo.opcional and not crudo.strip():
                    # None y no cero: «no lo sé» no es «vale cero», y quien
                    # lo reciba tiene que poder distinguirlo.
                    recogido[campo.clave] = None
                    continue
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
                if campo.opcional and not crudo.strip():
                    recogido[campo.clave] = ""
                    continue
                iso = texto_a_fecha(crudo)
                if iso is None:
                    return self._fallo(f"«{campo.etiqueta}» no es una fecha válida. "
                                       "Escríbela como 24/08/2026.")
                recogido[campo.clave] = iso

            elif isinstance(campo, Casilla):
                recogido[campo.clave] = bool(crudo)

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


def _saltar_al_siguiente(evento):
    """El tabulador sale del texto en vez de meter una tabulación dentro.

    Un `tk.Text` se queda con el tabulador, y en un formulario eso rompe la
    costumbre de ir de casilla en casilla sin tocar el ratón.
    """
    evento.widget.tk_focusNext().focus_set()
    return "break"


def _pista(control: ttk.Entry, variable: tk.StringVar, texto: str) -> None:
    """Texto de ejemplo en gris que desaparece al escribir.

    La casilla lleva apuntado si lo que se ve es el ejemplo (`pista_puesta`)
    en vez de reconocerlo comparando el texto. Comparándolo, escribir el
    ejemplo se tomaba por no haber escrito nada, y llamar «Gimnasio» a un
    gimnasio o «Fondo indexado» a un fondo indexado daba «no puede quedar
    vacío».
    """
    gris, normal = widgets.PALETA.suave, widgets.PALETA.texto

    def poner():
        if not variable.get():
            variable.set(texto)
            control.configure(foreground=gris)
            control.pista_puesta = True

    def quitar(_evento=None):
        if control.pista_puesta:
            variable.set("")
            control.pista_puesta = False
        control.configure(foreground=normal)

    def revisar(_evento=None):
        if not variable.get():
            poner()

    control.pista_puesta = False
    poner()
    control.bind("<FocusIn>", quitar)
    control.bind("<FocusOut>", revisar)


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


# --- explicaciones -----------------------------------------------------------

class Explicacion(tk.Toplevel):
    """La ventanita que se abre al pulsar la interrogación de una cifra.

    Enseña la cuenta con los números del propio usuario en vez de con la
    fórmula en abstracto: «5.232,98 / 123,19 = 42,5 meses» se entiende de un
    vistazo, y «saldo entre gasto medio» no.
    """

    # Todo el texto se corta a este ancho: si cada bloque eligiera el suyo,
    # el más largo decidiría el tamaño de la ventana.
    ANCHO = 420

    def __init__(self, padre, titulo: str, resumen: str, cuenta: list[tuple],
                 detalle: str = "", aviso: str = ""):
        super().__init__(padre)
        self.title(titulo)
        self.resizable(False, False)
        self.configure(background=widgets.PALETA.tarjeta)
        self.transient(padre)

        cuerpo = ttk.Frame(self, style="Tarjeta.TFrame", padding=20)
        cuerpo.pack(fill="both", expand=True)

        ttk.Label(cuerpo, text=titulo, style="Tarjeta.Negrita.TLabel").pack(anchor="w")
        ttk.Label(cuerpo, text=resumen, style="Tarjeta.TLabel",
                  wraplength=self.ANCHO, justify="left").pack(anchor="w", pady=(6, 0))

        if cuenta:
            self._cuenta(cuerpo, cuenta)

        if detalle:
            ttk.Label(cuerpo, text=detalle, style="Tarjeta.Suave.TLabel",
                      wraplength=self.ANCHO, justify="left").pack(anchor="w", pady=(14, 0))

        if aviso:
            widgets.Aviso(cuerpo, aviso, "alerta",
                          ancho=self.ANCHO - 24).pack(fill="x", pady=(14, 0))

        ttk.Button(cuerpo, text="Entendido", style="Principal.TButton",
                   command=self.destroy).pack(anchor="e", pady=(18, 0))

        self.bind("<Return>", lambda _e: self.destroy())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _cuenta(self, padre, filas: list[tuple]) -> None:
        """La cuenta, línea a línea. Una fila con `None` de valor es un
        separador: debajo va el resultado."""
        marco = tk.Frame(padre, background=widgets.PALETA.borde)
        marco.pack(fill="x", pady=(14, 0))
        rejilla = ttk.Frame(marco, style="Hundido.TFrame", padding=(14, 12))
        rejilla.pack(fill="both", expand=True, padx=1, pady=1)
        rejilla.columnconfigure(0, weight=1)

        linea = 0
        for concepto, valor in filas:
            if valor is None:
                tk.Frame(rejilla, background=widgets.PALETA.borde, height=1).grid(
                    row=linea, column=0, columnspan=2, sticky="ew", pady=(8, 8))
                linea += 1
                continue
            ultima = (concepto, valor) == filas[-1]
            estilo = "Hundido.Negrita.TLabel" if ultima else "Hundido.TLabel"
            ttk.Label(rejilla, text=concepto, style="Hundido.Suave.TLabel"
                      if not ultima else estilo).grid(row=linea, column=0, sticky="w")
            ttk.Label(rejilla, text=valor, style=estilo).grid(
                row=linea, column=1, sticky="e", padx=(24, 0))
            linea += 1

    def mostrar(self) -> None:
        self.update_idletasks()
        _centrar(self)
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.wait_window()
