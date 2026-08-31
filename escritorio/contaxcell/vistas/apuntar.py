"""Pestaña de entrada rápida.

Es la que se usa a diario: importe, concepto, categoría y listo. El resto de
la aplicación sirve para consultar; esta sirve para escribir, así que manda la
velocidad de teclado por encima de todo lo demás.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import calculos, formato, widgets
from ..modelo import (MENSUAL, PERIODOS, Movimiento, hoy, mes_de, nombre_mes,
                      suma_dias)
from . import comun


class VistaApuntar:
    def __init__(self, padre, app):
        self.app = app
        self.tipo = "gasto"

        self.desplazable = widgets.MarcoDesplazable(padre)
        self.desplazable.pack(fill="both", expand=True)
        raiz = ttk.Frame(self.desplazable.interior, padding=18)
        raiz.pack(fill="both", expand=True)
        raiz.columnconfigure(0, minsize=int(360 * app.escala), weight=0)
        raiz.columnconfigure(1, weight=1)
        raiz.rowconfigure(0, weight=1)

        izquierda = ttk.Frame(raiz)
        izquierda.grid(row=0, column=0, sticky="nsew", padx=(0, 16))
        derecha = ttk.Frame(raiz)
        derecha.grid(row=0, column=1, sticky="nsew")

        self._formulario(izquierda)
        self._mes(derecha)
        self._ultimos(derecha)

    # --- formulario -------------------------------------------------------

    def _formulario(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "Apuntar")
        tarjeta.pack(fill="x")
        cuerpo = tarjeta.cuerpo

        botones = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
        botones.pack(fill="x")
        botones.columnconfigure(0, weight=1, uniform="tipo")
        botones.columnconfigure(1, weight=1, uniform="tipo")
        self.boton_gasto = ttk.Button(botones, text="Gasto",
                                      command=lambda: self._poner_tipo("gasto"))
        self.boton_gasto.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.boton_ingreso = ttk.Button(botones, text="Ingreso",
                                        command=lambda: self._poner_tipo("ingreso"))
        self.boton_ingreso.grid(row=0, column=1, sticky="ew", padx=(4, 0))

        widgets.etiqueta_campo(cuerpo, "Importe")
        self.var_importe = tk.StringVar()
        self.campo_importe = ttk.Entry(cuerpo, textvariable=self.var_importe,
                                       font=self.app.fuentes.importe, justify="center",
                                       style="Importe.TEntry")
        widgets.solo_numeros(self.campo_importe)
        self.campo_importe.pack(fill="x")

        widgets.etiqueta_campo(cuerpo, "Descripción")
        self.var_descripcion = tk.StringVar()
        self.campo_descripcion = ttk.Entry(cuerpo, textvariable=self.var_descripcion)
        self.campo_descripcion.pack(fill="x")

        widgets.etiqueta_campo(cuerpo, "Categoría")
        self.var_categoria = tk.StringVar()
        self.campo_categoria = ttk.Combobox(cuerpo, textvariable=self.var_categoria,
                                            state="readonly")
        self.campo_categoria.pack(fill="x")
        self.campo_categoria.bind("<<ComboboxSelected>>", lambda _e: self._revisar_activo())

        # El bloque del activo se enseña solo cuando la categoría es inversión.
        self.bloque_activo = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
        widgets.etiqueta_campo(self.bloque_activo, "¿A qué activo?")
        self.var_activo = tk.StringVar()
        self.campo_activo = ttk.Combobox(self.bloque_activo, textvariable=self.var_activo,
                                         state="readonly")
        self.campo_activo.pack(fill="x")
        self.aviso_sin_activos = ttk.Label(
            self.bloque_activo, style="Tarjeta.Suave.TLabel", wraplength=310, justify="left",
            text="Todavía no has creado ningún activo. Puedes apuntar la aportación "
                 "igual y asignarla luego desde la pestaña Inversiones.")

        self.etiqueta_fecha = widgets.etiqueta_campo(cuerpo, "Fecha")
        self.campo_fecha = widgets.CampoFecha(cuerpo, hoy())
        self.campo_fecha.pack(anchor="w")

        self._repeticion(cuerpo)

        ttk.Button(cuerpo, text="Guardar", style="Principal.TButton",
                   command=self.guardar).pack(fill="x", pady=(16, 0))

        self.campo_importe.bind("<Return>", lambda _e: self.campo_descripcion.focus_set())
        self.campo_descripcion.bind("<Return>", lambda _e: self.guardar())
        self.campo_fecha.bind("<Return>", lambda _e: self.guardar())

        self._poner_tipo("gasto")

    def _repeticion(self, cuerpo) -> None:
        """La casilla «se repite», debajo de la fecha.

        El alquiler y la nómina se apuntan igual que todo lo demás la primera
        vez. Marcarlo aquí evita ir a la otra pestaña a escribir lo mismo otra
        vez: este apunte es el primer pago y la regla sale de él.
        """
        # Todo dentro de un bloque suyo: la pista aparece y desaparece, y si
        # colgara del cuerpo se colocaría debajo del botón de guardar.
        bloque = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
        bloque.pack(fill="x", pady=(12, 0))
        fila = ttk.Frame(bloque, style="Tarjeta.TFrame")
        fila.pack(fill="x")

        self.var_repetir = tk.BooleanVar(value=False)
        ttk.Checkbutton(fila, text="Se repite", variable=self.var_repetir,
                        command=self._revisar_repeticion).pack(side="left")

        self.var_periodo = tk.StringVar(value=MENSUAL)
        self.campo_periodo = ttk.Combobox(fila, textvariable=self.var_periodo,
                                          state="readonly", width=12,
                                          values=list(PERIODOS))

        self.pista_repetir = ttk.Label(
            bloque, style="Tarjeta.Suave.TLabel", wraplength=310, justify="left",
            text="Se apuntará solo cuando toque, contando desde esta fecha. "
                 "Para cambiarlo o apagarlo, en la pestaña Periódicos.")

    def _revisar_repeticion(self) -> None:
        if self.var_repetir.get():
            self.campo_periodo.pack(side="left", padx=(10, 0))
            self.pista_repetir.pack(anchor="w", pady=(4, 0))
        else:
            self.campo_periodo.pack_forget()
            self.pista_repetir.pack_forget()

    def _poner_tipo(self, valor: str) -> None:
        self.tipo = valor
        self.boton_gasto.configure(
            style=f"{'GastoEncendido' if valor == 'gasto' else 'GastoApagado'}.TButton")
        self.boton_ingreso.configure(
            style=f"{'IngresoEncendido' if valor == 'ingreso' else 'IngresoApagado'}.TButton")
        self._llenar_categorias()

    def _llenar_categorias(self) -> None:
        disponibles = comun.categorias_para(self.app.libro, self.tipo)
        self.campo_categoria.configure(values=disponibles)
        if self.var_categoria.get() not in disponibles:
            self.var_categoria.set(disponibles[0] if disponibles else "")
        self._revisar_activo()

    def _revisar_activo(self) -> None:
        libro = self.app.libro
        toca = comun.es_aportacion(libro, self.var_categoria.get())
        if not toca:
            if self.bloque_activo.winfo_ismapped():
                self.bloque_activo.pack_forget()
            return

        nombres = [a.nombre for a in libro.activos]
        if nombres:
            self.aviso_sin_activos.pack_forget()
            self.campo_activo.configure(values=[comun.SIN_ASIGNAR] + nombres)
            if self.var_activo.get() not in [comun.SIN_ASIGNAR] + nombres:
                self.var_activo.set(nombres[0] if len(nombres) == 1 else comun.SIN_ASIGNAR)
            if not self.campo_activo.winfo_ismapped():
                self.campo_activo.pack(fill="x")
        else:
            self.campo_activo.pack_forget()
            self.aviso_sin_activos.pack(anchor="w", pady=(2, 0))

        if not self.bloque_activo.winfo_ismapped():
            # Va justo encima de la fecha, donde estaría si siempre se viera.
            self.bloque_activo.pack(fill="x", before=self.etiqueta_fecha)

    def guardar(self) -> None:
        importe = formato.texto_a_numero(self.var_importe.get())
        if importe is None or importe <= 0:
            self.app.estado("Escribe un importe mayor que cero.", "malo")
            self.campo_importe.focus_set()
            self.campo_importe.select_range(0, "end")
            return

        categoria = self.var_categoria.get()
        if not categoria:
            self.app.estado("Elige una categoría. Si no hay ninguna, créala en Ajustes.", "malo")
            return

        fecha = self.campo_fecha.iso()
        if fecha is None:
            self.app.estado("La fecha no es válida. Escríbela como 24/08/2026.", "malo")
            self.campo_fecha.focus_set()
            return

        activo = ""
        if comun.es_aportacion(self.app.libro, categoria):
            elegido = self.var_activo.get()
            activo = "" if elegido == comun.SIN_ASIGNAR else elegido

        nuevo = Movimiento(
            fecha=fecha,
            descripcion=self.var_descripcion.get().strip(),
            categoria=categoria,
            importe=abs(importe),
            activo=activo,
        )

        aviso = f"Apuntado: {formato.euros(nuevo.importe, siempre_visible=True)} · {categoria}"

        # Con la casilla marcada se crea además la regla que lo repetirá. El
        # movimiento de arriba es su primer pago, así que no se apunta dos
        # veces: de eso se encarga `calculos.periodico_de`.
        periodico = None
        if self.var_repetir.get():
            periodico = calculos.periodico_de(nuevo, self.var_periodo.get())
            # A partir del día siguiente al ya apuntado: el pago de hoy es
            # el que se acaba de escribir, no el siguiente.
            proximo = calculos.proximo_vencimiento(
                periodico, suma_dias(periodico.apuntado_hasta, 1))
            aviso += (f" · se repite {periodico.periodo.lower()}"
                      + (f", el próximo el {formato.fecha_corta(proximo)}"
                         if proximo else ""))

        def aplicar(libro):
            libro.movimientos.append(nuevo)
            if periodico is not None:
                libro.periodicos.append(periodico)

        if not self.app.cambiar(aplicar, aviso):
            return

        # Se conservan la categoría y la fecha: al apuntar varias cosas
        # seguidas suelen repetirse. El importe y el concepto, no. La casilla
        # tampoco: es una decisión de este apunte, y dejarla puesta llenaría
        # de reglas repetidas el resto de la tarde.
        self.var_importe.set("")
        self.var_descripcion.set("")
        self.var_repetir.set(False)
        self._revisar_repeticion()
        self.campo_importe.focus_set()

    # --- lateral ----------------------------------------------------------

    def _mes(self, padre) -> None:
        self.tarjeta_mes = widgets.Tarjeta(padre, "el mes")
        self.tarjeta_mes.pack(fill="x")
        self.cifras = widgets.PanelCifras(self.tarjeta_mes.cuerpo, columnas=4)
        self.cifras.pack(fill="x")

    def _ultimos(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "Últimos movimientos")
        tarjeta.pack(fill="both", expand=True, pady=(16, 0))
        self.tarjeta_ultimos = tarjeta

        ttk.Button(tarjeta.derecha, text="Ver todos", style="Enlace.TButton",
                   command=lambda: self.app.ir_a("movimientos")).pack(side="right")

        acciones = self.acciones = ttk.Frame(tarjeta.cuerpo, style="Tarjeta.TFrame")
        acciones.pack(side="bottom", fill="x", pady=(10, 0))

        self.tabla = widgets.Tabla(tarjeta.cuerpo, [
            widgets.Columna("fecha", "Fecha", 100),
            widgets.Columna("descripcion", "Descripción", 240, estira=True),
            widgets.Columna("categoria", "Categoría", 160),
            widgets.Columna("importe", "Importe", 130, anclaje="e"),
        ], alto=12, al_activar=self._editar_seleccionado)
        self.tabla.pack(fill="both", expand=True)

        self.vacio = ttk.Label(
            tarjeta.cuerpo, style="Tarjeta.Suave.TLabel", justify="center",
            text="Todavía no hay nada apuntado.\n\nApunta el primero en el formulario "
                 "de la izquierda, o trae tu historial desde el Excel en Ajustes.")

        ttk.Button(acciones, text="Editar", command=self._editar_seleccionado).pack(side="left")
        ttk.Button(acciones, text="Borrar", style="Peligro.TButton",
                   command=self._borrar_seleccionado).pack(side="left", padx=(8, 0))
        ttk.Label(acciones, text="Doble clic sobre una fila para editarla",
                  style="Tarjeta.Suave.TLabel").pack(side="right")

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

    def refrescar(self) -> None:
        libro = self.app.libro
        self._llenar_categorias()

        mes = mes_de(hoy())
        totales = calculos.totales_del_mes(libro, mes)
        self.tarjeta_mes.titulo(nombre_mes(mes))
        self.cifras.poner("ingresos", "Ingresos", formato.euros(totales.ingresos), "Ingreso")
        self.cifras.poner("gastos", "Gastos", formato.euros(totales.gastos), "Gasto")
        self.cifras.poner(
            "ahorro", "Ahorro", formato.euros(totales.ahorro),
            _color(totales.ahorro),
            f"{formato.porcentaje(totales.tasa_ahorro)} de lo ingresado"
            if totales.ingresos > 0 else "")
        self.cifras.poner("inversion", "Inversión", formato.euros(totales.inversion),
                          "Inversion")

        filas = []
        for registro in reversed(calculos.con_balance(libro)[-12:]):
            filas.append((registro.id, (
                formato.fecha_corta(registro.fecha),
                registro.descripcion or "—",
                registro.categoria,
                comun.importe_con_signo(registro.tipo, registro.importe),
            ), (comun.etiqueta_por_tipo(registro.tipo),)))

        if filas:
            self.vacio.pack_forget()
            if not self.tabla.winfo_ismapped():
                self.tabla.pack(fill="both", expand=True)
            self.tabla.poner(filas)
            self.tabla.ajustar_alto(len(filas), minimo=5, maximo=12)
        else:
            self.tabla.pack_forget()
            if not self.vacio.winfo_ismapped():
                self.vacio.pack(pady=40)

    def al_entrar(self) -> None:
        self.campo_importe.focus_set()


def _color(valor: float) -> str:
    if valor > 0:
        return "Ingreso"
    if valor < 0:
        return "Gasto"
    return "Suave"
