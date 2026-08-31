"""Piezas de interfaz que se repiten en varias pantallas.

Tkinter no trae tarjetas, ni barras de proporción, ni gráficos, así que se
construyen aquí una vez y las vistas se limitan a usarlas.
"""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date
from tkinter import ttk

from .tema import Fuentes, Paleta

# La paleta y las fuentes en uso. Se fijan al arrancar y cada vez que se
# cambia de tema, que rehace la ventana entera.
PALETA: Paleta | None = None
FUENTES: Fuentes | None = None


def usar(paleta: Paleta, fuentes: Fuentes) -> None:
    global PALETA, FUENTES
    PALETA, FUENTES = paleta, fuentes


# --- contenedores ----------------------------------------------------------

class Tarjeta(ttk.Frame):
    """Un bloque con borde, título opcional y sitio a la derecha del título
    para meter un botón o un desplegable.

    El borde es un marco de un píxel de color: ttk no deja poner el color del
    borde de un Frame de forma fiable en todas las versiones.
    """

    def __init__(self, padre, titulo: str | None = None, **kw):
        self.marco = tk.Frame(padre, background=PALETA.borde)
        super().__init__(self.marco, style="Tarjeta.TFrame", padding=14, **kw)
        super().pack(fill="both", expand=True, padx=1, pady=1)

        self.cabecera: ttk.Frame | None = None
        self.derecha: ttk.Frame | None = None
        self.cuerpo = ttk.Frame(self, style="Tarjeta.TFrame")

        if titulo is not None:
            self.cabecera = ttk.Frame(self, style="Tarjeta.TFrame")
            self.cabecera.pack(fill="x", pady=(0, 10))
            self.etiqueta_titulo = ttk.Label(
                self.cabecera, text=titulo.upper(), style="Tarjeta.Titulo.TLabel")
            self.etiqueta_titulo.pack(side="left")
            self.derecha = ttk.Frame(self.cabecera, style="Tarjeta.TFrame")
            self.derecha.pack(side="right")

        self.cuerpo.pack(fill="both", expand=True)

    def titulo(self, texto: str) -> None:
        if self.cabecera is not None:
            self.etiqueta_titulo.configure(text=texto.upper())

    # El widget que hay que colocar es el marco exterior, no la tarjeta.
    def pack(self, **kw):
        self.marco.pack(**kw)
        return self

    def grid(self, **kw):
        self.marco.grid(**kw)
        return self

    # Y el que hay que quitar, también: quitando solo la tarjeta se queda el
    # marco puesto, vacío y con el alto que tenía, como un hueco gris.
    def pack_forget(self) -> None:
        self.marco.pack_forget()

    def grid_forget(self) -> None:
        self.marco.grid_forget()

    def destruir(self) -> None:
        self.marco.destroy()


