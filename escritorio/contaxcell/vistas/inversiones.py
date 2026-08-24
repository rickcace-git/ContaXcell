"""La cartera.

La idea que ordena toda esta pantalla: hay tres formas de que entre dinero en
la cartera —lo que pusiste al empezar, lo que aportas desde el banco y lo que
te regalan— y ninguna de las tres es rentabilidad. Lo que ha hecho el mercado
es lo que vale hoy menos las tres juntas.
"""

from __future__ import annotations

import datetime as dt
from tkinter import ttk

from .. import calculos, dialogos, formato, widgets
from ..modelo import Activo, AportacionGratis, Valoracion, hoy
from . import comun


class VistaInversiones:
    def __init__(self, padre, app):
        self.app = app
        self._avisos: list[widgets.Aviso] = []

        self.desplazable = widgets.MarcoDesplazable(padre)
        self.desplazable.pack(fill="both", expand=True)
        raiz = ttk.Frame(self.desplazable.interior, padding=18)
        raiz.pack(fill="both", expand=True)

        self._resumen(raiz)
        self._activos(raiz)
        self._historico(raiz)
        self._gratis(raiz)

    # --- construcción -----------------------------------------------------

    def _resumen(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "La cartera")
        tarjeta.pack(fill="x")
        self.cifras = widgets.PanelCifras(tarjeta.cuerpo, columnas=4)
        self.cifras.pack(fill="x")
        self.cifras_origen = widgets.PanelCifras(tarjeta.cuerpo, columnas=4)
        self.cifras_origen.pack(fill="x")

        self.zona_avisos = ttk.Frame(padre)
        self.zona_avisos.pack(fill="x")

    def _activos(self, padre) -> None:
        self.tarjeta_activos = widgets.Tarjeta(padre, "Activos")
        self.tarjeta_activos.pack(fill="x", pady=(16, 0))
        ttk.Button(self.tarjeta_activos.derecha, text="Añadir activo",
                   command=self.anadir_activo).pack(side="right")

        self.tabla_activos = widgets.Tabla(self.tarjeta_activos.cuerpo, [
            widgets.Columna("nombre", "Activo", 170, estira=True),
            widgets.Columna("inicial", "1 · Inicial", 105, anclaje="e"),
            widgets.Columna("banco", "2 · Del banco", 115, anclaje="e"),
            widgets.Columna("gratis", "3 · Gratis", 100, anclaje="e"),
            widgets.Columna("aportado", "Total aportado", 125, anclaje="e"),
            widgets.Columna("valor", "Valor de mercado", 135, anclaje="e"),
            widgets.Columna("generado", "Generado", 115, anclaje="e"),
            widgets.Columna("rentabilidad", "Rentab.", 85, anclaje="e"),
            widgets.Columna("valoracion", "Última valoración", 130),
        ], alto=6, al_activar=lambda _c: self.editar_activo())
        self.tabla_activos.pack(fill="x")

        self.vacio_activos = ttk.Label(
            self.tarjeta_activos.cuerpo, style="Tarjeta.Suave.TLabel", justify="center",
            text="Todavía no has creado ningún activo.\n\nUn activo es cada sitio donde "
                 "tienes dinero invertido: un fondo, una cuenta remunerada, oro…")

        self.acciones_activos = ttk.Frame(self.tarjeta_activos.cuerpo, style="Tarjeta.TFrame")
        self.acciones_activos.pack(fill="x", pady=(10, 0))
        ttk.Button(self.acciones_activos, text="Editar",
                   command=self.editar_activo).pack(side="left")
        ttk.Button(self.acciones_activos, text="Quitar", style="Peligro.TButton",
                   command=self.quitar_activo).pack(side="left", padx=(8, 0))
        ttk.Label(self.acciones_activos, style="Tarjeta.Suave.TLabel",
                  text="Las columnas 2 y 3 se calculan solas: tú escribes la aportación "
                       "inicial y lo que vale hoy.").pack(side="right")

    def _historico(self, padre) -> None:
        self.tarjeta_historico = widgets.Tarjeta(padre, "Histórico de la cartera")
        self.tarjeta_historico.pack(fill="x", pady=(16, 0))
        ttk.Button(self.tarjeta_historico.derecha, text="Apuntar valoración",
                   command=self.anadir_valoracion).pack(side="right")

        self.grafico = widgets.GraficoLineas(self.tarjeta_historico.cuerpo, alto=200)
        self.leyenda = widgets.Leyenda(self.tarjeta_historico.cuerpo, [
            (widgets.PALETA.acento, "Valor de mercado"),
            (widgets.PALETA.suave, "Total aportado"),
        ])

        self.tabla_historico = widgets.Tabla(self.tarjeta_historico.cuerpo, [
            widgets.Columna("fecha", "Fecha", 120, estira=True),
            widgets.Columna("aportado", "Aportado acumulado", 165, anclaje="e"),
            widgets.Columna("valor", "Valor de mercado", 150, anclaje="e"),
            widgets.Columna("generado", "Generado", 130, anclaje="e"),
            widgets.Columna("rentabilidad", "Rentab.", 95, anclaje="e"),
        ], alto=6)

        self.vacio_historico = ttk.Label(
            self.tarjeta_historico.cuerpo, style="Tarjeta.Suave.TLabel", justify="center",
            text="Aún no has apuntado ninguna valoración.\n\nCada cierto tiempo, a fin de "
                 "mes por ejemplo, apunta lo que vale la cartera entera. Lo aportado hasta "
                 "esa fecha se calcula solo, y la diferencia es lo que ha hecho el mercado.")

        self.acciones_historico = ttk.Frame(self.tarjeta_historico.cuerpo,
                                            style="Tarjeta.TFrame")
        self.acciones_historico.pack(fill="x", pady=(10, 0))
        ttk.Button(self.acciones_historico, text="Borrar valoración",
                   style="Peligro.TButton",
                   command=self.borrar_valoracion).pack(side="left")

    def _gratis(self, padre) -> None:
        self.tarjeta_gratis = widgets.Tarjeta(padre, "Aportaciones gratis")
        self.tarjeta_gratis.pack(fill="x", pady=(16, 0))
        ttk.Button(self.tarjeta_gratis.derecha, text="Añadir aportación",
                   command=self.anadir_aportacion).pack(side="right")

        self.tabla_gratis = widgets.Tabla(self.tarjeta_gratis.cuerpo, [
            widgets.Columna("fecha", "Fecha", 120),
            widgets.Columna("activo", "Activo", 160),
            widgets.Columna("concepto", "Concepto", 260, estira=True),
            widgets.Columna("importe", "Importe", 120, anclaje="e"),
        ], alto=5)

        self.vacio_gratis = ttk.Label(self.tarjeta_gratis.cuerpo,
                                      style="Tarjeta.Suave.TLabel", justify="center",
                                      text="Nada apuntado todavía.")

        self.acciones_gratis = ttk.Frame(self.tarjeta_gratis.cuerpo, style="Tarjeta.TFrame")
        self.acciones_gratis.pack(fill="x", pady=(10, 0))
        ttk.Button(self.acciones_gratis, text="Borrar", style="Peligro.TButton",
                   command=self.borrar_aportacion).pack(side="left")
        ttk.Label(self.acciones_gratis, style="Tarjeta.Suave.TLabel", justify="right",
                  text="Dinero que entra en la cartera sin salir de tu cuenta: cashback, "
                       "promociones, redondeos. No es un ingreso ni un gasto, así que no "
                       "se apunta en Movimientos.", wraplength=520).pack(side="right")

    # --- activos ----------------------------------------------------------

    def anadir_activo(self) -> None:
        resultado = dialogos.Formulario(self.app, "Nuevo activo", [
            dialogos.Texto("nombre", "Nombre", pista="Fondo indexado", obligatorio=True),
            dialogos.Importe("inicial", "Aportación inicial", 0,
                             ayuda="Lo que ya tenías dentro antes de empezar a apuntar "
                                   "aportaciones en esta aplicación."),
            dialogos.Importe("valor", "Valor de mercado hoy", 0),
        ], aceptar="Crear", validar=self._validar_nombre_libre).mostrar()
        if resultado is None:
            return

        nuevo = Activo(nombre=resultado["nombre"],
                       aportacion_inicial=resultado["inicial"],
                       valor_mercado=resultado["valor"],
                       ultima_valoracion=hoy())
        self.app.cambiar(lambda libro: libro.activos.append(nuevo),
                         f"Activo «{nuevo.nombre}» creado.")

    def _validar_nombre_libre(self, valores, excepto: str = "") -> str | None:
        nombre = valores["nombre"]
        for activo in self.app.libro.activos:
            if activo.nombre == nombre and nombre != excepto:
                return "Ya tienes un activo con ese nombre."
        return None

    def _activo_seleccionado(self) -> Activo | None:
        clave = self.tabla_activos.seleccion()
        if clave is None:
            self.app.estado("Elige antes un activo de la lista.", "malo")
            return None
        return self.app.libro.activo(clave)

    def editar_activo(self) -> None:
        activo = self._activo_seleccionado()
        if activo is None:
            return
        anterior = activo.nombre

        resultado = dialogos.Formulario(self.app, f"Editar «{anterior}»", [
            dialogos.Texto("nombre", "Nombre", activo.nombre, obligatorio=True),
            dialogos.Importe("inicial", "Aportación inicial", activo.aportacion_inicial),
            dialogos.Importe("valor", "Valor de mercado hoy", activo.valor_mercado),
            dialogos.Fecha("valoracion", "Fecha de esa valoración",
                           activo.ultima_valoracion or hoy()),
        ], validar=lambda v: self._validar_nombre_libre(v, excepto=anterior)).mostrar()
        if resultado is None:
            return

        def aplicar(libro):
            objetivo = libro.activo(anterior)
            if objetivo is None:
                raise ValueError("Ese activo ya no existe.")
            nuevo_nombre = resultado["nombre"]
            if nuevo_nombre != anterior:
                # Renombrar arrastra lo que apuntaba al nombre viejo; si no,
                # esas aportaciones se quedarían sin asignar.
                for movimiento in libro.movimientos:
                    if movimiento.activo == anterior:
                        movimiento.activo = nuevo_nombre
                for aportacion in libro.aportaciones_gratis:
                    if aportacion.activo == anterior:
                        aportacion.activo = nuevo_nombre
            objetivo.nombre = nuevo_nombre
            objetivo.aportacion_inicial = resultado["inicial"]
            objetivo.valor_mercado = resultado["valor"]
            objetivo.ultima_valoracion = resultado["valoracion"]

        self.app.cambiar(aplicar, "Activo actualizado.")

    def quitar_activo(self) -> None:
        activo = self._activo_seleccionado()
        if activo is None:
            return
        usados = sum(1 for m in self.app.libro.movimientos if m.activo == activo.nombre)
        detalle = (
            f"Los {usados} movimientos que apuntaban a este activo no se borran, pero "
            "se quedarán sin asignar y aparecerán como aportaciones sueltas."
            if usados else "No hay ningún movimiento asignado a este activo.")
        if not dialogos.confirmar(self.app, f"¿Quitar «{activo.nombre}» de la cartera?",
                                  detalle):
            return

        nombre = activo.nombre

        def aplicar(libro):
            objetivo = libro.activo(nombre)
            if objetivo is not None:
                libro.activos.remove(objetivo)

        self.app.cambiar(aplicar, f"Activo «{nombre}» quitado.")

    # --- histórico --------------------------------------------------------

    def anadir_valoracion(self) -> None:
        resultado = dialogos.Formulario(self.app, "Apuntar una valoración", [
            dialogos.Fecha("fecha", "Fecha", hoy()),
            dialogos.Importe("valor", "¿Cuánto vale la cartera entera ese día?"),
            dialogos.Nota("El valor de toda la cartera junta, no el de un activo suelto. "
                          "Si apuntas dos veces la misma fecha, se queda la última."),
        ], aceptar="Apuntar").mostrar()
        if resultado is None:
            return

        def aplicar(libro):
            for valoracion in libro.historico:
                if valoracion.fecha == resultado["fecha"]:
                    valoracion.valor_mercado = resultado["valor"]
                    return
            libro.historico.append(Valoracion(fecha=resultado["fecha"],
                                              valor_mercado=resultado["valor"]))

        self.app.cambiar(aplicar, "Valoración apuntada.")

    def borrar_valoracion(self) -> None:
        clave = self.tabla_historico.seleccion()
        if clave is None:
            self.app.estado("Elige antes una valoración de la lista.", "malo")
            return
        punto = next((v for v in self.app.libro.historico if v.id == clave), None)
        if punto is None:
            return
        if not dialogos.confirmar(
                self.app, "¿Borrar esta valoración?",
                f"{formato.fecha_corta(punto.fecha)} · "
                f"{formato.euros(punto.valor_mercado, siempre_visible=True)}"):
            return
        self.app.cambiar(
            lambda libro: libro.historico.remove(
                next(v for v in libro.historico if v.id == clave)),
            "Valoración borrada.")

    # --- aportaciones gratis ---------------------------------------------

    def anadir_aportacion(self) -> None:
        nombres = [a.nombre for a in self.app.libro.activos]
        resultado = dialogos.Formulario(self.app, "Aportación gratis", [
            dialogos.Fecha("fecha", "Fecha", hoy()),
            dialogos.Opcion("activo", "Activo", nombres,
                            nombres[0] if len(nombres) == 1 else "",
                            vacio=comun.SIN_ASIGNAR),
            dialogos.Texto("concepto", "Concepto", pista="Cashback 1% de la tarjeta"),
            dialogos.Importe("importe", "Importe", permitir_cero=False),
        ], aceptar="Añadir").mostrar()
        if resultado is None:
            return

        nueva = AportacionGratis(fecha=resultado["fecha"], activo=resultado["activo"],
                                 concepto=resultado["concepto"], importe=resultado["importe"])
        self.app.cambiar(lambda libro: libro.aportaciones_gratis.append(nueva),
                         "Aportación añadida.")

    def borrar_aportacion(self) -> None:
        clave = self.tabla_gratis.seleccion()
        if clave is None:
            self.app.estado("Elige antes una aportación de la lista.", "malo")
            return
        aportacion = next((a for a in self.app.libro.aportaciones_gratis if a.id == clave), None)
        if aportacion is None:
            return
        etiqueta = " · ".join(p for p in (
            formato.fecha_corta(aportacion.fecha), aportacion.concepto,
            formato.euros(aportacion.importe, siempre_visible=True)) if p)
        if not dialogos.confirmar(self.app, "¿Borrar esta aportación?", etiqueta):
            return
        self.app.cambiar(
            lambda libro: libro.aportaciones_gratis.remove(
                next(a for a in libro.aportaciones_gratis if a.id == clave)),
            "Aportación borrada.")

    # --- refresco ---------------------------------------------------------

    def refrescar(self) -> None:
        cartera = calculos.cartera(self.app.libro)
        self._pintar_resumen(cartera)
        self._pintar_avisos(cartera)
        self._pintar_activos(cartera)
        self._pintar_historico(cartera)
        self._pintar_gratis()

    def _pintar_resumen(self, cartera) -> None:
        poner = self.cifras.poner
        poner("valor", "Valor de mercado", formato.euros(cartera.valor_mercado))
        poner("aportado", "Total aportado", formato.euros(cartera.total_aportado))
        poner("generado", "Generado por el mercado",
              formato.euros_con_signo(cartera.generado), _color(cartera.generado),
              formato.porcentaje(cartera.rentabilidad) if cartera.total_aportado > 0 else "")
        poner("sin_poner", "Ganado sin poner dinero",
              formato.euros_con_signo(cartera.ganado_sin_poner),
              _color(cartera.ganado_sin_poner), "mercado + aportaciones gratis")

        poner_origen = self.cifras_origen.poner
        poner_origen("inicial", "1 · Aportación inicial",
                     formato.euros(cartera.aportacion_inicial), "Suave")
        poner_origen("banco", "2 · Aportado del banco",
                     formato.euros(cartera.aportado_banco), "Suave")
        poner_origen("gratis", "3 · Aportado gratis",
                     formato.euros(cartera.aportado_gratis), "Suave")

    def _pintar_avisos(self, cartera) -> None:
        for aviso in self._avisos:
            aviso.destruir()
        self._avisos.clear()

        mensajes = []
        if abs(cartera.sin_asignar_banco) >= 0.01:
            mensajes.append(
                f"Hay {formato.euros(cartera.sin_asignar_banco)} aportados desde el banco "
                "sin asignar a ningún activo. Edita esos movimientos en la pestaña "
                "Movimientos y elige el activo.")
        if abs(cartera.sin_asignar_gratis) >= 0.01:
            mensajes.append(
                f"Hay {formato.euros(cartera.sin_asignar_gratis)} de aportaciones gratis "
                "sin asignar a ningún activo.")

        for texto in mensajes:
            aviso = widgets.Aviso(self.zona_avisos, texto, "alerta")
            aviso.pack(fill="x", pady=(12, 0))
            self._avisos.append(aviso)

    def _pintar_activos(self, cartera) -> None:
        filas = []
        for activo in cartera.activos:
            filas.append((activo.nombre, (
                activo.nombre,
                formato.euros(activo.aportacion_inicial),
                formato.euros(activo.aportado_banco),
                formato.euros(activo.aportado_gratis),
                formato.euros(activo.total_aportado),
                formato.euros(activo.valor_mercado),
                formato.euros_con_signo(activo.generado),
                formato.porcentaje(activo.rentabilidad) if activo.total_aportado > 0 else "—",
                formato.fecha_corta(activo.ultima_valoracion),
            ), ()))

        if filas:
            filas.append(("__total__", (
                "TOTAL CARTERA",
                formato.euros(cartera.aportacion_inicial),
                formato.euros(cartera.aportado_banco),
                formato.euros(cartera.aportado_gratis),
                formato.euros(cartera.total_aportado),
                formato.euros(cartera.valor_mercado),
                formato.euros_con_signo(cartera.generado),
                formato.porcentaje(cartera.rentabilidad) if cartera.total_aportado > 0 else "—",
                "",
            ), ("total",)))

        self.tabla_activos.poner(filas)
        self.tabla_activos.ajustar_alto(len(filas), minimo=3, maximo=12)
        _alternar(self.tabla_activos, self.vacio_activos, bool(cartera.activos),
                  self.acciones_activos)

    def _pintar_historico(self, cartera) -> None:
        puntos = cartera.historico
        filas = [(punto.id, (
            formato.fecha_corta(punto.fecha),
            formato.euros(punto.aportado),
            formato.euros(punto.valor_mercado),
            formato.euros_con_signo(punto.generado),
            formato.porcentaje(punto.rentabilidad) if punto.aportado > 0 else "—",
        ), ()) for punto in reversed(puntos)]
        self.tabla_historico.poner(filas)
        self.tabla_historico.ajustar_alto(len(filas), minimo=3, maximo=12)

        # El gráfico necesita al menos dos puntos para dibujar una línea.
        if len(puntos) >= 2:
            self.grafico.dibujar([(_dia(p.fecha), p.aportado, p.valor_mercado)
                                  for p in puntos])
            if not self.grafico.winfo_ismapped():
                self.grafico.pack(fill="x", before=self.acciones_historico)
                self.leyenda.pack(anchor="w", pady=(6, 12), before=self.acciones_historico)
        else:
            self.grafico.pack_forget()
            self.leyenda.pack_forget()

        _alternar(self.tabla_historico, self.vacio_historico, bool(puntos),
                  self.acciones_historico)

    def _pintar_gratis(self) -> None:
        aportaciones = sorted(self.app.libro.aportaciones_gratis,
                              key=lambda a: a.fecha, reverse=True)
        filas = [(a.id, (
            formato.fecha_corta(a.fecha),
            a.activo or comun.SIN_ASIGNAR,
            a.concepto or "—",
            formato.euros(a.importe),
        ), ("ingreso",)) for a in aportaciones]

        if filas:
            total = calculos.redondea(sum(a.importe for a in aportaciones))
            filas.append(("__total__", ("TOTAL GRATIS", "", "", formato.euros(total)),
                          ("total",)))

        self.tabla_gratis.poner(filas)
        self.tabla_gratis.ajustar_alto(len(filas), minimo=3, maximo=12)
        _alternar(self.tabla_gratis, self.vacio_gratis, bool(aportaciones),
                  self.acciones_gratis)

    def al_entrar(self) -> None:
        self.desplazable.arriba()


def _alternar(tabla, etiqueta_vacia, hay_datos: bool, antes) -> None:
    """Enseña la tabla o el texto de «aquí no hay nada», nunca los dos."""
    if hay_datos:
        etiqueta_vacia.pack_forget()
        if not tabla.winfo_ismapped():
            tabla.pack(fill="x", before=antes)
    else:
        tabla.pack_forget()
        if not etiqueta_vacia.winfo_ismapped():
            etiqueta_vacia.pack(pady=30, before=antes)


def _dia(iso: str) -> int:
    """Número de día absoluto, para que el eje del gráfico sea tiempo real."""
    fecha = dt.date.fromisoformat(iso)
    return fecha.toordinal()


def _color(valor: float) -> str:
    if valor > 0:
        return "Ingreso"
    if valor < 0:
        return "Gasto"
    return "Suave"
