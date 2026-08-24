"""Cómo va el año: los doce meses, en qué se va el dinero y los indicadores.

Es la pantalla de mirar hacia atrás. Los números finos están en las tablas; el
gráfico está para ver la forma del año de un vistazo.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import calculos, formato, widgets


class VistaResumen:
    def __init__(self, padre, app):
        self.app = app
        self.anio = None

        self.desplazable = widgets.MarcoDesplazable(padre)
        self.desplazable.pack(fill="both", expand=True)
        raiz = ttk.Frame(self.desplazable.interior, padding=18)
        raiz.pack(fill="both", expand=True)

        self._indicadores(raiz)
        self._mes_a_mes(raiz)
        self._repartos(raiz)

    # --- construcción -----------------------------------------------------

    def _indicadores(self, padre) -> None:
        self.tarjeta_indicadores = widgets.Tarjeta(padre, "Resumen")
        self.tarjeta_indicadores.pack(fill="x")

        ttk.Label(self.tarjeta_indicadores.derecha, text="Año",
                  style="Tarjeta.Suave.TLabel").pack(side="left", padx=(0, 6))
        self.var_anio = tk.StringVar()
        self.campo_anio = ttk.Combobox(self.tarjeta_indicadores.derecha,
                                       textvariable=self.var_anio,
                                       state="readonly", width=7)
        self.campo_anio.pack(side="left")
        self.campo_anio.bind("<<ComboboxSelected>>", lambda _e: self._cambio_de_anio())

        self.cifras = widgets.PanelCifras(self.tarjeta_indicadores.cuerpo, columnas=5)
        self.cifras.pack(fill="x")

        self.sin_datos = ttk.Label(self.tarjeta_indicadores.cuerpo, text="",
                                   style="Tarjeta.Suave.TLabel", justify="center")

    def _mes_a_mes(self, padre) -> None:
        self.tarjeta_meses = widgets.Tarjeta(padre, "Mes a mes")
        self.tarjeta_meses.pack(fill="x", pady=(16, 0))

        self.grafico = widgets.GraficoBarras(self.tarjeta_meses.cuerpo, alto=190)
        self.grafico.pack(fill="x")
        widgets.Leyenda(self.tarjeta_meses.cuerpo, [
            (widgets.PALETA.ingreso, "Ingresos"),
            (widgets.PALETA.gasto, "Gastos"),
            (widgets.PALETA.inversion, "Inversión"),
        ]).pack(anchor="w", pady=(6, 12))

        self.tabla_meses = widgets.Tabla(self.tarjeta_meses.cuerpo, [
            widgets.Columna("mes", "Mes", 130, estira=True),
            widgets.Columna("ingresos", "Ingresos", 120, anclaje="e"),
            widgets.Columna("gastos", "Gastos", 120, anclaje="e"),
            widgets.Columna("ahorro", "Ahorro", 120, anclaje="e"),
            widgets.Columna("inversion", "Inversión", 120, anclaje="e"),
            widgets.Columna("saldo", "Saldo a fin de mes", 150, anclaje="e"),
        ], alto=13)
        self.tabla_meses.pack(fill="x")

    def _repartos(self, padre) -> None:
        fila = ttk.Frame(padre)
        fila.pack(fill="both", expand=True, pady=(16, 0))
        fila.columnconfigure(0, weight=1, uniform="reparto")
        fila.columnconfigure(1, weight=1, uniform="reparto")

        self.tarjeta_gasto = widgets.Tarjeta(fila, "En qué se va el dinero")
        self.tarjeta_gasto.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.tabla_gasto = self._tabla_reparto(self.tarjeta_gasto)

        self.tarjeta_ingreso = widgets.Tarjeta(fila, "De dónde viene")
        self.tarjeta_ingreso.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        self.tabla_ingreso = self._tabla_reparto(self.tarjeta_ingreso)

    def _tabla_reparto(self, tarjeta) -> widgets.Tabla:
        tabla = widgets.Tabla(tarjeta.cuerpo, [
            widgets.Columna("categoria", "Categoría", 160, estira=True),
            widgets.Columna("importe", "Año", 110, anclaje="e"),
            widgets.Columna("porcentaje", "%", 70, anclaje="e"),
            # Las barras se dibujan con caracteres: en un Treeview no se pueden
            # meter widgets dentro de una celda.
            widgets.Columna("barra", "", 110),
        ], alto=9)
        tabla.pack(fill="both", expand=True)
        return tabla

    # --- año --------------------------------------------------------------

    def _cambio_de_anio(self) -> None:
        try:
            self.anio = int(self.var_anio.get())
        except ValueError:
            return
        self.refrescar()

    # --- refresco ---------------------------------------------------------

    def refrescar(self) -> None:
        libro = self.app.libro
        anios = calculos.anios_con_datos(libro)
        if self.anio not in anios:
            self.anio = anios[0]

        self.campo_anio.configure(values=[str(a) for a in anios])
        self.var_anio.set(str(self.anio))

        resumen = calculos.resumen_anual(libro, self.anio)
        indicadores = calculos.indicadores(libro, self.anio)

        self.tarjeta_indicadores.titulo(f"Resumen de {self.anio}")
        self._pintar_indicadores(resumen, indicadores)
        self._pintar_meses(resumen)
        self._pintar_reparto(self.tabla_gasto, resumen.gasto, "gasto")
        self._pintar_reparto(self.tabla_ingreso, resumen.ingreso, "ingreso")

    def _pintar_indicadores(self, resumen, indicadores) -> None:
        total = resumen.total
        poner = self.cifras.poner

        poner("ingresos", "Ingresos del año", formato.euros(total.ingresos), "Ingreso")
        poner("gastos", "Gastos del año", formato.euros(total.gastos), "Gasto")
        poner("ahorro", "Ahorro del año", formato.euros(total.ahorro), _color(total.ahorro),
              f"{formato.porcentaje(total.tasa_ahorro)} de lo ingresado"
              if total.ingresos > 0 else "")
        poner("inversion", "Aportado a inversión", formato.euros(total.inversion), "Inversion")
        poner("patrimonio", "Patrimonio", formato.euros(indicadores.patrimonio), "",
              "banco + cartera")

        meses = indicadores.meses_con_datos
        poner("gasto_medio", "Gasto medio al mes", formato.euros(indicadores.gasto_medio), "",
              f"{meses} mes con datos" if meses == 1 else f"{meses} meses con datos")
        poner("ahorro_medio", "Ahorro medio al mes", formato.euros(indicadores.ahorro_medio),
              _color(indicadores.ahorro_medio))
        poner("colchon", "Meses de colchón",
              formato.decimal(indicadores.meses_de_colchon)
              if indicadores.gasto_medio > 0 else "—",
              "", "con el saldo de hoy, a tu ritmo de gasto")
        poner("mayor", "Mes de mayor gasto", indicadores.mes_mayor_gasto or "—", "Suave")
        poner("cartera", "Valor de la cartera", formato.euros(indicadores.valor_cartera), "",
              f"{formato.euros_con_signo(indicadores.generado_mercado)} del mercado"
              if indicadores.total_aportado > 0 else "")

        hay_datos = total.hay_datos
        if hay_datos:
            self.sin_datos.pack_forget()
        else:
            self.sin_datos.configure(
                text=f"No hay movimientos en {self.anio}.\n"
                     "Elige otro año arriba, o empieza a apuntar.")
            if not self.sin_datos.winfo_ismapped():
                self.sin_datos.pack(pady=(6, 0))

    def _pintar_meses(self, resumen) -> None:
        etiquetas = [m.corto for m in resumen.meses]
        self.grafico.dibujar((etiquetas, [
            ("Ingresos", widgets.PALETA.ingreso, [m.totales.ingresos for m in resumen.meses]),
            ("Gastos", widgets.PALETA.gasto, [m.totales.gastos for m in resumen.meses]),
            ("Inversión", widgets.PALETA.inversion, [m.totales.inversion for m in resumen.meses]),
        ]))

        filas = []
        for mes in resumen.meses:
            vacio = not mes.hay_datos
            filas.append((mes.clave, (
                mes.nombre.capitalize(),
                formato.euros(mes.totales.ingresos) if mes.totales.ingresos else "—",
                formato.euros(mes.totales.gastos) if mes.totales.gastos else "—",
                formato.euros(mes.totales.ahorro) if not vacio else "—",
                formato.euros(mes.totales.inversion) if mes.totales.inversion else "—",
                formato.euros(mes.saldo_final),
            ), ("suave",) if vacio else ()))

        total = resumen.total
        filas.append(("total", (
            f"TOTAL {resumen.anio}",
            formato.euros(total.ingresos),
            formato.euros(total.gastos),
            formato.euros(total.ahorro),
            formato.euros(total.inversion),
            "",
        ), ("total",)))
        self.tabla_meses.poner(filas)

    def _pintar_reparto(self, tabla, reparto, etiqueta: str) -> None:
        filas = []
        for indice, registro in enumerate(reparto.filas):
            if not registro.importe:
                continue
            filas.append((f"{etiqueta}-{indice}", (
                registro.nombre,
                formato.euros(registro.importe),
                formato.porcentaje(registro.porcentaje),
                _barra_de_texto(registro.porcentaje),
            ), ()))

        if filas:
            filas.append((f"{etiqueta}-total",
                          ("Total", formato.euros(reparto.total), "", ""), ("total",)))
        tabla.poner(filas)
        tabla.ajustar_alto(len(filas) or 3, minimo=4, maximo=14)

    def al_entrar(self) -> None:
        self.desplazable.arriba()


def _barra_de_texto(fraccion: float, ancho: int = 14) -> str:
    """Una barra hecha con bloques Unicode.

    Un Treeview no admite widgets dentro de las celdas, así que la barra se
    dibuja con caracteres. Queda menos fina que un lienzo, pero se alinea sola
    con el resto de la tabla y se ordena bien.
    """
    if not (fraccion == fraccion) or fraccion <= 0:
        return ""
    llenos = max(1, min(ancho, round(fraccion * ancho)))
    return "█" * llenos + "·" * (ancho - llenos)


def _color(valor: float) -> str:
    if valor > 0:
        return "Ingreso"
    if valor < 0:
        return "Gasto"
    return "Suave"