class MarcoDesplazable(ttk.Frame):
    """Un marco con barra de desplazamiento vertical.

    Las pantallas de resumen e inversiones son más altas que la ventana, así
    que su contenido va dentro de `interior`.
    """

    def __init__(self, padre, **kw):
        super().__init__(padre, **kw)
        self.lienzo = tk.Canvas(self, highlightthickness=0, background=PALETA.fondo,
                                borderwidth=0)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.lienzo.yview)
        self.lienzo.configure(yscrollcommand=self._al_desplazar)

        self.lienzo.pack(side="left", fill="both", expand=True)
        self.interior = ttk.Frame(self.lienzo)
        self._ventana = self.lienzo.create_window((0, 0), window=self.interior, anchor="nw")

        self.interior.bind("<Configure>", self._interior_cambio)
        self.lienzo.bind("<Configure>", self._lienzo_cambio)
        # La rueda solo mueve esta zona mientras el ratón esté encima, para no
        # secuestrar el desplazamiento de las tablas.
        self.lienzo.bind("<Enter>", lambda _e: self.lienzo.bind_all("<MouseWheel>", self._rueda))
        self.lienzo.bind("<Leave>", lambda _e: self.lienzo.unbind_all("<MouseWheel>"))

    def _al_desplazar(self, primero, ultimo):
        # La barra solo aparece cuando hace falta.
        if float(primero) <= 0.0 and float(ultimo) >= 1.0:
            self.barra.pack_forget()
        else:
            self.barra.pack(side="right", fill="y")
        self.barra.set(primero, ultimo)

    def _interior_cambio(self, _evento=None):
        self.lienzo.configure(scrollregion=self.lienzo.bbox("all"))

    def _lienzo_cambio(self, evento):
        self.lienzo.itemconfigure(self._ventana, width=evento.width)

    def _rueda(self, evento):
        if self.lienzo.bbox("all") is None:
            return
        alto_contenido = self.lienzo.bbox("all")[3]
        if alto_contenido <= self.lienzo.winfo_height():
            return
        self.lienzo.yview_scroll(-1 * (evento.delta // 120), "units")

    def arriba(self) -> None:
        self.lienzo.yview_moveto(0)


# --- textos y cifras -------------------------------------------------------

class BotonAyuda(tk.Canvas):
    """La interrogación pequeña que abre la explicación de una cifra.

    Se dibuja en un lienzo en lugar de usar un botón con el texto «?» porque
    así el círculo queda del tamaño justo y no arrastra el relleno que ttk le
    pone a los botones, que aquí desencuadraría la casilla.
    """

    LADO = 17

    def __init__(self, padre, comando, fondo: str | None = None):
        self.fondo = fondo or PALETA.hundido
        super().__init__(padre, width=self.LADO, height=self.LADO,
                         highlightthickness=0, background=self.fondo,
                         borderwidth=0, cursor="hand2")
        self.comando = comando
        self._encima = False
        self.bind("<Button-1>", lambda _e: self.comando())
        self.bind("<Enter>", lambda _e: self._resaltar(True))
        self.bind("<Leave>", lambda _e: self._resaltar(False))
        self.pintar()

    def cambiar_comando(self, comando) -> None:
        self.comando = comando

    def _resaltar(self, encima: bool) -> None:
        self._encima = encima
        self.pintar()

    def pintar(self) -> None:
        self.delete("all")
        color = PALETA.acento if self._encima else PALETA.suave
        borde = 1.4 if self._encima else 1.0
        self.create_oval(borde, borde, self.LADO - borde, self.LADO - borde,
                         outline=color, width=borde)
        self.create_text(self.LADO / 2, self.LADO / 2 + 0.5, text="?",
                         fill=color, font=FUENTES.diminuta)


class Cifra(ttk.Frame):
    """Una casilla con un rótulo pequeño, un número grande y una nota.

    Si se le pasa `ayuda`, aparece una interrogación junto al rótulo que la
    llama al pulsarla. Se usa en los indicadores que se calculan de una forma
    que no es evidente y conviene poder consultar.
    """

    def __init__(self, padre, rotulo: str, valor: str = "", color: str = "",
                 nota: str = "", ayuda=None, **kw):
        super().__init__(padre, style="Hundido.TFrame", padding=(12, 10), **kw)

        cabecera = ttk.Frame(self, style="Hundido.TFrame")
        cabecera.pack(fill="x")
        self.etiqueta_rotulo = ttk.Label(cabecera, text=rotulo.upper(),
                                         style="Hundido.Titulo.TLabel")
        self.etiqueta_rotulo.pack(side="left")

        self.boton_ayuda = None
        if ayuda is not None:
            self.boton_ayuda = BotonAyuda(cabecera, ayuda)
            self.boton_ayuda.pack(side="right", padx=(6, 0))

        self.etiqueta_valor = ttk.Label(
            self, text=valor, style=f"Hundido.Grande{color}.TLabel")
        self.etiqueta_valor.pack(anchor="w", pady=(2, 0))
        self.etiqueta_nota = ttk.Label(self, text=nota, style="Hundido.Suave.TLabel",
                                       wraplength=190, justify="left")
        if nota:
            self.etiqueta_nota.pack(anchor="w")

    def actualizar(self, valor: str, color: str = "", nota: str | None = None,
                   ayuda=None, rotulo: str | None = None) -> None:
        # El rótulo también cambia: la misma casilla dice «gastos del año» o
        # «gastos del mes» según lo que se esté mirando.
        if rotulo is not None:
            self.etiqueta_rotulo.configure(text=rotulo.upper())
        self.etiqueta_valor.configure(text=valor, style=f"Hundido.Grande{color}.TLabel")
        # La explicación se rehace en cada refresco porque lleva dentro las
        # cifras del momento; hay que cambiarle el gatillo al botón.
        if ayuda is not None and self.boton_ayuda is not None:
            self.boton_ayuda.cambiar_comando(ayuda)
        if nota is not None:
            self.etiqueta_nota.configure(text=nota)
            if nota and not self.etiqueta_nota.winfo_ismapped():
                self.etiqueta_nota.pack(anchor="w")
            elif not nota and self.etiqueta_nota.winfo_ismapped():
                self.etiqueta_nota.pack_forget()


class PanelCifras(ttk.Frame):
    """Una rejilla de `Cifra` que se reparte el ancho por igual."""

    def __init__(self, padre, columnas: int = 4, fondo: str = "Tarjeta", **kw):
        super().__init__(padre, style=f"{fondo}.TFrame", **kw)
        self.columnas = columnas
        self._cifras: dict[str, Cifra] = {}
        for indice in range(columnas):
            self.columnconfigure(indice, weight=1, uniform="cifras")

    def poner(self, clave: str, rotulo: str, valor: str, color: str = "",
              nota: str = "", ayuda=None) -> None:
        """Crea la casilla la primera vez y la actualiza las siguientes, para
        no destruir y rehacer widgets en cada refresco."""
        if clave in self._cifras:
            self._cifras[clave].actualizar(valor, color, nota, ayuda, rotulo)
            return
        posicion = len(self._cifras)
        cifra = Cifra(self, rotulo, valor, color, nota, ayuda)
        cifra.grid(row=posicion // self.columnas, column=posicion % self.columnas,
                   sticky="nsew", padx=(0, 8), pady=(0, 8))
        self._cifras[clave] = cifra

    def limpiar(self) -> None:
        for cifra in self._cifras.values():
            cifra.destroy()
        self._cifras.clear()


class Aviso(ttk.Frame):
    """Una nota de color para lo que conviene que el usuario lea."""

    COLORES = {"info": "acento", "alerta": "aviso", "malo": "gasto"}

    def __init__(self, padre, texto: str, clase: str = "info",
                 ancho: int = 760, **kw):
        color = getattr(PALETA, self.COLORES.get(clase, "acento"))
        self.marco = tk.Frame(padre, background=color)
        super().__init__(self.marco, padding=(11, 9), **kw)
        super().pack(fill="both", expand=True, padx=(3, 1), pady=1)
        self.configure(style="Tarjeta.TFrame")
        etiqueta = ttk.Label(self, text=texto, style="Tarjeta.TLabel",
                             foreground=color, wraplength=ancho, justify="left")
        etiqueta.pack(anchor="w")

    def pack(self, **kw):
        self.marco.pack(**kw)
        return self

    def destruir(self) -> None:
        self.marco.destroy()


# --- barras y gráficos -----------------------------------------------------

class Barra(tk.Canvas):
    """Barra de proporción. Con `semaforo` cambia de color: verde mientras
    sobra presupuesto, ámbar cuando aprieta y rojo si se ha pasado."""

    def __init__(self, padre, ancho: int = 110, alto: int = 8, fondo: str | None = None):
        super().__init__(padre, width=ancho, height=alto, highlightthickness=0,
                         background=fondo or PALETA.tarjeta, borderwidth=0)
        self._ancho, self._alto = ancho, alto

    def dibujar(self, fraccion: float, semaforo: bool = False) -> None:
        self.delete("all")
        radio = self._alto / 2
        self._redondeada(0, self._ancho, PALETA.hundido, radio)

        if fraccion != fraccion:  # NaN
            return
        pasado = fraccion > 1 or fraccion == float("inf")
        visible = 1.0 if pasado else max(0.0, fraccion)
        if visible <= 0:
            return

        if semaforo:
            color = PALETA.gasto if pasado else (
                PALETA.aviso if fraccion > 0.85 else PALETA.ingreso)
        else:
            color = PALETA.acento
        self._redondeada(0, max(self._alto, self._ancho * visible), color, radio)

    def _redondeada(self, x1: float, x2: float, color: str, radio: float) -> None:
        if x2 - x1 < radio * 2:
            self.create_oval(x1, 0, x1 + radio * 2, self._alto, fill=color, outline="")
            return
        self.create_oval(x1, 0, x1 + radio * 2, self._alto, fill=color, outline="")
        self.create_oval(x2 - radio * 2, 0, x2, self._alto, fill=color, outline="")
        self.create_rectangle(x1 + radio, 0, x2 - radio, self._alto, fill=color, outline="")


class Grafico(tk.Canvas):
    """Base de los gráficos: se redibuja solo cuando cambia de tamaño."""

    def __init__(self, padre, alto: int = 190, **kw):
        super().__init__(padre, height=alto, highlightthickness=0,
                         background=PALETA.tarjeta, borderwidth=0, **kw)
        self._alto = alto
        self._datos = None
        self.bind("<Configure>", lambda _e: self._pintar())

    def dibujar(self, datos) -> None:
        self._datos = datos
        self._pintar()

    def _pintar(self) -> None:
        self.delete("all")
        if not self._datos:
            return
        ancho = self.winfo_width()
        if ancho <= 1:  # todavía no se ha colocado
            return
        self._pintar_datos(ancho, self._alto)

    def _pintar_datos(self, ancho: int, alto: int) -> None:
        raise NotImplementedError


class GraficoBarras(Grafico):
    """Barras agrupadas: ingresos, gastos e inversión de cada mes.

    Sin números en los ejes a propósito: para la cifra exacta está la tabla de
    debajo, y aquí lo que interesa es la forma del año.
    """

    def _pintar_datos(self, ancho: int, alto: int) -> None:
        etiquetas, series = self._datos
        maximo = max((max(valores) for _, _, valores in series if valores), default=0)
        if maximo <= 0:
            return

        base = alto - 18
        ancho_grupo = ancho / max(1, len(etiquetas))
        ancho_barra = min(14, max(3, (ancho_grupo - 10) / len(series)))
        hueco = 2

        self.create_line(0, base, ancho, base, fill=PALETA.borde)

        for indice, etiqueta in enumerate(etiquetas):
            centro = indice * ancho_grupo + ancho_grupo / 2
            total_ancho = len(series) * ancho_barra + (len(series) - 1) * hueco
            inicio = centro - total_ancho / 2

            for posicion, (_nombre, color, valores) in enumerate(series):
                valor = valores[indice] if indice < len(valores) else 0
                if valor <= 0:
                    continue
                altura = max(2, (valor / maximo) * (base - 6))
                x1 = inicio + posicion * (ancho_barra + hueco)
                self.create_rectangle(x1, base - altura, x1 + ancho_barra, base,
                                      fill=color, outline="")

            self.create_text(centro, alto - 8, text=etiqueta, fill=PALETA.suave,
                             font=FUENTES.diminuta)


class GraficoLineas(Grafico):
    """Dos líneas: lo que vale la cartera y lo que llevas aportado.

    El eje horizontal es el tiempo real, no la posición en la lista: si dejas
    tres meses sin apuntar, el hueco se ve.

    Con `marcas` se pone un punto en cada dato. Va bien con las valoraciones,
    que son unas pocas y se apuntan a mano, y estorba con una cotización
    diaria: cuarenta puntos seguidos no dicen nada y tapan la línea.

    Con `desde_cero` el eje empieza en cero, que es lo que hay que hacer con
    el dinero para no exagerar una subida pequeña. Para un precio hay que
    apagarlo: entre 126 y 128 euros no se vería nada.
    """

    def __init__(self, padre, alto: int = 190, marcas: bool = True,
                 desde_cero: bool = True, **kw):
        super().__init__(padre, alto=alto, **kw)
        self.marcas = marcas
        self.desde_cero = desde_cero

    def _pintar_datos(self, ancho: int, alto: int) -> None:
        puntos = self._datos
        if len(puntos) < 2:
            return

        margen_lados, arriba, abajo = 10, 12, 22
        dias = [d for d, _, _ in puntos]
        min_dia, max_dia = min(dias), max(dias)
        rango_dias = max(1, max_dia - min_dia)

        valores = [v for _, a, v in puntos] + [a for _, a, _ in puntos]
        if self.desde_cero:
            # Para dinero, el cero tiene que verse: si no, una cartera que ha
            # subido un 2 % parece que se ha disparado.
            maximo, minimo = max(valores), min(min(valores), 0)
        else:
            # Para un precio, arrancar en cero aplasta la linea contra el
            # techo: 126 y 128 euros serian la misma raya. Se ajusta a lo que
            # hay, con un respiro arriba y abajo.
            maximo, minimo = max(valores), min(valores)
            respiro = max((maximo - minimo) * 0.15, maximo * 0.002)
            maximo, minimo = maximo + respiro, minimo - respiro
        rango = max(1e-9, maximo - minimo)

        def x_de(dia):
            return margen_lados + (dia - min_dia) / rango_dias * (ancho - margen_lados * 2)

        def y_de(valor):
            return arriba + (1 - (valor - minimo) / rango) * (alto - arriba - abajo)

        self.create_line(margen_lados, alto - abajo, ancho - margen_lados, alto - abajo,
                         fill=PALETA.borde)

        aportado = [c for dia, ap, _ in puntos for c in (x_de(dia), y_de(ap))]
        valor = [c for dia, _, val in puntos for c in (x_de(dia), y_de(val))]
        self.create_line(*aportado, fill=PALETA.suave, width=2, dash=(4, 3), smooth=False)
        self.create_line(*valor, fill=PALETA.acento, width=3, smooth=False)

        if self.marcas:
            for dia, _, val in puntos:
                x, y = x_de(dia), y_de(val)
                self.create_oval(x - 4, y - 4, x + 4, y + 4,
                                 fill=PALETA.acento, outline=PALETA.tarjeta, width=2)


class Leyenda(ttk.Frame):
    def __init__(self, padre, entradas: list[tuple[str, str]], fondo: str = "Tarjeta", **kw):
        super().__init__(padre, style=f"{fondo}.TFrame", **kw)
        for color, texto in entradas:
            bloque = ttk.Frame(self, style=f"{fondo}.TFrame")
            bloque.pack(side="left", padx=(0, 16))
            punto = tk.Canvas(bloque, width=10, height=10, highlightthickness=0,
                              background=getattr(PALETA, fondo.lower(), PALETA.tarjeta))
            punto.create_rectangle(0, 1, 10, 10, fill=color, outline="")
            punto.pack(side="left", padx=(0, 5))
            ttk.Label(bloque, text=texto, style=f"{fondo}.Suave.TLabel").pack(side="left")


# --- tablas ----------------------------------------------------------------

class Columna:
    def __init__(self, clave: str, titulo: str, ancho: int = 110,
                 anclaje: str = "w", estira: bool = False):
        self.clave = clave
        self.titulo = titulo
        self.ancho = ancho
        self.anclaje = anclaje
        self.estira = estira


class Tabla(ttk.Frame):
    """Envoltorio de Treeview con barras, colores por fila y doble clic.

    Los colores van por fila y no por celda porque Treeview no sabe pintar
    celdas sueltas. Donde hace falta distinguir ingreso de gasto se usan dos
    columnas distintas, igual que en la hoja de cálculo.
    """

    def __init__(self, padre, columnas: list[Columna], alto: int = 12,
                 al_activar=None, seleccion: str = "browse", al_elegir=None, **kw):
        super().__init__(padre, style="Tarjeta.TFrame", **kw)
        self.columnas = columnas
        self._al_activar = al_activar

        claves = [c.clave for c in columnas]
        self.arbol = ttk.Treeview(self, columns=claves, show="headings",
                                  height=alto, selectmode=seleccion)
        for columna in columnas:
            self.arbol.heading(columna.clave, text=columna.titulo,
                               anchor="e" if columna.anclaje == "e" else "w")
            self.arbol.column(columna.clave, width=columna.ancho, anchor=columna.anclaje,
                              stretch=columna.estira, minwidth=40)

        self.vertical = ttk.Scrollbar(self, orient="vertical", command=self.arbol.yview)
        self.horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.arbol.xview)
        self.arbol.configure(yscrollcommand=self._mover_vertical,
                             xscrollcommand=self._mover_horizontal)

        self.arbol.grid(row=0, column=0, sticky="nsew")
        self.vertical.grid(row=0, column=1, sticky="ns")
        self.horizontal.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        for nombre, color in (("ingreso", PALETA.ingreso), ("gasto", PALETA.gasto),
                              ("inversion", PALETA.inversion), ("suave", PALETA.suave),
                              ("aviso", PALETA.aviso)):
            self.arbol.tag_configure(nombre, foreground=color)
        self.arbol.tag_configure("total", font=FUENTES.negrita)
        # Franjas alternas. Solo tocan el fondo, así que se llevan bien con
        # las etiquetas de color, que solo tocan la letra: una fila puede ir
        # con las dos. Con seis columnas, el ojo no se va de fila.
        self.arbol.tag_configure("franja", background=PALETA.hundido)

        if al_activar:
            self.arbol.bind("<Double-1>", self._activar)
            self.arbol.bind("<Return>", self._activar)
        if al_elegir:
            # Para los botones que cambian de nombre según la fila elegida.
            self.arbol.bind("<<TreeviewSelect>>", lambda _e: al_elegir())

    def _mover_vertical(self, primero, ultimo):
        self._ajustar(self.vertical, primero, ultimo)

    def _mover_horizontal(self, primero, ultimo):
        self._ajustar(self.horizontal, primero, ultimo)

    @staticmethod
    def _ajustar(barra, primero, ultimo):
        """Enseña la barra solo si sobra contenido por ese lado."""
        if float(primero) <= 0.0 and float(ultimo) >= 1.0:
            barra.grid_remove()
        else:
            barra.grid()
        barra.set(primero, ultimo)

    def _activar(self, _evento=None):
        clave = self.seleccion()
        if clave is not None:
            self._al_activar(clave)

    def poner(self, filas: list[tuple]) -> None:
        """`filas` es una lista de (clave, valores, etiquetas)."""
        self.arbol.delete(*self.arbol.get_children())
        for numero, (clave, valores, etiquetas) in enumerate(filas):
            marcas = tuple(etiquetas or ())
            if numero % 2:
                marcas += ("franja",)
            self.arbol.insert("", "end", iid=str(clave), values=valores, tags=marcas)

    def titulo_columna(self, clave: str, texto: str) -> None:
        """Cambia la cabecera de una columna sin rehacer la tabla.

        La misma tabla enseña meses o años según lo que se esté mirando, y la
        cabecera tiene que decir cuál de los dos.
        """
        columna = next((c for c in self.columnas if c.clave == clave), None)
        if columna is None:
            return
        self.arbol.heading(clave, text=texto,
                           anchor="e" if columna.anclaje == "e" else "w")

    def seleccion(self) -> str | None:
        elegido = self.arbol.selection()
        return elegido[0] if elegido else None

    def ajustar_alto(self, filas: int, minimo: int = 3, maximo: int = 25) -> None:
        self.arbol.configure(height=max(minimo, min(maximo, filas)))


# --- formularios -----------------------------------------------------------

class Calendario(tk.Toplevel):
    """Calendario para elegir el día con el ratón.

    Tkinter no trae ninguno y meter una dependencia solo por esto no compensa,
    así que se dibuja con etiquetas: siete columnas y hasta seis filas, que es
    lo que necesita el mes más largo.

    La semana empieza en lunes, como aquí.
    """

    DIAS = ("L", "M", "X", "J", "V", "S", "D")
    LADO = 30

    def __init__(self, padre, iso: str, al_elegir):
        super().__init__(padre)
        self.al_elegir = al_elegir
        # Quién tenía agarrado el ratón antes, para devolvérselo al cerrar.
        self.agarraba = None
        self.hoy = date.today()
        self.elegido = _a_fecha(iso)
        self.mes = (self.elegido or self.hoy).replace(day=1)

        # Sin barra de título: es un desplegable, no una ventana.
        self.wm_overrideredirect(True)
        self.configure(background=PALETA.borde)
        self.marco = tk.Frame(self, background=PALETA.tarjeta)
        self.marco.pack(padx=1, pady=1)

        self._cabecera()
        self.rejilla = tk.Frame(self.marco, background=PALETA.tarjeta)
        self.rejilla.pack(padx=10)
        self._pie()
        self._pintar()

        self.bind("<Escape>", lambda _e: self.cerrar())
        # Con el ratón agarrado, un clic fuera llega igual aquí, pero con
        # coordenadas de fuera: así se cierra al pinchar en otro sitio.
        self.bind("<Button-1>", self._quizas_fuera)

    # --- montaje ---

    def _cabecera(self) -> None:
        fila = tk.Frame(self.marco, background=PALETA.tarjeta)
        fila.pack(fill="x", padx=10, pady=(8, 6))
        self._flecha(fila, "‹", -1).pack(side="left")
        self.titulo = tk.Label(fila, background=PALETA.tarjeta, foreground=PALETA.texto,
                               font=FUENTES.negrita, width=16)
        self.titulo.pack(side="left", expand=True)
        self._flecha(fila, "›", 1).pack(side="right")

    def _flecha(self, padre, signo: str, salto: int) -> tk.Label:
        flecha = tk.Label(padre, text=signo, background=PALETA.tarjeta,
                          foreground=PALETA.suave, font=FUENTES.negrita,
                          width=2, cursor="hand2")
        flecha.bind("<Button-1>", lambda _e: self._mover(salto))
        _al_pasar(flecha, PALETA.hundido, PALETA.tarjeta)
        return flecha

    def _pie(self) -> None:
        pie = tk.Frame(self.marco, background=PALETA.tarjeta)
        pie.pack(fill="x", padx=10, pady=(4, 8))
        hoy = tk.Label(pie, text="Hoy", background=PALETA.tarjeta,
                       foreground=PALETA.acento, font=FUENTES.pequena,
                       cursor="hand2", padx=6, pady=2)
        hoy.pack(side="right")
        hoy.bind("<Button-1>", lambda _e: self._elegir(self.hoy))
        _al_pasar(hoy, PALETA.hundido, PALETA.tarjeta)

    # --- pintado ---

    def _mover(self, salto: int) -> None:
        mes = self.mes.month + salto
        anio = self.mes.year + (mes - 1) // 12
        self.mes = date(anio, (mes - 1) % 12 + 1, 1)
        self._pintar()

    def _pintar(self) -> None:
        from .modelo import MESES

        self.titulo.configure(text=f"{MESES[self.mes.month - 1]} {self.mes.year}".capitalize())
        for hijo in self.rejilla.winfo_children():
            hijo.destroy()

        for columna, inicial in enumerate(self.DIAS):
            tk.Label(self.rejilla, text=inicial, background=PALETA.tarjeta,
                     foreground=PALETA.suave, font=FUENTES.diminuta,
                     width=3).grid(row=0, column=columna, pady=(0, 2))

        semanas = calendar.Calendar(firstweekday=0).monthdayscalendar(
            self.mes.year, self.mes.month)
        for fila, semana in enumerate(semanas, start=1):
            for columna, numero in enumerate(semana):
                if numero == 0:
                    continue  # días del mes de al lado: se dejan en blanco
                self._dia(date(self.mes.year, self.mes.month, numero)).grid(
                    row=fila, column=columna)

    def _dia(self, fecha) -> tk.Label:
        if fecha == self.elegido:
            fondo, color, fuente = PALETA.acento, "#ffffff", FUENTES.negrita
        elif fecha == self.hoy:
            fondo, color, fuente = PALETA.hundido, PALETA.acento, FUENTES.negrita
        else:
            fondo, color, fuente = PALETA.tarjeta, PALETA.texto, FUENTES.normal

        celda = tk.Label(self.rejilla, text=str(fecha.day), background=fondo,
                         foreground=color, font=fuente, width=3, pady=3,
                         cursor="hand2")
        celda.bind("<Button-1>", lambda _e, f=fecha: self._elegir(f))
        if fecha != self.elegido:
            _al_pasar(celda, PALETA.boton, fondo)
        return celda

    # --- cierre ---

    def _elegir(self, fecha) -> None:
        self.al_elegir(fecha.isoformat())
        self.cerrar()

    def _quizas_fuera(self, evento) -> None:
        dentro = (0 <= evento.x < self.winfo_width()
                  and 0 <= evento.y < self.winfo_height())
        if not dentro:
            self.cerrar()

    def cerrar(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()
        # Si el calendario se abrió dentro de un formulario, ese formulario
        # tenía agarrado el ratón y hay que devolvérselo: si no, al cerrar el
        # calendario la ventana de detrás se volvería pulsable con el
        # formulario todavía abierto.
        if self.agarraba is not None:
            try:
                if self.agarraba.winfo_exists():
                    self.agarraba.grab_set()
            except tk.TclError:
                pass

    def abrir_junto_a(self, widget: tk.Widget) -> None:
        """Lo coloca debajo del campo, sin salirse de la pantalla."""
        self.update_idletasks()
        x = widget.winfo_rootx()
        y = widget.winfo_rooty() + widget.winfo_height() + 2
        if y + self.winfo_height() > self.winfo_screenheight():
            y = widget.winfo_rooty() - self.winfo_height() - 2
        x = min(x, self.winfo_screenwidth() - self.winfo_width() - 8)
        self.wm_geometry(f"+{max(0, x)}+{max(0, y)}")
        try:
            self.agarraba = self.grab_current()
            self.grab_set()
        except tk.TclError:
            self.agarraba = None


class CampoFecha(ttk.Frame):
    """Casilla de fecha en dd/mm/aaaa con un calendario al lado.

    No deja teclear letras: en una fecha no pintan nada, y rechazarlas
    mientras se escribe evita tener que dar un error después. Se sigue
    admitiendo casi cualquier separador, que es cómodo para quien teclea
    rápido, y el botón abre un calendario para quien prefiera el ratón.
    """

    # Todo lo que puede aparecer en una fecha escrita y nada más.
    PERMITIDOS = set("0123456789/-.")
    LARGO = 10  # «24/08/2026» y «2026-08-24» miden lo mismo

    def __init__(self, padre, valor_iso: str = "", fondo: str = "Tarjeta", **kw):
        super().__init__(padre, style=f"{fondo}.TFrame")
        self.variable = tk.StringVar()
        self.calendario: Calendario | None = None
        comprobante = self.register(self._admite)
        self.entrada = ttk.Entry(self, textvariable=self.variable, width=12,
                                 validate="key", validatecommand=(comprobante, "%P"),
                                 **kw)
        self.entrada.pack(side="left")
        self.boton = BotonIcono(self, "calendario", self.abrir_calendario, lado=27,
                                fondo=getattr(PALETA, fondo.lower(), PALETA.tarjeta))
        self.boton.pack(side="left", padx=(4, 0))
        self.poner(valor_iso)

    def _admite(self, propuesto: str) -> bool:
        return len(propuesto) <= self.LARGO and set(propuesto) <= self.PERMITIDOS

    def iso(self) -> str | None:
        from .formato import texto_a_fecha
        return texto_a_fecha(self.variable.get())

    def poner(self, valor_iso: str) -> None:
        from .formato import fecha_a_texto
        self.variable.set(fecha_a_texto(valor_iso))
        # Tk apaga la validación en cuanto una escritura del programa la
        # incumple. Se vuelve a encender por si acaso, que si no la casilla
        # se queda admitiendo cualquier cosa sin avisar.
        self.entrada.configure(validate="key")

    def abrir_calendario(self) -> None:
        # Solo uno abierto a la vez: pulsar el botón otra vez lo cierra, que
        # es lo que espera cualquiera de un desplegable.
        if self.calendario is not None and self.calendario.winfo_exists():
            self.calendario.cerrar()
            self.calendario = None
            return
        self.calendario = Calendario(self, self.iso() or "", self._elegido)
        self.calendario.abrir_junto_a(self)

    def _elegido(self, iso: str) -> None:
        self.poner(iso)
        self.entrada.focus_set()

    # El campo de verdad es la casilla: el marco solo la sujeta junto al botón.
    def focus_set(self) -> None:
        self.entrada.focus_set()

    def bind(self, secuencia=None, funcion=None, add=None):
        return self.entrada.bind(secuencia, funcion, add)


def _a_fecha(iso: str):
    try:
        return date.fromisoformat(iso)
    except (TypeError, ValueError):
        return None


def _al_pasar(widget: tk.Widget, encima: str, normal: str) -> None:
    """Cambia el fondo al pasar el ratón. Dice que se puede pulsar."""
    widget.bind("<Enter>", lambda _e: widget.configure(background=encima), add="+")
    widget.bind("<Leave>", lambda _e: widget.configure(background=normal), add="+")


def etiqueta_campo(padre, texto: str, fondo: str = "Tarjeta") -> ttk.Label:
    etiqueta = ttk.Label(padre, text=texto, style=f"{fondo}.Suave.TLabel")
    etiqueta.pack(anchor="w", pady=(8, 3))
    return etiqueta


def separador(padre, fondo: str = "Tarjeta") -> ttk.Frame:
    linea = tk.Frame(padre, background=PALETA.borde, height=1)
    linea.pack(fill="x", pady=10)
    return linea


# --- botones con icono dibujado --------------------------------------------

# Los emoji no sirven: en Windows tkinter los pinta como un cuadrado negro
# porque la fuente de la interfaz no tiene glifos de color. Se dibujan a mano
# con primitivas del lienzo, que además quedan nítidos en pantallas grandes.

def _dibujar_ojo(lienzo, x, y, lado, color, tachado=False):
    ancho, alto = lado, lado * 0.62
    izquierda, arriba = x - ancho / 2, y - alto / 2
    lienzo.create_oval(izquierda, arriba, izquierda + ancho, arriba + alto,
                       outline=color, width=max(1.4, lado / 12))
    radio = lado * 0.16
    lienzo.create_oval(x - radio, y - radio, x + radio, y + radio,
                       outline=color, width=max(1.4, lado / 12))
    if tachado:
        media = lado * 0.52
        lienzo.create_line(x - media, y + media, x + media, y - media,
                           fill=color, width=max(1.6, lado / 10), capstyle="round")


def _dibujar_sol(lienzo, x, y, lado, color):
    radio = lado * 0.26
    grosor = max(1.4, lado / 12)
    lienzo.create_oval(x - radio, y - radio, x + radio, y + radio,
                       outline=color, width=grosor)
    import math
    for paso in range(8):
        angulo = math.pi * paso / 4
        seno, coseno = math.sin(angulo), math.cos(angulo)
        lienzo.create_line(x + coseno * radio * 1.55, y + seno * radio * 1.55,
                           x + coseno * radio * 2.1, y + seno * radio * 2.1,
                           fill=color, width=grosor, capstyle="round")


def _dibujar_luna(lienzo, x, y, lado, color, fondo):
    radio = lado * 0.42
    # La media luna sale de tapar un círculo con otro del color del fondo.
    lienzo.create_oval(x - radio, y - radio, x + radio, y + radio,
                       fill=color, outline=color)
    desplazamiento = radio * 0.55
    lienzo.create_oval(x - radio + desplazamiento, y - radio - desplazamiento * 0.5,
                       x + radio + desplazamiento, y + radio - desplazamiento * 0.5,
                       fill=fondo, outline=fondo)


def _dibujar_pantalla(lienzo, x, y, lado, color):
    ancho, alto = lado * 0.82, lado * 0.6
    grosor = max(1.4, lado / 12)
    izquierda, arriba = x - ancho / 2, y - alto / 2 - lado * 0.06
    lienzo.create_rectangle(izquierda, arriba, izquierda + ancho, arriba + alto,
                            outline=color, width=grosor)
    lienzo.create_line(x, arriba + alto, x, arriba + alto + lado * 0.16,
                       fill=color, width=grosor)
    lienzo.create_line(x - ancho * 0.28, arriba + alto + lado * 0.16,
                       x + ancho * 0.28, arriba + alto + lado * 0.16,
                       fill=color, width=grosor, capstyle="round")


def _dibujar_calendario(lienzo, x, y, lado, color):
    """Una hojita de calendario: el marco, la barra de arriba y dos anillas."""
    ancho = alto = lado * 0.78
    grosor = max(1.2, lado / 14)
    izquierda, arriba = x - ancho / 2, y - alto / 2 + lado * 0.06
    lienzo.create_rectangle(izquierda, arriba, izquierda + ancho, arriba + alto,
                            outline=color, width=grosor)
    # La franja del encabezado, que es lo que lo hace reconocible de un vistazo.
    lienzo.create_line(izquierda, arriba + alto * 0.3,
                       izquierda + ancho, arriba + alto * 0.3,
                       fill=color, width=grosor)
    for lado_anilla in (0.3, 0.7):
        equis = izquierda + ancho * lado_anilla
        lienzo.create_line(equis, arriba - lado * 0.13, equis, arriba + alto * 0.1,
                           fill=color, width=grosor, capstyle="round")


class BotonIcono(tk.Canvas):
    """Un botón cuadrado con el icono dibujado, para la barra de arriba."""

    def __init__(self, padre, icono: str, comando, lado: int = 32,
                 fondo: str | None = None):
        self.fondo = fondo or PALETA.tarjeta
        super().__init__(padre, width=lado, height=lado, highlightthickness=0,
                         background=self.fondo, borderwidth=0, cursor="hand2")
        self.lado = lado
        self.comando = comando
        self.icono = icono
        self._encima = False

        self.bind("<Button-1>", lambda _e: self.comando())
        self.bind("<Enter>", self._entrar)
        self.bind("<Leave>", self._salir)
        self.pintar()

    def poner_icono(self, icono: str) -> None:
        self.icono = icono
        self.pintar()

    def _entrar(self, _evento=None):
        self._encima = True
        self.pintar()

    def _salir(self, _evento=None):
        self._encima = False
        self.pintar()

    def pintar(self) -> None:
        self.delete("all")
        fondo = PALETA.hundido if self._encima else self.fondo
        self.configure(background=fondo)
        color = PALETA.texto if self._encima else PALETA.suave
        centro = self.lado / 2
        tamano = self.lado * 0.58

        if self.icono == "ojo":
            _dibujar_ojo(self, centro, centro, tamano, color)
        elif self.icono == "ojo-tachado":
            _dibujar_ojo(self, centro, centro, tamano, color, tachado=True)
        elif self.icono == "sol":
            _dibujar_sol(self, centro, centro, tamano, color)
        elif self.icono == "luna":
            _dibujar_luna(self, centro, centro, tamano, color, fondo)
        elif self.icono == "calendario":
            _dibujar_calendario(self, centro, centro, tamano, color)
        else:
            _dibujar_pantalla(self, centro, centro, tamano, color)
