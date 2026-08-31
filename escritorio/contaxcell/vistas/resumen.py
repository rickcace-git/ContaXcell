"""Cómo va la cuenta: los tramos del periodo, en qué se va el dinero y los
indicadores.

Es la pantalla de mirar hacia atrás. Los números finos están en las tablas; el
gráfico está para ver la forma del periodo de un vistazo.

Se puede mirar un año entero (los doce meses), varios años seguidos (un tramo
por año) o un mes suelto. Dentro de un mes no hay «mes a mes» que enseñar, así
que esa tarjeta desaparece y quedan las cifras y el reparto por categorías,
que es lo que sí tiene sentido a esa escala.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .. import calculos, dialogos, formato, widgets
from ..modelo import nombre_mes

UN_ANIO = "Un año"
VARIOS_ANIOS = "Varios años"
UN_MES = "Un mes"
MODOS = (UN_ANIO, VARIOS_ANIOS, UN_MES)

# La opción de «varios años» que lo coge todo. Las demás son «Últimos N años».
TODO = "Todo"


class VistaResumen:
    def __init__(self, padre, app):
        self.app = app
        self.modo = UN_ANIO
        self.anio = None
        self.mes = ""
        self.cuantos_anios = TODO
        # Qué juego de cifras está puesto: el de un mes no lleva las medias,
        # que en un mes suelto serían el propio total repetido.
        self._panel = ""
        self._meses_por_etiqueta: dict[str, str] = {}

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

        ttk.Label(self.tarjeta_indicadores.derecha, text="Ver",
                  style="Tarjeta.Suave.TLabel").pack(side="left", padx=(0, 6))
        self.var_modo = tk.StringVar(value=UN_ANIO)
        self.campo_modo = ttk.Combobox(self.tarjeta_indicadores.derecha,
                                       textvariable=self.var_modo, values=list(MODOS),
                                       state="readonly", width=12)
        self.campo_modo.pack(side="left", padx=(0, 6))
        self.campo_modo.bind("<<ComboboxSelected>>", lambda _e: self._cambio_de_modo())

        self.var_cual = tk.StringVar()
        self.campo_cual = ttk.Combobox(self.tarjeta_indicadores.derecha,
                                       textvariable=self.var_cual,
                                       state="readonly", width=15)
        self.campo_cual.pack(side="left")
        self.campo_cual.bind("<<ComboboxSelected>>", lambda _e: self._cambio_de_cual())

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
        # Guardado porque la tarjeta de los tramos se quita y se vuelve a
        # poner, y tiene que volver a su sitio: justo encima de esta fila.
        fila = self.fila_repartos = ttk.Frame(padre)
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
            widgets.Columna("importe", "Importe", 110, anclaje="e"),
            widgets.Columna("porcentaje", "%", 70, anclaje="e"),
            # Las barras se dibujan con caracteres: en un Treeview no se pueden
            # meter widgets dentro de una celda.
            widgets.Columna("barra", "", 110),
        ], alto=9)
        tabla.pack(fill="both", expand=True)
        return tabla

    # --- qué periodo se está mirando --------------------------------------

    def _cambio_de_modo(self) -> None:
        self.modo = self.var_modo.get()
        # La segunda lista cambia entera: años, meses o «últimos N años». Se
        # deja que `refrescar` elija el primer valor que encaje.
        self.refrescar()

    def _cambio_de_cual(self) -> None:
        elegido = self.var_cual.get()
        if self.modo == UN_ANIO:
            try:
                self.anio = int(elegido)
            except ValueError:
                return
        elif self.modo == UN_MES:
            self.mes = self._meses_por_etiqueta.get(elegido, self.mes)
        else:
            self.cuantos_anios = elegido
        self.refrescar()

    def _opciones(self, anios: list[int], meses: list[str]) -> tuple[list[str], str]:
        """Lo que va en la segunda lista y qué hay elegido, según el modo."""
        if self.modo == UN_ANIO:
            if self.anio not in anios:
                self.anio = anios[0]
            return [str(a) for a in anios], str(self.anio)

        if self.modo == UN_MES:
            etiquetas = [nombre_mes(m).capitalize() for m in meses]
            self._meses_por_etiqueta = dict(zip(etiquetas, meses))
            if self.mes not in meses:
                self.mes = meses[0]
            return etiquetas, nombre_mes(self.mes).capitalize()

        # Varios años: no hay que elegirlos uno a uno, basta con decir cuántos
        # hacia atrás. Se cuenta el hueco entre el primero y el último, no
        # cuántos años tienen datos: un año en blanco por medio también es
        # parte de la cuenta.
        cuantos_hay = max(anios) - min(anios) + 1
        opciones = [TODO] + [f"Últimos {n} años" for n in range(2, 6) if n < cuantos_hay]
        if self.cuantos_anios not in opciones:
            self.cuantos_anios = TODO
        return opciones, self.cuantos_anios

    def _periodo(self, anios: list[int]) -> tuple[str, str, str, str, str]:
        """(desde, hasta, en qué se parte, cómo se llama, coletilla)."""
        if self.modo == UN_MES:
            # Dentro de un mes los tramos son los días: la misma tarjeta, con
            # una barra por día en vez de por mes.
            return (self.mes, self.mes, calculos.POR_DIAS,
                    nombre_mes(self.mes).capitalize(), "del mes")

        if self.modo == UN_ANIO:
            return (f"{self.anio:04d}-01", f"{self.anio:04d}-12", calculos.POR_MESES,
                    str(self.anio), "del año")

        ultimo = max(anios)
        primero = min(anios)
        if self.cuantos_anios != TODO:
            try:
                primero = max(primero, ultimo - int(self.cuantos_anios.split()[1]) + 1)
            except (IndexError, ValueError):
                pass
        # Con un año solo no hay «año a año» que enseñar: se parte en meses,
        # que es lo que se ve cuando se pide ese año a secas.
        if primero == ultimo:
            return (f"{primero:04d}-01", f"{ultimo:04d}-12", calculos.POR_MESES,
                    str(primero), "del año")
        return (f"{primero:04d}-01", f"{ultimo:04d}-12", calculos.POR_ANIOS,
                f"{primero}–{ultimo}", "del periodo")

    # --- refresco ---------------------------------------------------------

    def refrescar(self) -> None:
        libro = self.app.libro
        anios = calculos.anios_con_datos(libro)
        meses = calculos.meses_con_datos(libro)

        if self.modo not in MODOS:
            self.modo = UN_ANIO
        self.var_modo.set(self.modo)
        opciones, elegido = self._opciones(anios, meses)
        self.campo_cual.configure(values=opciones)
        self.var_cual.set(elegido)

        desde, hasta, particion, etiqueta, coletilla = self._periodo(anios)
        resumen = calculos.resumen_periodo(libro, desde, hasta, particion)
        indicadores = calculos.indicadores_de(libro, desde, hasta, particion)

        self.tarjeta_indicadores.titulo(f"Resumen de {etiqueta}")
        self._pintar_indicadores(resumen, indicadores, etiqueta, coletilla)
        self._pintar_tramos(resumen, etiqueta)
        self._pintar_reparto(self.tabla_gasto, resumen.gasto, "gasto")
        self._pintar_reparto(self.tabla_ingreso, resumen.ingreso, "ingreso")

    def _pintar_indicadores(self, resumen, indicadores, etiqueta: str,
                            coletilla: str) -> None:
        total = resumen.total
        # Dentro de un mes, «gasto medio al mes» sería el mismo total otra vez,
        # así que ese panel lleva otras casillas y hay que rehacerlo al cambiar.
        panel = "mes" if self.modo == UN_MES else "tramos"
        if panel != self._panel:
            self.cifras.limpiar()
            self._panel = panel
        poner = self.cifras.poner

        poner("ingresos", f"Ingresos {coletilla}", formato.euros(total.ingresos), "Ingreso")
        poner("gastos", f"Gastos {coletilla}", formato.euros(total.gastos), "Gasto")
        poner("ahorro", f"Ahorro {coletilla}", formato.euros(total.ahorro), _color(total.ahorro),
              f"{formato.porcentaje(total.tasa_ahorro)} de lo ingresado"
              if total.ingresos > 0 else "")
        poner("inversion", "Aportado a inversión", formato.euros(total.inversion), "Inversion")
        poner("patrimonio", "Patrimonio", formato.euros(indicadores.patrimonio), "",
              "banco + cartera")

        meses = indicadores.meses_con_datos
        if panel == "tramos":
            poner("gasto_medio", "Gasto medio al mes",
                  formato.euros(indicadores.gasto_medio), "",
                  f"{meses} mes con datos" if meses == 1 else f"{meses} meses con datos")
            poner("ahorro_medio", "Ahorro medio al mes",
                  formato.euros(indicadores.ahorro_medio),
                  _color(indicadores.ahorro_medio))

        poner("colchon", "Meses de colchón",
              formato.decimal(indicadores.meses_de_colchon)
              if indicadores.gasto_medio > 0 else "—",
              "", "con el saldo de hoy, a tu ritmo de gasto",
              ayuda=lambda r=resumen, i=indicadores, e=etiqueta:
                    self._explicar_colchon(r, i, e))

        if panel == "tramos":
            poner("mayor",
                  "Año de mayor gasto" if resumen.particion == calculos.POR_ANIOS
                  else "Mes de mayor gasto",
                  indicadores.tramo_mayor_gasto.capitalize() or "—", "Suave")
        else:
            # En un mes suelto el tramo de mayor gasto sería el propio mes. Lo
            # que sí dice algo es cuál fue el gasto más gordo.
            mayor = indicadores.mayor_gasto
            poner("mayor_gasto", "Mayor gasto",
                  formato.euros(mayor.importe) if mayor else "—", "Gasto",
                  (mayor.descripcion or mayor.categoria) if mayor else "")

        poner("cartera", "Valor de la cartera", formato.euros(indicadores.valor_cartera), "",
              f"{formato.euros_con_signo(indicadores.generado_mercado)} del mercado"
              if indicadores.total_aportado > 0 else "")

        if total.hay_datos:
            self.sin_datos.pack_forget()
        else:
            self.sin_datos.configure(
                text=f"No hay movimientos en {etiqueta}.\n"
                     "Elige otro periodo arriba, o empieza a apuntar.")
            if not self.sin_datos.winfo_ismapped():
                self.sin_datos.pack(pady=(6, 0))

    # Cómo se llama cada partición en la tarjeta, en la columna y en el saldo.
    ROTULOS = {
        calculos.POR_DIAS: ("Día a día", "Día", "Saldo a fin de día"),
        calculos.POR_MESES: ("Mes a mes", "Mes", "Saldo a fin de mes"),
        calculos.POR_ANIOS: ("Año a año", "Año", "Saldo a fin de año"),
    }

    def _pintar_tramos(self, resumen, etiqueta: str) -> None:
        # Sin nada apuntado, un gráfico de barras a cero y una tabla de rayas
        # no dicen nada: arriba ya pone que no hay movimientos.
        if len(resumen.tramos) <= 1 or not resumen.total.hay_datos:
            self.tarjeta_meses.pack_forget()
            return
        if not self.tarjeta_meses.winfo_ismapped():
            self.tarjeta_meses.pack(fill="x", pady=(16, 0), before=self.fila_repartos)

        por_dias = resumen.particion == calculos.POR_DIAS
        titulo, columna, saldo = self.ROTULOS[resumen.particion]
        self.tarjeta_meses.titulo(titulo)
        self.tabla_meses.titulo_columna("mes", columna)
        self.tabla_meses.titulo_columna("saldo", saldo)

        tramos = resumen.tramos
        self.grafico.dibujar(([t.corto for t in tramos], [
            ("Ingresos", widgets.PALETA.ingreso, [t.totales.ingresos for t in tramos]),
            ("Gastos", widgets.PALETA.gasto, [t.totales.gastos for t in tramos]),
            ("Inversión", widgets.PALETA.inversion, [t.totales.inversion for t in tramos]),
        ]))

        filas = []
        for tramo in tramos:
            vacio = not tramo.hay_datos
            # Un mes tiene treinta y un días y casi ninguno tiene nada: la
            # tabla se queda solo con los que sí. En el gráfico siguen todos,
            # que ahí los huecos son parte de la forma del mes.
            if vacio and por_dias:
                continue
            filas.append((tramo.clave, (
                tramo.nombre.capitalize(),
                formato.euros(tramo.totales.ingresos) if tramo.totales.ingresos else "—",
                formato.euros(tramo.totales.gastos) if tramo.totales.gastos else "—",
                formato.euros(tramo.totales.ahorro) if not vacio else "—",
                formato.euros(tramo.totales.inversion) if tramo.totales.inversion else "—",
                formato.euros(tramo.saldo_final),
            ), ("suave",) if vacio else ()))

        total = resumen.total
        filas.append(("total", (
            f"TOTAL {etiqueta}",
            formato.euros(total.ingresos),
            formato.euros(total.gastos),
            formato.euros(total.ahorro),
            formato.euros(total.inversion),
            "",
        ), ("total",)))
        self.tabla_meses.poner(filas)
        self.tabla_meses.ajustar_alto(len(filas), minimo=4, maximo=14)

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

    # --- explicaciones ----------------------------------------------------

    def _explicar_colchon(self, resumen, ind, etiqueta: str) -> None:
        """La cuenta del colchón, con las cifras del año que se está mirando.

        Es el indicador que más se malinterpreta: con pocos meses apuntados da
        un número altísimo y tranquilizador que no significa nada, así que la
        explicación avisa cuando ese es el caso.
        """
        meses = ind.meses_con_datos

        if ind.gasto_medio <= 0:
            dialogos.Explicacion(
                self.app, "Meses de colchón",
                "Cuántos meses aguantarías con lo que hay en el banco si dejaras "
                "de ingresar y siguieras gastando a tu ritmo.",
                cuenta=[],
                detalle=f"Todavía no se puede calcular: no hay ningún gasto apuntado "
                        f"en {etiqueta}. En cuanto empieces a apuntar aparecerá "
                        f"la cifra.").mostrar()
            return

        cuenta = [
            (f"Gastos de {etiqueta}", formato.euros(resumen.total.gastos)),
            ("Meses con datos", "1 mes" if meses == 1 else f"{meses} meses"),
            (None, None),
            ("Gasto medio al mes", formato.euros(ind.gasto_medio)),
            ("Saldo del banco hoy", formato.euros(ind.saldo_banco)),
            (None, None),
            ("Meses de colchón", f"{formato.decimal(ind.meses_de_colchon)} meses"),
        ]

        detalle = (
            "Se divide lo que tienes en el banco entre lo que gastas en un mes "
            "normal. El gasto medio sale de los gastos del año repartidos entre "
            "los meses en los que apuntaste algo.\n\n"
            "Las aportaciones a inversión no cuentan como gasto: si te quedaras "
            "sin ingresos, dejar de invertir es lo primero que harías, así que no "
            "es dinero que estés obligado a sacar todos los meses."
        )

        aviso = ""
        if meses < 3:
            aviso = (
                f"Ojo: solo hay {'1 mes' if meses == 1 else f'{meses} meses'} con "
                "datos, así que esta cifra no es de fiar todavía. Si aún no estás "
                "apuntándolo todo, el gasto medio sale bajo y el colchón sale "
                "mucho más grande de lo que es. Empieza a ser fiable a partir de "
                "tres o cuatro meses completos."
            )

        dialogos.Explicacion(
            self.app, "Meses de colchón",
            "Cuántos meses aguantarías con lo que hay en el banco si dejaras de "
            "ingresar y siguieras gastando a tu ritmo.",
            cuenta=cuenta, detalle=detalle, aviso=aviso).mostrar()

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
