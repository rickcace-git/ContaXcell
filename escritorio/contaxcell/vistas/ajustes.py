"""Lo que se toca una vez y ya: el punto de partida del banco, las categorías,
el aspecto y el trasiego de archivos.
"""

from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

from .. import calculos, dialogos, excel, formato, widgets
from ..modelo import GASTO, INGRESO, INVERSION, Categoria
from ..sincronia import ErrorDeSincronia


class VistaAjustes:
    def __init__(self, padre, app):
        self.app = app

        self.desplazable = widgets.MarcoDesplazable(padre)
        self.desplazable.pack(fill="both", expand=True)
        raiz = ttk.Frame(self.desplazable.interior, padding=18)
        raiz.pack(fill="both", expand=True)

        self._banco(raiz)
        self._categorias(raiz)
        self._abajo(raiz)
        if app.sincronia is not None:
            self._cuenta(raiz)

    # --- el banco ---------------------------------------------------------

    def _banco(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "El banco")
        tarjeta.pack(fill="x")

        bloque = ttk.Frame(tarjeta.cuerpo, style="Tarjeta.TFrame")
        bloque.pack(anchor="w")
        ttk.Label(bloque, style="Tarjeta.Suave.TLabel",
                  text="Saldo inicial: lo que tenías en la cuenta antes del primer "
                       "movimiento").pack(anchor="w")
        self.var_saldo = tk.StringVar()
        self.campo_saldo = ttk.Entry(bloque, textvariable=self.var_saldo, width=16)
        self.campo_saldo.pack(anchor="w", pady=(3, 0))
        self.campo_saldo.bind("<FocusOut>", lambda _e: self._guardar_saldo())
        self.campo_saldo.bind("<Return>", lambda _e: self._guardar_saldo())

        self.cifras = widgets.PanelCifras(tarjeta.cuerpo, columnas=4)
        self.cifras.pack(fill="x", pady=(14, 0))

        ttk.Label(tarjeta.cuerpo, style="Tarjeta.Suave.TLabel", justify="left",
                  wraplength=820,
                  text="El saldo de hoy es el inicial más todo lo ingresado menos todo lo "
                       "que ha salido. Si no cuadra con tu banco, casi siempre es que "
                       "falta algún movimiento por apuntar.").pack(anchor="w", pady=(4, 0))

    def _guardar_saldo(self) -> None:
        valor = formato.texto_a_numero(self.var_saldo.get())
        if valor is None:
            self.app.estado(f"«{self.var_saldo.get()}» no es un número.", "malo")
            self.refrescar()
            return
        if self.app.libro.ajustes.saldo_inicial == valor:
            return
        self.app.cambiar(lambda libro: setattr(libro.ajustes, "saldo_inicial", valor),
                         "Saldo inicial actualizado.")

    # --- categorías -------------------------------------------------------

    def _categorias(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "Categorías")
        tarjeta.pack(fill="x", pady=(16, 0))
        ttk.Button(tarjeta.derecha, text="Añadir categoría",
                   command=self.anadir_categoria).pack(side="right")

        self.tabla = widgets.Tabla(tarjeta.cuerpo, [
            widgets.Columna("nombre", "Categoría", 240, estira=True),
            widgets.Columna("tipo", "Tipo", 130),
            widgets.Columna("presupuesto", "Presupuesto/mes", 150, anclaje="e"),
            widgets.Columna("usos", "Movimientos", 120, anclaje="e"),
        ], alto=9, al_activar=lambda _c: self.editar_categoria())
        self.tabla.pack(fill="x")

        acciones = ttk.Frame(tarjeta.cuerpo, style="Tarjeta.TFrame")
        acciones.pack(fill="x", pady=(10, 0))
        ttk.Button(acciones, text="Editar", command=self.editar_categoria).pack(side="left")
        ttk.Button(acciones, text="Subir",
                   command=lambda: self._mover(-1)).pack(side="left", padx=(8, 0))
        ttk.Button(acciones, text="Bajar",
                   command=lambda: self._mover(1)).pack(side="left", padx=(8, 0))
        ttk.Button(acciones, text="Borrar", style="Peligro.TButton",
                   command=self.borrar_categoria).pack(side="left", padx=(8, 0))

        ttk.Label(tarjeta.cuerpo, style="Tarjeta.Suave.TLabel", justify="left",
                  wraplength=820,
                  text="El tipo manda: cambiarlo recalcula todo el histórico de esa "
                       "categoría. «Inversión» sale del banco como un gasto, pero no "
                       "cuenta como gasto al calcular el ahorro. Si renombras una "
                       "categoría, sus movimientos la siguen.").pack(anchor="w", pady=(10, 0))

    def _categoria_seleccionada(self) -> Categoria | None:
        clave = self.tabla.seleccion()
        if clave is None:
            self.app.estado("Elige antes una categoría de la lista.", "malo")
            return None
        return self.app.libro.categoria(clave)

    def _campos_categoria(self, categoria: Categoria | None):
        return [
            dialogos.Texto("nombre", "Nombre", categoria.nombre if categoria else "",
                           pista="Suscripciones", obligatorio=True),
            dialogos.Opcion("tipo", "Tipo", [INGRESO, GASTO, INVERSION],
                            categoria.tipo if categoria else GASTO),
            dialogos.Importe("presupuesto", "Presupuesto al mes",
                             categoria.presupuesto if categoria else 0,
                             ayuda="Solo se usa en las categorías de gasto. Déjalo en "
                                   "cero si esa categoría no tiene tope."),
        ]

    def _validar_categoria(self, valores, excepto: str = "") -> str | None:
        nombre = valores["nombre"]
        for categoria in self.app.libro.categorias:
            if categoria.nombre == nombre and nombre != excepto:
                return "Ya existe una categoría con ese nombre."
        return None

    def anadir_categoria(self) -> None:
        resultado = dialogos.Formulario(
            self.app, "Nueva categoría", self._campos_categoria(None),
            aceptar="Crear", validar=self._validar_categoria).mostrar()
        if resultado is None:
            return

        nueva = Categoria(
            nombre=resultado["nombre"], tipo=resultado["tipo"],
            presupuesto=resultado["presupuesto"] if resultado["tipo"] == GASTO else 0.0)
        self.app.cambiar(lambda libro: libro.categorias.append(nueva),
                         f"Categoría «{nueva.nombre}» creada.")

    def editar_categoria(self) -> None:
        categoria = self._categoria_seleccionada()
        if categoria is None:
            return
        anterior = categoria.nombre

        resultado = dialogos.Formulario(
            self.app, f"Editar «{anterior}»", self._campos_categoria(categoria),
            validar=lambda v: self._validar_categoria(v, excepto=anterior)).mostrar()
        if resultado is None:
            return

        def aplicar(libro):
            objetivo = libro.categoria(anterior)
            if objetivo is None:
                raise ValueError("Esa categoría ya no existe.")
            nuevo_nombre = resultado["nombre"]
            if nuevo_nombre != anterior:
                # Los movimientos guardan el nombre, así que renombrar tiene
                # que arrastrarlos o se quedarían apuntando a la nada.
                for movimiento in libro.movimientos:
                    if movimiento.categoria == anterior:
                        movimiento.categoria = nuevo_nombre
            objetivo.nombre = nuevo_nombre
            objetivo.tipo = resultado["tipo"]
            objetivo.presupuesto = (resultado["presupuesto"]
                                    if resultado["tipo"] == GASTO else 0.0)

        self.app.cambiar(aplicar, "Categoría actualizada.")

    def _mover(self, direccion: int) -> None:
        categoria = self._categoria_seleccionada()
        if categoria is None:
            return
        nombre = categoria.nombre

        def aplicar(libro):
            posicion = next(i for i, c in enumerate(libro.categorias) if c.nombre == nombre)
            destino = posicion + direccion
            if not 0 <= destino < len(libro.categorias):
                return
            libro.categorias.insert(destino, libro.categorias.pop(posicion))

        if self.app.cambiar(aplicar):
            self.tabla.arbol.selection_set(nombre)

    def borrar_categoria(self) -> None:
        categoria = self._categoria_seleccionada()
        if categoria is None:
            return
        nombre = categoria.nombre
        usos = sum(1 for m in self.app.libro.movimientos if m.categoria == nombre)

        if usos:
            # Borrarla dejaría esos movimientos apuntando a una categoría que
            # ya no existe, y pasarían a contar como gasto suelto.
            if not dialogos.confirmar(
                    self.app, f"«{nombre}» tiene {usos} movimientos.",
                    "Si la borras, esos movimientos se quedan con el nombre de una "
                    "categoría que ya no existe y pasarán a contar como gasto suelto.\n\n"
                    "Si lo que quieres es juntarla con otra, cámbiale el nombre en vez "
                    "de borrarla."):
                return
        elif not dialogos.confirmar(self.app, f"¿Borrar la categoría «{nombre}»?",
                                    "No tiene ningún movimiento."):
            return

        def aplicar(libro):
            objetivo = libro.categoria(nombre)
            if objetivo is not None:
                libro.categorias.remove(objetivo)

        self.app.cambiar(aplicar, f"Categoría «{nombre}» borrada.")

    # --- aspecto y datos --------------------------------------------------

    def _abajo(self, padre) -> None:
        fila = ttk.Frame(padre)
        fila.pack(fill="x", pady=(16, 0))
        fila.columnconfigure(0, weight=1, uniform="abajo")
        fila.columnconfigure(1, weight=1, uniform="abajo")

        self._aspecto(fila)
        self._datos(fila)

    def _aspecto(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "Aspecto")
        tarjeta.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        botones = ttk.Frame(tarjeta.cuerpo, style="Tarjeta.TFrame")
        botones.pack(anchor="w")
        self.botones_tema = {}
        for valor, texto in (("auto", "Como el sistema"), ("claro", "Claro"),
                             ("oscuro", "Oscuro")):
            boton = ttk.Button(botones, text=texto,
                               command=lambda v=valor: self.app.poner_tema(v))
            boton.pack(side="left", padx=(0, 8))
            self.botones_tema[valor] = boton

        ttk.Label(tarjeta.cuerpo, style="Tarjeta.Suave.TLabel", justify="left",
                  wraplength=380,
                  text="El botón del ojo de la barra de arriba tapa de golpe todos los "
                       "importes de la aplicación, por si apuntas algo con gente "
                       "delante. Se recuerda al cerrar.").pack(anchor="w", pady=(12, 0))

    def _datos(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "Tus datos")
        tarjeta.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        primera = ttk.Frame(tarjeta.cuerpo, style="Tarjeta.TFrame")
        primera.pack(fill="x")
        ttk.Button(primera, text="Importar desde Excel…",
                   command=self.importar_excel).pack(side="left")
        ttk.Button(primera, text="Exportar a Excel…",
                   command=self.exportar_excel).pack(side="left", padx=(8, 0))

        segunda = ttk.Frame(tarjeta.cuerpo, style="Tarjeta.TFrame")
        segunda.pack(fill="x", pady=(8, 0))
        ttk.Button(segunda, text="Guardar copia",
                   command=self.guardar_copia).pack(side="left")
        ttk.Button(segunda, text="Restaurar copia…",
                   command=self.restaurar_copia).pack(side="left", padx=(8, 0))
        ttk.Button(segunda, text="Abrir la carpeta",
                   command=self.app.abrir_carpeta_datos).pack(side="left", padx=(8, 0))

        self.ruta = ttk.Label(tarjeta.cuerpo, style="Tarjeta.Suave.TLabel",
                              justify="left", wraplength=380,
                              text=str(self.app.almacen.carpeta))
        self.ruta.pack(anchor="w", pady=(12, 0))
        ttk.Label(tarjeta.cuerpo, style="Tarjeta.Suave.TLabel", justify="left",
                  wraplength=380,
                  text="Tus datos no salen de este ordenador. Cada vez que importas o "
                       "restauras se guarda antes una copia automática, y se conservan "
                       "las veinte últimas.").pack(anchor="w", pady=(4, 0))
        from ..ventana import VERSION
        ttk.Label(tarjeta.cuerpo, text=f"ContaXcell {VERSION}",
                  style="Tarjeta.Suave.TLabel").pack(anchor="w", pady=(8, 0))

    # --- la cuenta ---------------------------------------------------------

    def _cuenta(self, padre) -> None:
        tarjeta = widgets.Tarjeta(padre, "Tu cuenta")
        tarjeta.pack(fill="x", pady=(16, 0))

        self.etiqueta_cuenta = ttk.Label(tarjeta.cuerpo, style="Tarjeta.TLabel",
                                         justify="left", wraplength=820)
        self.etiqueta_cuenta.pack(anchor="w")
        self.etiqueta_sincronia = ttk.Label(tarjeta.cuerpo, style="Tarjeta.Suave.TLabel",
                                            justify="left", wraplength=820)
        self.etiqueta_sincronia.pack(anchor="w", pady=(4, 0))

        botones = ttk.Frame(tarjeta.cuerpo, style="Tarjeta.TFrame")
        botones.pack(fill="x", pady=(10, 0))
        self.boton_reentrar = ttk.Button(botones, text="Entrar de nuevo",
                                         command=self.entrar_de_nuevo)
        self.boton_contrasena = ttk.Button(botones, text="Cambiar la contraseña…",
                                           command=self.cambiar_contrasena)
        self.boton_contrasena.pack(side="left")
        ttk.Button(botones, text="Cerrar sesión", style="Peligro.TButton",
                   command=self.cerrar_sesion).pack(side="left", padx=(8, 0))

        ttk.Label(tarjeta.cuerpo, style="Tarjeta.Suave.TLabel", justify="left",
                  wraplength=820,
                  text="La contabilidad se guarda primero en este ordenador, como "
                       "siempre, y después se sube sola a tu cuenta cuando hay "
                       "conexión. Sin internet todo sigue funcionando igual; lo que "
                       "cambies se sube al volver.").pack(anchor="w", pady=(10, 0))

    def _refrescar_cuenta(self) -> None:
        sincronia = self.app.sincronia
        if sincronia is None or not hasattr(self, "etiqueta_cuenta"):
            return
        if sincronia.hay_sesion():
            self.etiqueta_cuenta.configure(
                text=f"Conectado como «{sincronia.sesion['usuario']}» "
                     f"en {sincronia.sesion['servidor']}")
        else:
            self.etiqueta_cuenta.configure(text="Sin cuenta en este ordenador.")
        self.etiqueta_sincronia.configure(text=sincronia.estado_actual())
        # Cambiar la contraseña necesita cuenta y servidor: sin sesión no hay
        # a quién pedírselo, así que el botón se queda apagado.
        self.boton_contrasena.configure(
            state="normal" if sincronia.hay_sesion() else "disabled")
        if sincronia.caducada:
            if not self.boton_reentrar.winfo_ismapped():
                self.boton_reentrar.pack(side="left", padx=(8, 0))
        elif self.boton_reentrar.winfo_ismapped():
            self.boton_reentrar.pack_forget()

    def entrar_de_nuevo(self) -> None:
        """El token caducó: se vuelve a pedir la cuenta sin cerrar nada. Lo
        pendiente sigue apuntado y se sube en cuanto se entra."""
        from .. import acceso
        resultado = acceso.pedir_cuenta(self.app.sincronia, padre=self.app)
        if resultado == acceso.DENTRO:
            self.app.estado("Ya estás dentro. Lo pendiente se sube ahora.", "bien")
        self._refrescar_cuenta()

    def cambiar_contrasena(self) -> None:
        """Abre el diálogo de la contraseña. El aviso de que los demás
        ordenadores tendrán que entrar de nuevo se da al terminar, porque es
        justo lo que sorprendería después."""
        sincronia = self.app.sincronia
        if sincronia is None or not sincronia.hay_sesion():
            self.app.estado("Antes hay que entrar con una cuenta.", "malo")
            return
        if VentanaContrasena(self.app, sincronia).mostrar():
            self.app.estado("Contraseña cambiada. Los demás ordenadores tendrán "
                            "que entrar de nuevo.", "bien")
        self._refrescar_cuenta()

    def cerrar_sesion(self) -> None:
        if not dialogos.confirmar(
                self.app, "¿Cerrar la sesión en este ordenador?",
                "Tus datos se quedan aquí y en el servidor tal como están. La "
                "aplicación se cerrará y al volver a abrirla pedirá una cuenta."):
            return
        self.app.cerrar_sesion()

    # --- archivos ---------------------------------------------------------

    def importar_excel(self) -> None:
        if not dialogos.confirmar(
                self.app, "¿Sustituir la contabilidad actual por la de un Excel?",
                "Se leen los movimientos, las categorías, el presupuesto y la cartera del "
                "archivo que elijas. Lo que tengas ahora en la aplicación se reemplaza por "
                "completo, pero antes se guarda una copia de seguridad automática."):
            return

        ruta = filedialog.askopenfilename(
            parent=self.app, title="Elige el Excel de tu contabilidad",
            filetypes=[("Libros de Excel", "*.xlsx"), ("Todos los archivos", "*.*")])
        if not ruta:
            return

        try:
            libro, avisos = excel.importar(ruta)
        except excel.ErrorDeImportacion as error:
            dialogos.error(self.app, "No se ha podido importar", str(error))
            return
        except Exception as error:  # noqa: BLE001
            dialogos.error(self.app, "No se ha podido importar",
                           f"El archivo ha dado este error:\n\n{error}")
            return

        self.app.reemplazar_libro(libro, "antes-de-importar",
                                  f"Importados {len(libro.movimientos)} movimientos.")
        if avisos:
            dialogos.avisar(self.app, "Importado, con algunos detalles",
                            "\n\n".join(avisos))

    def exportar_excel(self) -> None:
        anio = getattr(self.app.vistas.get("resumen"), "anio", None) or \
            calculos.anios_con_datos(self.app.libro)[0]
        ruta = filedialog.asksaveasfilename(
            parent=self.app, title="Guardar la contabilidad como Excel",
            defaultextension=".xlsx", initialfile=f"ContaXcell-{anio}.xlsx",
            filetypes=[("Libros de Excel", "*.xlsx")])
        if not ruta:
            return

        try:
            _, avisos = excel.exportar(ruta, self.app.libro, anio)
        except OSError as error:
            dialogos.error(self.app, "No se ha podido guardar el Excel",
                           f"{error}\n\n¿Lo tienes abierto en Excel ahora mismo?")
            return
        self.app.estado(f"Guardado en {ruta}", "bien")
        if avisos:
            dialogos.avisar(self.app, "Exportado, con algún detalle",
                            "\n\n".join(avisos))

    def guardar_copia(self) -> None:
        destino = self.app.almacen.copia_de_seguridad("manual")
        if destino is None:
            self.app.estado("Todavía no hay nada que copiar.", "malo")
            return
        self.app.estado(f"Copia guardada: {destino.name}", "bien")

    def restaurar_copia(self) -> None:
        copias = self.app.almacen.listar_copias()
        carpeta = self.app.almacen.ruta_copias if copias else self.app.almacen.carpeta
        ruta = filedialog.askopenfilename(
            parent=self.app, title="Elige la copia que quieres restaurar",
            initialdir=str(carpeta),
            filetypes=[("Copias de ContaXcell", "*.json"), ("Todos los archivos", "*.*")])
        if not ruta:
            return

        if not dialogos.confirmar(
                self.app, "¿Sustituir la contabilidad actual por esta copia?",
                f"{Path(ruta).name}\n\nAntes se guardará una copia de lo que tienes "
                "ahora, por si quieres volver atrás."):
            return

        try:
            self.app.almacen.restaurar(Path(ruta))
        except (OSError, ValueError) as error:
            dialogos.error(self.app, "No se ha podido restaurar",
                           f"El archivo no se ha podido leer:\n\n{error}")
            return

        self.app.libro = self.app.almacen.libro
        formato.ocultar_importes(self.app.libro.ajustes.ocultar_importes)
        self.app._apuntar_para_subir()
        self.app.ensuciar()
        self.app.refrescar()
        self.app.estado("Copia restaurada.", "bien")

    # --- refresco ---------------------------------------------------------

    def refrescar(self) -> None:
        libro = self.app.libro

        if self.app.focus_get() is not self.campo_saldo:
            self.var_saldo.set(formato.numero(libro.ajustes.saldo_inicial))

        self.cifras.poner("saldo", "Saldo del banco hoy",
                          formato.euros(calculos.saldo_banco(libro)))
        self.cifras.poner("movimientos", "Movimientos apuntados",
                          str(len(libro.movimientos)))
        self.cifras.poner("categorias", "Categorías", str(len(libro.categorias)))
        self.cifras.poner("activos", "Activos", str(len(libro.activos)))

        usos: dict[str, int] = {}
        for movimiento in libro.movimientos:
            usos[movimiento.categoria] = usos.get(movimiento.categoria, 0) + 1

        etiquetas = {INGRESO: "ingreso", INVERSION: "inversion", GASTO: ""}
        filas = [(c.nombre, (
            c.nombre,
            c.tipo,
            formato.euros(c.presupuesto) if c.tipo == GASTO and c.presupuesto else "—",
            str(usos.get(c.nombre, 0)),
        ), (etiquetas.get(c.tipo, ""),)) for c in libro.categorias]
        self.tabla.poner(filas)
        self.tabla.ajustar_alto(len(filas), minimo=5, maximo=16)

        for valor, boton in self.botones_tema.items():
            boton.configure(style="Principal.TButton" if valor == libro.ajustes.tema
                            else "TButton")

        self._refrescar_cuenta()

    def al_entrar(self) -> None:
        self.desplazable.arriba()


