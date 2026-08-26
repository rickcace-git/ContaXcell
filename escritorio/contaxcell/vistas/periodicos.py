"""Los pagos que se repiten solos: suscripciones, alquiler, gimnasio, nómina
o la aportación de todos los meses a la cartera.

Aquí no se apunta nada: se describe lo que se repite y cada cuánto. Los
movimientos los fabrica `calculos.apuntar_pendientes` cuando llega el día, y
a partir de ahí son movimientos normales del libro.

Un periódico deja de fabricar pagos de dos maneras: apagándolo, que es lo que
se hace al darse de baja de algo, o llegando a su fecha de fin, para lo que se
acaba solo (las doce cuotas de un préstamo). Ninguna de las dos borra lo ya
apuntado: lo que se pagó, se pagó.
"""

from __future__ import annotations

from tkinter import ttk

from .. import calculos, dialogos, formato, widgets
from ..modelo import GASTO, PERIODOS, Periodico, hoy
from . import comun


class VistaPeriodicos:
    def __init__(self, padre, app):
        self.app = app

        raiz = ttk.Frame(padre, padding=18)
        raiz.pack(fill="both", expand=True)

        self._cabecera(raiz)
        self._tabla(raiz)

    # --- montaje ----------------------------------------------------------

    def _cabecera(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "Lo que se repite cada mes")
        tarjeta.pack(fill="x")

        self.cifras = widgets.PanelCifras(tarjeta.cuerpo, columnas=4)
        self.cifras.pack(fill="x")

    def _tabla(self, padre) -> None:
        self.tarjeta = widgets.Tarjeta(padre, "Periódicos")
        self.tarjeta.pack(fill="both", expand=True, pady=(16, 0))

        # Anclados al fondo antes que la tabla, para que no los desplace.
        acciones = ttk.Frame(self.tarjeta.cuerpo, style="Tarjeta.TFrame")
        acciones.pack(side="bottom", fill="x", pady=(10, 0))

        self.tabla = widgets.Tabla(self.tarjeta.cuerpo, [
            widgets.Columna("nombre", "Nombre", 190, estira=True),
            widgets.Columna("categoria", "Categoría", 170),
            widgets.Columna("importe", "Importe", 110, anclaje="e"),
            widgets.Columna("periodo", "Cada", 110),
            widgets.Columna("proximo", "Próximo pago", 130),
            widgets.Columna("estado", "Estado", 100),
        ], alto=12, al_activar=self._editar_seleccionado)
        self.tabla.pack(fill="both", expand=True)

        self.vacio = ttk.Label(self.tarjeta.cuerpo, style="Tarjeta.Suave.TLabel",
                               justify="center", text="")

        ttk.Button(acciones, text="Nuevo", style="Principal.TButton",
                   command=self.nuevo).pack(side="left")
        ttk.Button(acciones, text="Editar",
                   command=self._editar_seleccionado).pack(side="left", padx=(8, 0))
        self.boton_encendido = ttk.Button(acciones, text="Apagar",
                                          command=self._alternar_seleccionado)
        self.boton_encendido.pack(side="left", padx=(8, 0))
        ttk.Button(acciones, text="Borrar", style="Peligro.TButton",
                   command=self._borrar_seleccionado).pack(side="left", padx=(8, 0))

        ttk.Label(self.tarjeta.derecha, text="Doble clic sobre una fila para editarla",
                  style="Tarjeta.Suave.TLabel").pack(side="right")

    # --- selección --------------------------------------------------------

    def _seleccionado(self) -> Periodico | None:
        clave = self.tabla.seleccion()
        if clave is None:
            self.app.estado("Elige antes uno de la lista.", "malo")
            return None
        return self.app.libro.periodico(clave)

    def _editar_seleccionado(self, _clave=None) -> None:
        periodico = self._seleccionado()
        if periodico:
            self.editar(periodico)

    def _alternar_seleccionado(self) -> None:
        periodico = self._seleccionado()
        if periodico:
            self.alternar(periodico)

    def _borrar_seleccionado(self) -> None:
        periodico = self._seleccionado()
        if periodico:
            self.borrar(periodico)

    # --- formulario -------------------------------------------------------

    def _campos(self, periodico: Periodico | None) -> list:
        libro = self.app.libro
        base = periodico or Periodico(nombre="", desde=hoy())
        return [
            dialogos.Texto("nombre", "Nombre", base.nombre,
                           pista="Gimnasio", obligatorio=True,
                           ayuda="Es lo que se escribirá como descripción de "
                                 "cada movimiento."),
            dialogos.Opcion("categoria", "Categoría",
                            [c.nombre for c in libro.categorias], base.categoria,
                            ayuda="La categoría manda: si eliges una de "
                                  "inversión, esto aporta a la cartera en vez "
                                  "de contar como gasto."),
            dialogos.Importe("importe", "Importe", base.importe or None,
                             permitir_cero=False),
            dialogos.Opcion("periodo", "Cada cuánto", list(PERIODOS), base.periodo),
            dialogos.Fecha("desde", "Primer pago", base.desde or hoy(),
                           ayuda="De esta fecha sale el día: si es mensual y "
                                 "cae en día 5, será el 5 de cada mes."),
            dialogos.Fecha("hasta", "Último pago", base.hasta, opcional=True,
                           ayuda="Déjalo en blanco si no se acaba nunca. Para "
                                 "un préstamo a 12 meses, la fecha de la "
                                 "última cuota: al llegar, para solo."),
            dialogos.Opcion("activo", "¿A qué activo?",
                            [a.nombre for a in libro.activos], base.activo,
                            vacio=comun.SIN_ASIGNAR),
        ]

    def _pedir_datos(self, titulo: str, periodico: Periodico | None,
                     aceptar: str) -> dict | None:
        libro = self.app.libro

        def al_cambiar(formulario, _evento):
            # La casilla del activo solo tiene sentido si aporta a la cartera.
            formulario.mostrar_campo(
                "activo", comun.es_aportacion(libro, formulario.valor("categoria")))

        def validar(datos):
            if not datos["categoria"]:
                return "Hay que elegir una categoría."
            if datos["hasta"] and datos["hasta"] < datos["desde"]:
                return ("El último pago no puede ser anterior al primero. "
                        "Déjalo en blanco si no se acaba nunca.")
            return ""

        datos = dialogos.Formulario(self.app, titulo, self._campos(periodico),
                                    aceptar=aceptar, al_cambiar=al_cambiar,
                                    validar=validar).mostrar()
        if datos is None:
            return None
        if not comun.es_aportacion(libro, datos["categoria"]):
            datos["activo"] = ""
        return datos

    # --- acciones ---------------------------------------------------------

    def nuevo(self) -> None:
        datos = self._pedir_datos("Nuevo pago periódico", None, "Crear")
        if datos is None:
            return

        nuevo = Periodico(
            nombre=datos["nombre"], categoria=datos["categoria"],
            importe=abs(datos["importe"]), periodo=datos["periodo"],
            desde=datos["desde"], hasta=datos["hasta"], activo=datos["activo"],
        )

        # Con una fecha de primer pago antigua hay que decidir qué se hace con
        # lo que ya ha pasado: rellenar el histórico o empezar desde hoy.
        pasados = [f for f in calculos.vencimientos(nuevo, hoy()) if f < hoy()]
        if pasados and not self._rellenar_el_pasado(nuevo, pasados):
            calculos.saltar_lo_pasado(nuevo, hoy())

        creados: list = []

        def aplicar(libro_actual):
            libro_actual.periodicos.append(nuevo)
            creados.extend(calculos.apuntar_pendientes(libro_actual, hoy()))

        if self.app.cambiar(aplicar):
            self.app.estado(f"«{nuevo.nombre}» creado. {_cuantos(len(creados))}", "bien")

    def _rellenar_el_pasado(self, periodico: Periodico, pasados: list[str]) -> bool:
        cuantos = len(pasados)
        return dialogos.confirmar(
            self.app,
            f"¿Apunto también los {cuantos} pagos que ya han pasado?",
            f"El primer pago que has puesto fue el "
            f"{formato.fecha_corta(pasados[0])}, así que desde entonces han "
            f"vencido {cuantos}.\n\n"
            f"Sí: los apunta todos ahora, útil para rellenar el histórico.\n"
            f"No: empieza a contar desde hoy y no toca el pasado.")

    def editar(self, periodico: Periodico) -> None:
        datos = self._pedir_datos(f"Editar «{periodico.nombre}»", periodico,
                                  "Guardar cambios")
        if datos is None:
            return

        creados: list = []

        def aplicar(libro_actual):
            objetivo = libro_actual.periodico(periodico.id)
            if objetivo is None:
                raise ValueError("Ese pago periódico ya no existe.")
            objetivo.nombre = datos["nombre"]
            objetivo.categoria = datos["categoria"]
            objetivo.importe = abs(datos["importe"])
            objetivo.periodo = datos["periodo"]
            objetivo.desde = datos["desde"]
            objetivo.hasta = datos["hasta"]
            objetivo.activo = datos["activo"]
            creados.extend(calculos.apuntar_pendientes(libro_actual, hoy()))

        if self.app.cambiar(aplicar):
            self.app.estado(f"«{datos['nombre']}» actualizado. {_cuantos(len(creados))}",
                            "bien")

    def alternar(self, periodico: Periodico) -> None:
        encender = not periodico.encendido
        creados: list = []

        def aplicar(libro_actual):
            objetivo = libro_actual.periodico(periodico.id)
            if objetivo is None:
                raise ValueError("Ese pago periódico ya no existe.")
            objetivo.encendido = encender
            if not encender:
                return
            # Los pagos de mientras estuvo apagado no se pagaron, así que no
            # se apuntan al volver: solo cuenta desde hoy.
            calculos.saltar_lo_pasado(objetivo, hoy())
            creados.extend(calculos.apuntar_pendientes(libro_actual, hoy()))

        if self.app.cambiar(aplicar):
            if encender:
                self.app.estado(f"«{periodico.nombre}» encendido. {_cuantos(len(creados))}",
                                "bien")
            else:
                self.app.estado(f"«{periodico.nombre}» apagado. Deja de apuntarse, "
                                "pero lo ya apuntado se queda.")

    def borrar(self, periodico: Periodico) -> None:
        apuntados = calculos.apuntados_por(self.app.libro, periodico)
        detalle = (f"{periodico.nombre} · {formato.euros(periodico.importe, True)} · "
                   f"{periodico.periodo.lower()}\n\n")
        if apuntados:
            detalle += (f"Los {apuntados} movimientos que ya apuntó se quedan en el "
                        "libro: se pagaron de verdad. Lo que se borra es la regla, "
                        "así que no se apuntará ninguno más.\n\n"
                        "Si solo quieres que pare, es mejor apagarlo.")
        else:
            detalle += "Todavía no ha apuntado ningún movimiento."

        if not dialogos.confirmar(self.app, "¿Borrar este pago periódico?", detalle):
            return

        def aplicar(libro_actual):
            objetivo = libro_actual.periodico(periodico.id)
            if objetivo is None:
                raise ValueError("Ese pago periódico ya no existe.")
            libro_actual.periodicos.remove(objetivo)

        self.app.cambiar(aplicar, f"«{periodico.nombre}» borrado.")

    # --- explicaciones ----------------------------------------------------

    def _explicar_gasto(self) -> None:
        """De dónde sale el gasto fijo al mes.

        Es una cifra que no coincide con ningún recibo, porque mete en la
        misma escala cosas que se pagan cada semana y cosas que se pagan una
        vez al año. Sin verlo desglosado no hay manera de reconocerla.
        """
        libro = self.app.libro
        resumen = calculos.resumen_periodicos(libro)
        gastos = [p for p in libro.periodicos
                  if calculos.esta_vigente(p) and libro.tipo_de(p.categoria) == GASTO]

        cuenta = [(f"{p.nombre} · {p.periodo.lower()}",
                   formato.euros(calculos.coste_mensual(p)))
                  for p in sorted(gastos, key=lambda p: -calculos.coste_mensual(p))]
        if cuenta:
            cuenta.append((None, None))
            cuenta.append(("Gasto fijo al mes", formato.euros(resumen.gasto)))

        detalle = (
            "Lo que no es mensual se reparte para poder sumarlo: un seguro de "
            "310 € al año cuenta como 25,83 € al mes. Es solo para comparar; "
            "en el libro se apunta el día que toca y por su importe entero.\n\n"
            "No entra lo apagado, ni lo que ya llegó a su último pago, ni la "
            "inversión: la inversión sale del banco, pero el dinero sigue "
            "siendo tuyo y por eso va en su propia casilla."
        )

        dialogos.Explicacion(
            self.app, "Gasto fijo al mes",
            "Lo que se te va todos los meses en cosas que se pagan solas, "
            "puestas todas en la misma escala."
            if cuenta else
            "Aquí saldrá lo que se te va cada mes en cuanto tengas algún gasto "
            "periódico encendido.",
            cuenta=cuenta, detalle=detalle).mostrar()

    # --- refresco ---------------------------------------------------------

    def refrescar(self) -> None:
        libro = self.app.libro
        resumen = calculos.resumen_periodicos(libro)

        self.cifras.poner("gasto", "Gasto fijo al mes", formato.euros(resumen.gasto),
                          "", "de lo que está encendido",
                          ayuda=self._explicar_gasto)
        self.cifras.poner("inversion", "Inversión al mes",
                          formato.euros(resumen.inversion), "",
                          "aportado a la cartera")
        self.cifras.poner("ingreso", "Ingreso fijo al mes",
                          formato.euros(resumen.ingreso), "", "nóminas y demás")
        self.cifras.poner("cuantos", "En marcha", str(resumen.encendidos), "Suave",
                          _parados(resumen))

        # Lo que sigue en marcha primero y por fecha del próximo pago: lo que
        # viene antes, arriba. Lo parado al final, que es lo que menos importa.
        def orden(periodico):
            vigente = calculos.esta_vigente(periodico)
            proximo = calculos.proximo_vencimiento(periodico) if vigente else ""
            return (not vigente, proximo or "9999-99-99", periodico.nombre)

        filas = []
        for periodico in sorted(libro.periodicos, key=orden):
            vigente = calculos.esta_vigente(periodico)
            proximo = calculos.proximo_vencimiento(periodico) if vigente else ""
            tipo = libro.tipo_de(periodico.categoria)
            filas.append((periodico.id, (
                periodico.nombre,
                periodico.categoria,
                comun.importe_con_signo(tipo, periodico.importe),
                periodico.periodo,
                formato.fecha_corta(proximo) if proximo else "—",
                "En marcha" if vigente else
                ("Terminado" if periodico.encendido else "Apagado"),
            ), ("suave" if not vigente else comun.etiqueta_por_tipo(tipo),)))

        self.tabla.poner(filas)
        self.tarjeta.titulo("1 periódico" if len(filas) == 1
                            else f"{len(filas)} periódicos")
        self._pintar_vacio(len(filas))
        self._pintar_boton()

    def _pintar_boton(self) -> None:
        periodico = self.app.libro.periodico(self.tabla.seleccion() or "")
        self.boton_encendido.configure(
            text="Encender" if periodico is not None and not periodico.encendido
            else "Apagar")

    def _pintar_vacio(self, cuantos: int) -> None:
        if cuantos > 0:
            self.vacio.pack_forget()
            if not self.tabla.winfo_ismapped():
                self.tabla.pack(fill="both", expand=True)
            return

        self.tabla.pack_forget()
        self.vacio.configure(text=(
            "Todavía no hay ningún pago periódico.\n\n"
            "Pulsa «Nuevo» y apunta lo que se repite solo cada mes: el "
            "alquiler, el wifi, el gimnasio,\nlas suscripciones o lo que "
            "aportas a la cartera."))
        if not self.vacio.winfo_ismapped():
            self.vacio.pack(pady=40)

    def al_entrar(self) -> None:
        self._pintar_boton()


def _parados(resumen) -> str:
    """La coletilla de la casilla: qué hay parado y por qué está parado.

    Apagado y terminado no son lo mismo: el apagado puede volver, el
    terminado ya cumplió su fecha de fin.
    """
    piezas = []
    if resumen.apagados:
        piezas.append(f"{resumen.apagados} apagado" if resumen.apagados == 1
                      else f"{resumen.apagados} apagados")
    if resumen.terminados:
        piezas.append(f"{resumen.terminados} terminado" if resumen.terminados == 1
                      else f"{resumen.terminados} terminados")
    return " · ".join(piezas) if piezas else "ninguno parado"


def _cuantos(creados: int) -> str:
    """La coletilla que dice cuántos movimientos se acaban de apuntar."""
    if creados == 0:
        return "No había ningún pago vencido."
    if creados == 1:
        return "Se ha apuntado 1 pago."
    return f"Se han apuntado {creados} pagos."
