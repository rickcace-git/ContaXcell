"""El libro completo, con buscador y filtros.

La tabla usa dos columnas separadas para ingresos y gastos, igual que la hoja
de cálculo: la posición dice el signo sin necesidad de pintar nada de color.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import calculos, formato, widgets
from ..modelo import INGRESO, INVERSION, mes_de, nombre_mes
from . import comun

TODAS = "Todas"
TODOS_LOS_MESES = "Todos"
# Con muchos movimientos, pintarlos todos de golpe hace que la ventana tarde
# en responder. Se enseñan por tandas.
TANDA = 300


class VistaMovimientos:
    def __init__(self, padre, app):
        self.app = app
        self.limite = TANDA
        self._visibles: list = []
        self._meses_por_etiqueta: dict[str, str] = {}

        raiz = ttk.Frame(padre, padding=18)
        raiz.pack(fill="both", expand=True)

        self._filtros(raiz)
        self._tabla(raiz)

    # --- filtros ----------------------------------------------------------

    def _filtros(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "Filtros")
        tarjeta.pack(fill="x")
        fila = ttk.Frame(tarjeta.cuerpo, style="Tarjeta.TFrame")
        fila.pack(fill="x")

        bloque_buscar = ttk.Frame(fila, style="Tarjeta.TFrame")
        bloque_buscar.pack(side="left", fill="x", expand=True, padx=(0, 12))
        ttk.Label(bloque_buscar, text="Buscar", style="Tarjeta.Suave.TLabel").pack(anchor="w")
        self.var_texto = tk.StringVar()
        self.campo_buscar = ttk.Entry(bloque_buscar, textvariable=self.var_texto)
        self.campo_buscar.pack(fill="x")
        # Se filtra al escribir, sin botón: la lista responde a cada tecla.
        self.var_texto.trace_add("write", lambda *_: self._filtro_cambiado())

        bloque_categoria = ttk.Frame(fila, style="Tarjeta.TFrame")
        bloque_categoria.pack(side="left", padx=(0, 12))
        ttk.Label(bloque_categoria, text="Categoría", style="Tarjeta.Suave.TLabel").pack(anchor="w")
        self.var_categoria = tk.StringVar(value=TODAS)
        self.campo_categoria = ttk.Combobox(bloque_categoria, textvariable=self.var_categoria,
                                            state="readonly", width=22)
        self.campo_categoria.pack()
        self.campo_categoria.bind("<<ComboboxSelected>>", lambda _e: self._filtro_cambiado())

        bloque_mes = ttk.Frame(fila, style="Tarjeta.TFrame")
        bloque_mes.pack(side="left", padx=(0, 12))
        ttk.Label(bloque_mes, text="Mes", style="Tarjeta.Suave.TLabel").pack(anchor="w")
        self.var_mes = tk.StringVar(value=TODOS_LOS_MESES)
        self.campo_mes = ttk.Combobox(bloque_mes, textvariable=self.var_mes,
                                      state="readonly", width=18)
        self.campo_mes.pack()
        self.campo_mes.bind("<<ComboboxSelected>>", lambda _e: self._filtro_cambiado())

        bloque_boton = ttk.Frame(fila, style="Tarjeta.TFrame")
        bloque_boton.pack(side="left")
        ttk.Label(bloque_boton, text=" ", style="Tarjeta.Suave.TLabel").pack(anchor="w")
        ttk.Button(bloque_boton, text="Limpiar", command=self.limpiar).pack()

    def limpiar(self) -> None:
        self.var_texto.set("")
        self.var_categoria.set(TODAS)
        self.var_mes.set(TODOS_LOS_MESES)
        self._filtro_cambiado()

    def _filtro_cambiado(self) -> None:
        self.limite = TANDA
        self.refrescar()

    # --- tabla ------------------------------------------------------------

    def _tabla(self, padre) -> None:
        self.tarjeta = widgets.Tarjeta(padre, "Movimientos")
        self.tarjeta.pack(fill="both", expand=True, pady=(16, 0))

        self.resumen_filtro = ttk.Label(self.tarjeta.derecha, text="",
                                        style="Tarjeta.Suave.TLabel")
        self.resumen_filtro.pack(side="right")

        # Anclados al fondo antes que la tabla, para que no los desplace.
        self.acciones = ttk.Frame(self.tarjeta.cuerpo, style="Tarjeta.TFrame")
        self.acciones.pack(side="bottom", fill="x", pady=(10, 0))

        self.tabla = widgets.Tabla(self.tarjeta.cuerpo, [
            widgets.Columna("fecha", "Fecha", 100),
            widgets.Columna("descripcion", "Descripción", 260, estira=True),
            widgets.Columna("categoria", "Categoría", 170),
            widgets.Columna("activo", "Activo", 130),
            widgets.Columna("ingreso", "Ingreso", 110, anclaje="e"),
            widgets.Columna("gasto", "Gasto", 110, anclaje="e"),
            widgets.Columna("balance", "Balance", 120, anclaje="e"),
        ], alto=18, al_activar=self._editar_seleccionado)
        self.tabla.pack(fill="both", expand=True)

        self.vacio = ttk.Label(self.tarjeta.cuerpo, style="Tarjeta.Suave.TLabel",
                               justify="center", text="")

        ttk.Button(self.acciones, text="Editar",
                   command=self._editar_seleccionado).pack(side="left")
        ttk.Button(self.acciones, text="Borrar", style="Peligro.TButton",
                   command=self._borrar_seleccionado).pack(side="left", padx=(8, 0))
        self.boton_mas = ttk.Button(self.acciones, text="", command=self._ver_mas)
        self.totales = ttk.Label(self.acciones, text="", style="Tarjeta.Suave.TLabel")
        self.totales.pack(side="right")

    def _ver_mas(self) -> None:
        self.limite += TANDA * 2
        self.refrescar()

    def _seleccionado(self):
        clave = self.tabla.seleccion()
        if clave is None:
            self.app.estado("Elige antes un movimiento de la lista.", "malo")
            return None
        return self.app.libro.movimiento(clave)

    def _editar_seleccionado(self, _clave=None) -> None:
        movimiento = self._seleccionado()
        if movimiento:
            comun.editar_movimiento(self.app, movimiento)

    def _borrar_seleccionado(self) -> None:
        movimiento = self._seleccionado()
        if movimiento:
            comun.borrar_movimiento(self.app, movimiento)

    # --- refresco ---------------------------------------------------------

    def _rellenar_listas(self) -> None:
        libro = self.app.libro
        categorias = [TODAS] + [c.nombre for c in libro.categorias]
        self.campo_categoria.configure(values=categorias)
        if self.var_categoria.get() not in categorias:
            self.var_categoria.set(TODAS)

        meses = calculos.meses_con_datos(libro)
        etiquetas = [TODOS_LOS_MESES] + [nombre_mes(m) for m in meses]
        self._meses_por_etiqueta = dict(zip(etiquetas[1:], meses))
        self.campo_mes.configure(values=etiquetas)
        if self.var_mes.get() not in etiquetas:
            self.var_mes.set(TODOS_LOS_MESES)

    def _filtrar(self, filas: list) -> list:
        texto = self.var_texto.get().strip().lower()
        categoria = self.var_categoria.get()
        mes = self._meses_por_etiqueta.get(self.var_mes.get())

        resultado = []
        for fila in filas:
            if categoria != TODAS and fila.categoria != categoria:
                continue
            if mes and mes_de(fila.fecha) != mes:
                continue
            if texto:
                buscable = f"{fila.descripcion} {fila.categoria} {fila.activo}".lower()
                if texto not in buscable:
                    continue
            resultado.append(fila)
        return resultado

    def refrescar(self) -> None:
        self._rellenar_listas()
        libro = self.app.libro

        # De más reciente a más antiguo: lo último apuntado es lo que se mira.
        todas = list(reversed(calculos.con_balance(libro)))
        self._visibles = self._filtrar(todas)
        mostradas = self._visibles[:self.limite]

        filas = []
        for fila in mostradas:
            es_ingreso = fila.tipo == INGRESO
            filas.append((fila.id, (
                formato.fecha_corta(fila.fecha),
                fila.descripcion or "—",
                fila.categoria,
                fila.activo,
                formato.euros(fila.importe) if es_ingreso else "",
                "" if es_ingreso else formato.euros(fila.importe),
                formato.euros(fila.balance),
            ), (comun.etiqueta_por_tipo(fila.tipo),)))
        self.tabla.poner(filas)

        cuantos = len(self._visibles)
        self.tarjeta.titulo("1 movimiento" if cuantos == 1 else f"{cuantos} movimientos")
        self._pintar_totales()
        self._pintar_vacio(len(todas), cuantos)

        faltan = cuantos - len(mostradas)
        if faltan > 0:
            self.boton_mas.configure(text=f"Ver {faltan} más")
            if not self.boton_mas.winfo_ismapped():
                self.boton_mas.pack(side="left", padx=(8, 0))
        elif self.boton_mas.winfo_ismapped():
            self.boton_mas.pack_forget()

    def _pintar_totales(self) -> None:
        ingresos = gastos = inversion = 0.0
        for fila in self._visibles:
            if fila.tipo == INGRESO:
                ingresos = calculos.redondea(ingresos + fila.importe)
            elif fila.tipo == INVERSION:
                inversion = calculos.redondea(inversion + fila.importe)
            else:
                gastos = calculos.redondea(gastos + fila.importe)

        self.totales.configure(
            text=f"{formato.euros(ingresos)} ingresado   ·   "
                 f"{formato.euros(gastos)} gastado   ·   "
                 f"{formato.euros(inversion)} invertido")
        self.resumen_filtro.configure(
            text="Doble clic sobre una fila para editarla")

    def _pintar_vacio(self, total: int, visibles: int) -> None:
        if visibles > 0:
            self.vacio.pack_forget()
            if not self.tabla.winfo_ismapped():
                self.tabla.pack(fill="both", expand=True)
            return

        self.tabla.pack_forget()
        self.vacio.configure(text=(
            "El libro está vacío.\n\nApunta algo en la pestaña Apuntar, o trae tu "
            "historial desde el Excel en Ajustes."
            if total == 0 else
            "Ningún movimiento coincide con el filtro.\n\nPrueba a pulsar «Limpiar»."))
        if not self.vacio.winfo_ismapped():
            self.vacio.pack(pady=50)

    def al_entrar(self) -> None:
        self.campo_buscar.focus_set()