# --- cambiar la contraseña ------------------------------------------------------

LETRAS_MINIMAS = 8


class VentanaContrasena(tk.Toplevel):
    """Un formulario pequeño para cambiar la contraseña de la cuenta.

    Igual que la puerta de entrada: se habla con el servidor desde el hilo
    principal, que es cosa de un momento, y lo que salga mal se cuenta aquí
    dentro sin cerrar nada, para no obligar a escribirlo todo otra vez.

    `mostrar()` devuelve si la contraseña se llegó a cambiar.
    """

    def __init__(self, padre, sincronia):
        super().__init__(padre)
        self.sincronia = sincronia
        self.cambiada = False

        self.title("ContaXcell — Cambiar la contraseña")
        self.resizable(False, False)
        self.configure(background=widgets.PALETA.tarjeta)
        self.transient(padre)

        cuerpo = ttk.Frame(self, style="Tarjeta.TFrame", padding=18)
        cuerpo.pack(fill="both", expand=True)
        ttk.Label(cuerpo, text="Cambiar la contraseña",
                  style="Tarjeta.Negrita.TLabel").pack(anchor="w")
        ttk.Label(cuerpo, style="Tarjeta.Suave.TLabel", wraplength=340, justify="left",
                  text="Este ordenador se queda dentro. En los demás habrá que "
                       "entrar de nuevo con la contraseña nueva.").pack(anchor="w",
                                                                        pady=(4, 6))

        zona = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
        zona.pack(fill="x")

        widgets.etiqueta_campo(zona, "Contraseña de ahora")
        self.var_actual = tk.StringVar()
        self.campo_actual = ttk.Entry(zona, textvariable=self.var_actual, width=34,
                                      show="•")
        self.campo_actual.pack(fill="x")

        widgets.etiqueta_campo(zona, "Contraseña nueva")
        self.var_nueva = tk.StringVar()
        ttk.Entry(zona, textvariable=self.var_nueva, width=34, show="•").pack(fill="x")

        widgets.etiqueta_campo(zona, "Repite la nueva")
        self.var_repetida = tk.StringVar()
        ttk.Entry(zona, textvariable=self.var_repetida, width=34,
                  show="•").pack(fill="x")

        ttk.Label(zona, style="Tarjeta.Suave.TLabel", wraplength=340, justify="left",
                  text=f"Al menos {LETRAS_MINIMAS} letras o números. Una frase "
                       "corta que recuerdes vale más que un revoltijo que "
                       "acabes apuntando en un papel.").pack(anchor="w", pady=(8, 0))

        self.error = ttk.Label(cuerpo, text="", style="Tarjeta.Gasto.TLabel",
                               wraplength=340, justify="left")
        self.error.pack(anchor="w", pady=(8, 0))

        pie = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
        pie.pack(fill="x", pady=(14, 0))
        ttk.Button(pie, text="Cancelar", command=self._cerrar).pack(side="right")
        ttk.Button(pie, text="Cambiar la contraseña", style="Principal.TButton",
                   command=self._enviar).pack(side="right", padx=(0, 8))

        self.bind("<Return>", lambda _e: self._enviar())
        self.bind("<Escape>", lambda _e: self._cerrar())
        self.protocol("WM_DELETE_WINDOW", self._cerrar)

    def _enviar(self) -> None:
        actual = self.var_actual.get()
        nueva = self.var_nueva.get()
        # Lo que se puede comprobar aquí se comprueba aquí: es más rápido y no
        # gasta un intento de los que el servidor cuenta.
        if not actual or not nueva:
            self._fallo("Escribe la contraseña de ahora y la nueva.")
            return
        if len(nueva) < LETRAS_MINIMAS:
            self._fallo(f"La contraseña nueva necesita al menos "
                        f"{LETRAS_MINIMAS} letras o números.")
            return
        if nueva != self.var_repetida.get():
            self._fallo("Las dos veces que has escrito la nueva no coinciden.")
            return

        self.error.configure(text="Hablando con el servidor…")
        self.update_idletasks()
        try:
            self.sincronia.cambiar_contrasena(actual, nueva)
        except ErrorDeSincronia as error:
            self._fallo(str(error))
            return
        self.cambiada = True
        self.destroy()

    def _fallo(self, mensaje: str) -> None:
        self.error.configure(text=mensaje)
        self.bell()

    def _cerrar(self) -> None:
        self.destroy()

    def mostrar(self) -> bool:
        self.update_idletasks()
        self._centrar()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.campo_actual.focus_set()
        self.wait_window()
        return self.cambiada

    def _centrar(self) -> None:
        padre = self.master
        ancho, alto = self.winfo_width(), self.winfo_height()
        x = padre.winfo_rootx() + (padre.winfo_width() - ancho) // 2
        y = padre.winfo_rooty() + (padre.winfo_height() - alto) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")
