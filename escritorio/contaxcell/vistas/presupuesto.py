"""Cuánto tenías previsto gastar en cada cosa y cuánto llevas.

El presupuesto es una cifra por categoría y vale para todos los meses, igual
que en la plantilla: lo que cambia de un mes a otro es el gasto real.

La tabla no es un Treeview sino una rejilla de casillas de verdad, porque aquí
hay que poder escribir encima y ver una barra de consumo en cada fila. Son
pocas filas, así que sale a cuenta.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import calculos, formato, widgets
from ..modelo import nombre_mes


class VistaPresupuesto:
    def __init__(self, padre, app):
        self.app = app
        self.mes = None
        self._filas: dict[str, dict] = {}
        self._meses_por_etiqueta: dict[str, str] = {}

        self.desplazable = widgets.MarcoDesplazable(padre)
        self.desplazable.pack(fill="both", expand=True)
        raiz = ttk.Frame(self.desplazable.interior, padding=18)
        raiz.pack(fill="both", expand=True)

        self._tabla(raiz)
        self._conjunto(raiz)
        self._inversion(raiz)

    # --- construcción -----------------------------------------------------

    def _tabla(self, padre) -> None:
        self.tarjeta = widgets.Tarjeta(padre, "Presupuesto")
        self.tarjeta.pack(fill="x")

        ttk.Label(self.tarjeta.derecha, text="Mes",
                  style="Tarjeta.Suave.TLabel").pack(side="left", padx=(0, 6))
        self.var_mes = tk.StringVar()
        self.campo_mes = ttk.Combobox(self.tarjeta.derecha, textvariable=self.var_mes,
                                      state="readonly", width=18)
        self.campo_mes.pack(side="left")
        self.campo_mes.bind("<<ComboboxSelected>>", lambda _e: self._cambio_de_mes())

        self.rejilla = ttk.Frame(self.tarjeta.cuerpo, style="Tarjeta.TFrame")
        self.rejilla.pack(fill="x")
        for columna, peso in ((0, 3), (1, 0), (2, 0), (3, 0), (4, 0), (5, 0)):
            self.rejilla.columnconfigure(columna, weight=peso)

        self.pista = ttk.Label(
            self.tarjeta.cuerpo, style="Tarjeta.Suave.TLabel", justify="left",
            wraplength=800,
            text="Escribe directamente en la columna «Presupuesto»: se guarda al salir "
                 "de la casilla o al pulsar Intro, y vale para todos los meses. "
                 "Déjala vacía si esa categoría no tiene tope.")
        self.pista.pack(anchor="w", pady=(12, 0))

    def _conjunto(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "El mes en conjunto")
        tarjeta.pack(fill="x", pady=(16, 0))
        self.cifras = widgets.PanelCifras(tarjeta.cuerpo, columnas=5)
        self.cifras.pack(fill="x")

    def _inversion(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "Inversión")
        tarjeta.pack(fill="x", pady=(16, 0))
        self.cifras_inversion = widgets.PanelCifras(tarjeta.cuerpo, columnas=3)
        self.cifras_inversion.pack(fill="x")

        bloque = ttk.Frame(tarjeta.cuerpo, style="Tarjeta.TFrame")
        bloque.pack(anchor="w", pady=(6, 0))
        ttk.Label(bloque, text="Objetivo de inversión al mes",
                  style="Tarjeta.Suave.TLabel").pack(anchor="w")
        self.var_objetivo = tk.StringVar()
        self.campo_objetivo = ttk.Entry(bloque, textvariable=self.var_objetivo, width=14)
        self.campo_objetivo.pack(anchor="w", pady=(3, 0))
        self.campo_objetivo.bind("<FocusOut>", lambda _e: self._guardar_objetivo())
        self.campo_objetivo.bind("<Return>", lambda _e: self._guardar_objetivo())

        ttk.Label(tarjeta.cuerpo, style="Tarjeta.Suave.TLabel", justify="left",
                  wraplength=800,
                  text="La inversión no cuenta como gasto: sale del banco, pero el dinero "
                       "sigue siendo tuyo. Por eso el ahorro del mes la ignora y el saldo "
                       "del banco sí la descuenta.").pack(anchor="w", pady=(12, 0))

    # --- rejilla del presupuesto -----------------------------------------

    def _rehacer_rejilla(self, nombres: list[str]) -> None:
        for hijo in self.rejilla.winfo_children():
            hijo.destroy()
        self._filas.clear()

        cabeceras = ["Categoría", "Presupuesto", "Gasto real", "Disponible", "Consumido", ""]
        for columna, texto in enumerate(cabeceras):
            ttk.Label(self.rejilla, text=texto.upper(), style="Tarjeta.Titulo.TLabel",
                      anchor="e" if columna in (1, 2, 3, 4) else "w").grid(
                row=0, column=columna, sticky="ew", padx=(0, 14), pady=(0, 8))

        for indice, nombre in enumerate(nombres, start=1):
            variable = tk.StringVar()
            casilla = ttk.Entry(self.rejilla, textvariable=variable, width=12,
                                justify="right")
            casilla.grid(row=indice, column=1, sticky="e", padx=(0, 14), pady=2)
            casilla.bind("<FocusOut>", lambda _e, n=nombre: self._guardar_tope(n))
            casilla.bind("<Return>", lambda _e, n=nombre: self._guardar_tope(n))

            etiquetas = {}
            ttk.Label(self.rejilla, text=nombre, style="Tarjeta.TLabel").grid(
                row=indice, column=0, sticky="w", padx=(0, 14), pady=2)
            for columna, clave, estilo in ((2, "real", "Tarjeta.Gasto.TLabel"),
                                           (3, "disponible", "Tarjeta.TLabel"),
                                           (4, "consumido", "Tarjeta.Suave.TLabel")):
                etiqueta = ttk.Label(self.rejilla, text="", style=estilo, anchor="e")
                etiqueta.grid(row=indice, column=columna, sticky="ew", padx=(0, 14), pady=2)
                etiquetas[clave] = etiqueta

            barra = widgets.Barra(self.rejilla, ancho=120)
            barra.grid(row=indice, column=5, sticky="w", pady=2)

            self._filas[nombre] = {"variable": variable, "casilla": casilla,
                                   "etiquetas": etiquetas, "barra": barra}

        # Fila de totales, separada por una línea.
        fila_total = len(nombres) + 1
        tk.Frame(self.rejilla, background=widgets.PALETA.borde, height=1).grid(
            row=fila_total, column=0, columnspan=6, sticky="ew", pady=(8, 6))

        self._totales = {}
        ttk.Label(self.rejilla, text="TOTAL", style="Tarjeta.Negrita.TLabel").grid(
            row=fila_total + 1, column=0, sticky="w", padx=(0, 14))
        for columna, clave in ((1, "presupuestado"), (2, "gastado"),
                               (3, "disponible"), (4, "consumido")):
            etiqueta = ttk.Label(self.rejilla, text="", style="Tarjeta.Negrita.TLabel",
                                 anchor="e")
            etiqueta.grid(row=fila_total + 1, column=columna, sticky="ew", padx=(0, 14))
            self._totales[clave] = etiqueta
        self._barra_total = widgets.Barra(self.rejilla, ancho=120)
        self._barra_total.grid(row=fila_total + 1, column=5, sticky="w")

    # --- guardado ---------------------------------------------------------

    def _guardar_tope(self, nombre: str) -> None:
        fila = self._filas.get(nombre)
        if fila is None:
            return
        texto = fila["variable"].get().strip()
        valor = 0.0 if not texto else formato.texto_a_numero(texto)
        if valor is None or valor < 0:
            self.app.estado(f"«{texto}» no es un presupuesto válido.", "malo")
            self.refrescar()
            return

        categoria = self.app.libro.categoria(nombre)
        if categoria is None or categoria.presupuesto == valor:
            return
        self.app.cambiar(lambda libro: setattr(libro.categoria(nombre), "presupuesto", valor))

    def _guardar_objetivo(self) -> None:
        texto = self.var_objetivo.get().strip()
        valor = 0.0 if not texto else formato.texto_a_numero(texto)
        if valor is None or valor < 0:
            self.app.estado(f"«{texto}» no es un objetivo válido.", "malo")
            self.refrescar()
            return
        if self.app.libro.ajustes.objetivo_inversion == valor:
            return
        self.app.cambiar(
            lambda libro: setattr(libro.ajustes, "objetivo_inversion", valor),
            "Objetivo de inversión actualizado.")

    def _cambio_de_mes(self) -> None:
        self.mes = self._meses_por_etiqueta.get(self.var_mes.get())
        self.refrescar()

    # --- refresco ---------------------------------------------------------

    def refrescar(self) -> None:
        libro = self.app.libro
        meses = calculos.meses_con_datos(libro)
        if self.mes not in meses:
            self.mes = meses[0]

        etiquetas = [nombre_mes(m) for m in meses]
        self._meses_por_etiqueta = dict(zip(etiquetas, meses))
        self.campo_mes.configure(values=etiquetas)
        self.var_mes.set(nombre_mes(self.mes))

        presupuesto = calculos.presupuesto_del_mes(libro, self.mes)
        self.tarjeta.titulo(f"Presupuesto de {nombre_mes(self.mes)}")

        nombres = [f.nombre for f in presupuesto.filas]
        if nombres != list(self._filas):
            self._rehacer_rejilla(nombres)

        if not nombres:
            self.pista.configure(
                text="No tienes ninguna categoría de gasto. Créalas en Ajustes y aquí "
                     "podrás ponerles un tope mensual.")
        for fila in presupuesto.filas:
            self._pintar_fila(fila)
        self._pintar_totales(presupuesto)
        self._pintar_conjunto(presupuesto)

    def _pintar_fila(self, fila) -> None:
        widgets_fila = self._filas.get(fila.nombre)
        if widgets_fila is None:
            return

        # No pisamos lo que el usuario está escribiendo ahora mismo.
        if self.app.focus_get() is not widgets_fila["casilla"]:
            widgets_fila["variable"].set(
                formato.numero(fila.presupuesto) if fila.presupuesto else "")

        etiquetas = widgets_fila["etiquetas"]
        etiquetas["real"].configure(text=formato.euros(fila.real))
        if fila.presupuesto > 0:
            etiquetas["disponible"].configure(
                text=formato.euros(fila.disponible),
                style="Tarjeta.Gasto.TLabel" if fila.disponible < 0
                else "Tarjeta.Ingreso.TLabel")
            etiquetas["consumido"].configure(text=formato.porcentaje(fila.consumido))
        else:
            etiquetas["disponible"].configure(text="—", style="Tarjeta.Suave.TLabel")
            etiquetas["consumido"].configure(text="—")
        widgets_fila["barra"].dibujar(fila.consumido if fila.presupuesto > 0 else 0,
                                      semaforo=True)

    def _pintar_totales(self, presupuesto) -> None:
        if not self._filas and not getattr(self, "_totales", None):
            return
        self._totales["presupuestado"].configure(text=formato.euros(presupuesto.presupuestado))
        self._totales["gastado"].configure(text=formato.euros(presupuesto.gastado))
        self._totales["disponible"].configure(text=formato.euros(presupuesto.disponible))
        self._totales["consumido"].configure(
            text=formato.porcentaje(presupuesto.consumido)
            if presupuesto.presupuestado > 0 else "—")
        self._barra_total.dibujar(
            presupuesto.consumido if presupuesto.presupuestado > 0 else 0, semaforo=True)

    def _pintar_conjunto(self, presupuesto) -> None:
        poner = self.cifras.poner
        poner("ingresos", "Ingresos del mes", formato.euros(presupuesto.ingresos), "Ingreso")
        poner("presupuestado", "Presupuestado", formato.euros(presupuesto.presupuestado))
        poner("gastado", "Gastado", formato.euros(presupuesto.gastado), "Gasto")
        poner("queda", "Queda por gastar", formato.euros(presupuesto.disponible),
              "Gasto" if presupuesto.disponible < 0 else "Ingreso")
        poner("margen", "Margen", formato.euros(presupuesto.margen),
              _color(presupuesto.margen), "lo que ingresas menos lo presupuestado")

        poner_inv = self.cifras_inversion.poner
        poner_inv("aportado", "Aportado este mes", formato.euros(presupuesto.aportado),
                  "Inversion")
        poner_inv("pendiente", "Pendiente de aportar", formato.euros(presupuesto.pendiente),
                  "Suave" if presupuesto.pendiente > 0 else "Ingreso")
        poner_inv("cumplido", "Objetivo cumplido",
                  formato.porcentaje(presupuesto.aportado / presupuesto.objetivo_inversion)
                  if presupuesto.objetivo_inversion > 0 else "—")

        if self.app.focus_get() is not self.campo_objetivo:
            self.var_objetivo.set(formato.numero(presupuesto.objetivo_inversion)
                                  if presupuesto.objetivo_inversion else "")

    def al_entrar(self) -> None:
        self.desplazable.arriba()


def _color(valor: float) -> str:
    if valor > 0:
        return "Ingreso"
    if valor < 0:
        return "Gasto"
    return "Suave"
