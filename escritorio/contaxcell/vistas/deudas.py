"""Las cuentas con la gente: lo que te deben y lo que debes.

Es una libreta, no una cuenta corriente. Que Fulanito te deba veinte euros
no es dinero que tengas, y por eso nada de esto toca el saldo del banco: el
saldo lo mueven los movimientos, y aquí solo se anota quién queda a deber.

Cuando el dinero cambia de manos de verdad se pulsa «Cobrar» o «Pagar», y ahí
sí se ofrece apuntar el movimiento. Se ofrece y no se hace solo, porque a
veces ya está apuntado: si pagaste tú la cena entera, el gasto de la cena ya
salió de tu cuenta y lo que te devuelven solo lo compensa.

Cada deuda lleva una nota de varias líneas para lo que no cabe en las
casillas: de qué era, quién más estaba, qué se acordó.
"""

from __future__ import annotations

from tkinter import ttk

from .. import calculos, dialogos, formato, widgets
from ..modelo import DEBO, ME_DEBEN, SENTIDOS, Deuda, Movimiento, hoy
from . import comun


class VistaDeudas:
    def __init__(self, padre, app):
        self.app = app

        raiz = ttk.Frame(padre, padding=18)
        raiz.pack(fill="both", expand=True)

        self._cabecera(raiz)
        self._tabla(raiz)

    # --- montaje ----------------------------------------------------------

    def _cabecera(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "Cuentas con la gente")
        tarjeta.pack(fill="x")

        self.cifras = widgets.PanelCifras(tarjeta.cuerpo, columnas=4)
        self.cifras.pack(fill="x")

    def _tabla(self, padre) -> None:
        self.tarjeta = widgets.Tarjeta(padre, "Deudas")
        self.tarjeta.pack(fill="both", expand=True, pady=(16, 0))

        # Anclados al fondo antes que la tabla, para que no los desplace.
        acciones = ttk.Frame(self.tarjeta.cuerpo, style="Tarjeta.TFrame")
        acciones.pack(side="bottom", fill="x", pady=(10, 0))

        self.tabla = widgets.Tabla(self.tarjeta.cuerpo, [
            widgets.Columna("quien", "Quién", 150),
            widgets.Columna("concepto", "De qué", 200, estira=True),
            widgets.Columna("fecha", "Desde", 100),
            widgets.Columna("importe", "Importe", 110, anclaje="e"),
            widgets.Columna("pendiente", "Pendiente", 110, anclaje="e"),
            widgets.Columna("nota", "Nota", 170),
            widgets.Columna("estado", "Estado", 100),
        ], alto=12, al_activar=self._editar_seleccionado,
           al_elegir=self._pintar_boton)
        self.tabla.pack(fill="both", expand=True)

        self.vacio = ttk.Label(self.tarjeta.cuerpo, style="Tarjeta.Suave.TLabel",
                               justify="center", text="")

        ttk.Button(acciones, text="Nueva", style="Principal.TButton",
                   command=self.nueva).pack(side="left")
        ttk.Button(acciones, text="Editar",
                   command=self._editar_seleccionado).pack(side="left", padx=(8, 0))
        ttk.Button(acciones, text="Nota…",
                   command=self._nota_seleccionada).pack(side="left", padx=(8, 0))
        self.boton_saldar = ttk.Button(acciones, text="Cobrar…",
                                       command=self._saldar_seleccionada)
        self.boton_saldar.pack(side="left", padx=(8, 0))
        ttk.Button(acciones, text="Borrar", style="Peligro.TButton",
                   command=self._borrar_seleccionada).pack(side="left", padx=(8, 0))

        ttk.Label(self.tarjeta.derecha, text="Doble clic sobre una fila para editarla",
                  style="Tarjeta.Suave.TLabel").pack(side="right")

    # --- selección --------------------------------------------------------

    def _seleccionada(self) -> Deuda | None:
        clave = self.tabla.seleccion()
        if clave is None:
            self.app.estado("Elige antes una de la lista.", "malo")
            return None
        return self.app.libro.deuda(clave)

    def _editar_seleccionado(self, _clave=None) -> None:
        deuda = self._seleccionada()
        if deuda:
            self.editar(deuda)

    def _nota_seleccionada(self) -> None:
        deuda = self._seleccionada()
        if deuda:
            self.escribir_nota(deuda)

    def _saldar_seleccionada(self) -> None:
        deuda = self._seleccionada()
        if deuda:
            self.saldar(deuda)

    def _borrar_seleccionada(self) -> None:
        deuda = self._seleccionada()
        if deuda:
            self.borrar(deuda)

    # --- formulario -------------------------------------------------------

    def _campos(self, deuda: Deuda | None) -> list:
        base = deuda or Deuda(quien="", fecha=hoy())
        return [
            dialogos.Opcion("sentido", "¿De quién es el dinero?", list(SENTIDOS),
                            base.sentido,
                            ayuda="«Me deben» si el dinero te tiene que llegar; "
                                  "«Debo» si eres tú quien tiene que pagar."),
            dialogos.Texto("quien", "Quién", base.quien, pista="Fulanito",
                           obligatorio=True,
                           ayuda="El nombre agrupa: todo lo de la misma persona "
                                 "se suma en una sola cuenta."),
            dialogos.Texto("concepto", "De qué", base.concepto,
                           pista="La cena del sábado"),
            dialogos.Importe("importe", "Importe", base.importe or None,
                             permitir_cero=False),
            dialogos.Fecha("fecha", "Desde", base.fecha or hoy()),
            dialogos.Parrafo("nota", "Nota", base.nota,
                             ayuda="Para lo que no cabe arriba: quién más estaba, "
                                   "qué se acordó, cómo lo va a devolver."),
        ]

    def nueva(self) -> None:
        datos = dialogos.Formulario(self.app, "Nueva deuda", self._campos(None),
                                    aceptar="Crear").mostrar()
        if datos is None:
            return

        nueva = Deuda(quien=datos["quien"], sentido=datos["sentido"],
                      importe=abs(datos["importe"]), fecha=datos["fecha"],
                      concepto=datos["concepto"], nota=datos["nota"])

        self.app.cambiar(lambda libro: libro.deudas.append(nueva),
                         f"{_frase(nueva)}.")

    def editar(self, deuda: Deuda) -> None:
        datos = dialogos.Formulario(self.app, f"Editar la deuda de «{deuda.quien}»",
                                    self._campos(deuda),
                                    aceptar="Guardar cambios").mostrar()
        if datos is None:
            return

        def aplicar(libro):
            objetivo = libro.deuda(deuda.id)
            if objetivo is None:
                raise ValueError("Esa deuda ya no existe.")
            objetivo.quien = datos["quien"]
            objetivo.sentido = datos["sentido"]
            objetivo.importe = abs(datos["importe"])
            objetivo.fecha = datos["fecha"]
            objetivo.concepto = datos["concepto"]
            objetivo.nota = datos["nota"]
            # Si se baja el importe por debajo de lo ya devuelto, lo devuelto
            # sobrante no existe: la deuda queda saldada y en paz.
            objetivo.devuelto = min(objetivo.devuelto, objetivo.importe)

        self.app.cambiar(aplicar, "Deuda actualizada.")

    def escribir_nota(self, deuda: Deuda) -> None:
        """Solo la nota, sin pasar por el formulario entero.

        Es lo que se usa a diario: apuntar que ha dicho que paga el viernes.
        """
        datos = dialogos.Formulario(
            self.app, f"Nota · {deuda.quien}",
            [dialogos.Nota(_frase(deuda) + "."),
             dialogos.Parrafo("nota", "Nota", deuda.nota, lineas=8)],
            aceptar="Guardar").mostrar()
        if datos is None:
            return

        def aplicar(libro):
            objetivo = libro.deuda(deuda.id)
            if objetivo is None:
                raise ValueError("Esa deuda ya no existe.")
            objetivo.nota = datos["nota"]

        self.app.cambiar(aplicar, "Nota guardada.")

    # --- cobrar y pagar ---------------------------------------------------

    def saldar(self, deuda: Deuda) -> None:
        """Anota que el dinero ha cambiado de manos, entero o a trozos."""
        if calculos.esta_saldada(deuda):
            self.app.estado("Esa deuda ya está saldada.", "malo")
            return

        libro = self.app.libro
        cobra = deuda.sentido == ME_DEBEN
        queda = calculos.pendiente_de(deuda)
        titulo = (f"Cobrar de «{deuda.quien}»" if cobra
                  else f"Pagar a «{deuda.quien}»")
        categorias = comun.categorias_para(libro, "ingreso" if cobra else "gasto")

        campos = [
            dialogos.Nota(f"Quedan {formato.euros(queda)} por "
                          f"{'cobrar' if cobra else 'pagar'}. Si te "
                          f"{'devuelven' if cobra else 'pagas'} solo una parte, "
                          "escribe esa parte y el resto sigue apuntado."),
            dialogos.Importe("importe", "Cuánto", queda, permitir_cero=False),
            dialogos.Fecha("fecha", "Cuándo", hoy()),
            dialogos.Casilla(
                "apuntar", "Apuntar también el movimiento", False,
                ayuda="Márcalo solo si este dinero entra o sale de tu cuenta "
                      "ahora y no lo vas a apuntar a mano. Si el gasto ya lo "
                      "apuntaste en su día, déjalo sin marcar: si no, contaría "
                      "dos veces."),
            dialogos.Opcion("categoria", "Categoría", categorias,
                            categorias[0] if categorias else ""),
        ]

        def al_cambiar(formulario, _evento):
            formulario.mostrar_campo("categoria", bool(formulario.valor("apuntar")))

        def validar(datos):
            if datos["importe"] > queda:
                return (f"No puedes {'cobrar' if cobra else 'pagar'} más de lo "
                        f"que queda: {formato.euros(queda)}.")
            if datos["apuntar"] and not datos["categoria"]:
                return "Elige una categoría para el movimiento."
            return ""

        datos = dialogos.Formulario(self.app, titulo, campos,
                                    aceptar="Cobrar" if cobra else "Pagar",
                                    al_cambiar=al_cambiar, validar=validar).mostrar()
        if datos is None:
            return

        movimiento = None
        if datos["apuntar"]:
            movimiento = Movimiento(
                fecha=datos["fecha"],
                descripcion=(f"{deuda.quien} · {deuda.concepto}"
                             if deuda.concepto else deuda.quien),
                categoria=datos["categoria"],
                importe=abs(datos["importe"]),
                origen=deuda.id,
            )

        def aplicar(libro_actual):
            objetivo = libro_actual.deuda(deuda.id)
            if objetivo is None:
                raise ValueError("Esa deuda ya no existe.")
            calculos.anotar_pago(objetivo, datos["importe"])
            if movimiento is not None:
                libro_actual.movimientos.append(movimiento)

        if not self.app.cambiar(aplicar):
            return

        despues = self.app.libro.deuda(deuda.id)
        resto = calculos.pendiente_de(despues) if despues else 0.0
        aviso = (f"{formato.euros(datos['importe'])} "
                 f"{'cobrados de' if cobra else 'pagados a'} {deuda.quien}. ")
        aviso += ("Saldada." if resto <= 0
                  else f"Quedan {formato.euros(resto)}.")
        if movimiento is not None:
            aviso += " Movimiento apuntado."
        self.app.estado(aviso, "bien")

    def borrar(self, deuda: Deuda) -> None:
        detalle = _frase(deuda) + ".\n\n"
        if deuda.devuelto > 0:
            detalle += (f"Ya se han {'cobrado' if deuda.sentido == ME_DEBEN else 'pagado'} "
                        f"{formato.euros(deuda.devuelto)} de esta deuda.\n\n")
        detalle += ("Los movimientos que hayas apuntado al cobrarla o pagarla se "
                    "quedan en el libro: ese dinero se movió de verdad.")

        if not dialogos.confirmar(self.app, "¿Borrar esta deuda?", detalle):
            return

        def aplicar(libro):
            objetivo = libro.deuda(deuda.id)
            if objetivo is None:
                raise ValueError("Esa deuda ya no existe.")
            libro.deudas.remove(objetivo)

        self.app.cambiar(aplicar, "Deuda borrada.")

    # --- explicaciones ----------------------------------------------------

    def _explicar_personas(self) -> None:
        """La cuenta con cada persona, que es como se salda de verdad.

        Si le debes veinte a Fulanito y él te debe cincuenta, no hay dos
        pagos: hay uno de treinta. Eso no se ve en la lista, donde cada deuda
        va por su lado, y es justo lo que hay que saber antes de quedar.
        """
        saldos = calculos.deudas_por_persona(self.app.libro)

        cuenta = []
        for saldo in saldos:
            detalle = f"{saldo.quien} · {saldo.cuantas} "
            detalle += "cosa" if saldo.cuantas == 1 else "cosas"
            cuenta.append((detalle, formato.euros_con_signo(saldo.neto)))

        dialogos.Explicacion(
            self.app, "Cuenta con cada persona",
            "En positivo, lo que esa persona te tiene que dar; en negativo, lo "
            "que le tienes que dar tú. Cada línea ya junta todo lo que tenéis "
            "abierto en los dos sentidos."
            if cuenta else
            "Aquí saldrá la cuenta con cada persona en cuanto haya alguna "
            "deuda sin saldar.",
            cuenta=cuenta,
            detalle="Solo entra lo que queda pendiente: lo saldado ya no cuenta, "
                    "y de lo devuelto a trozos solo la parte que falta.").mostrar()

    # --- refresco ---------------------------------------------------------

    def refrescar(self) -> None:
        libro = self.app.libro
        resumen = calculos.resumen_deudas(libro)

        self.cifras.poner("deben", "Te deben", formato.euros(resumen.te_deben),
                          "Ingreso", _personas(resumen.personas),
                          ayuda=self._explicar_personas)
        self.cifras.poner("debes", "Debes", formato.euros(resumen.debes), "Gasto",
                          "de lo que sigue abierto")
        self.cifras.poner("neto", "Neto", formato.euros_con_signo(resumen.neto),
                          _color(resumen.neto),
                          "a tu favor" if resumen.neto > 0 else
                          ("en tu contra" if resumen.neto < 0 else "en paz"))
        self.cifras.poner("abiertas", "Sin saldar", str(resumen.abiertas), "Suave",
                          f"{resumen.saldadas} saldadas" if resumen.saldadas
                          else "ninguna saldada")

        # Lo abierto primero, y dentro por persona: las cosas de Fulanito
        # juntas. Lo saldado al final, que es lo que menos importa.
        def orden(deuda):
            return (calculos.esta_saldada(deuda), deuda.quien.lower(), deuda.fecha)

        # Aquí sí se pintan de rojo las de «Debo», al revés que los gastos del
        # libro. Allí van sin color porque son casi todas las filas y pintarlas
        # no distingue nada; aquí son la mitad, y de un vistazo tiene que verse
        # de qué lado está cada una.
        filas = []
        for deuda in sorted(libro.deudas, key=orden):
            saldada = calculos.esta_saldada(deuda)
            pendiente = calculos.pendiente_de(deuda)
            filas.append((deuda.id, (
                deuda.quien,
                deuda.concepto or "—",
                formato.fecha_corta(deuda.fecha),
                formato.euros(deuda.importe),
                "—" if saldada else formato.euros(pendiente),
                _primera_linea(deuda.nota),
                "Saldada" if saldada else deuda.sentido,
            ), ("suave" if saldada else
                ("ingreso" if deuda.sentido == ME_DEBEN else "gasto"),)))

        self.tabla.poner(filas)
        self.tarjeta.titulo("1 deuda" if len(filas) == 1 else f"{len(filas)} deudas")
        self._pintar_vacio(len(filas))
        self._pintar_boton()

    def _pintar_boton(self) -> None:
        """El botón dice lo que se va a hacer: no es lo mismo cobrar que pagar."""
        deuda = self.app.libro.deuda(self.tabla.seleccion() or "")
        self.boton_saldar.configure(
            text="Pagar…" if deuda is not None and deuda.sentido == DEBO
            else "Cobrar…")

    def _pintar_vacio(self, cuantas: int) -> None:
        if cuantas > 0:
            self.vacio.pack_forget()
            if not self.tabla.winfo_ismapped():
                self.tabla.pack(fill="both", expand=True)
            return

        self.tabla.pack_forget()
        self.vacio.configure(text=(
            "Todavía no hay ninguna deuda apuntada.\n\n"
            "Pulsa «Nueva» y apunta lo que te deben o lo que debes: la cena que "
            "pagaste tú,\nel dinero que te prestaron, lo que quedasteis a "
            "medias."))
        if not self.vacio.winfo_ismapped():
            self.vacio.pack(pady=40)

    def al_entrar(self) -> None:
        self._pintar_boton()


def _frase(deuda: Deuda) -> str:
    """«Fulanito te debe 20,00 €», para los avisos y las confirmaciones."""
    verbo = "te debe" if deuda.sentido == ME_DEBEN else "quiere cobrarte"
    frase = f"{deuda.quien} {verbo} {formato.euros(deuda.importe, True)}"
    if deuda.concepto:
        frase += f" · {deuda.concepto}"
    return frase


def _primera_linea(nota: str) -> str:
    """Lo que cabe de la nota en una celda de la tabla.

    Solo la primera línea y cortada: la tabla es para reconocerla de un
    vistazo, la nota entera se lee en «Nota…».
    """
    if not nota.strip():
        return ""
    primera = nota.strip().splitlines()[0].strip()
    return primera if len(primera) <= 30 else primera[:29] + "…"


def _personas(cuantas: int) -> str:
    if cuantas == 0:
        return "no hay nada abierto"
    return "de 1 persona" if cuantas == 1 else f"de {cuantas} personas"


def _color(valor: float) -> str:
    if valor > 0:
        return "Ingreso"
    if valor < 0:
        return "Gasto"
    return "Suave"
