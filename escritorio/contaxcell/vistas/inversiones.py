"""La cartera.

La idea que ordena toda esta pantalla: hay tres formas de que entre dinero en
la cartera —lo que pusiste al empezar, lo que aportas desde el banco y lo que
te regalan— y ninguna de las tres es rentabilidad. Lo que ha hecho el mercado
es lo que vale hoy menos las tres juntas.
"""

from __future__ import annotations

import datetime as dt
from tkinter import filedialog, ttk

from .. import calculos, dialogos, formato, traderepublic, widgets
from ..modelo import (CATEGORIAS_ACTIVO, INGRESO, INVERSION,
                      Activo, AportacionGratis, Valoracion, hoy)
from . import comun


SUSTITUIR = "Sustituirlas por las del extracto"
MANTENER = "Dejarlas como están"


class VistaInversiones:
    def __init__(self, padre, app):
        self.app = app
        self._avisos: list[widgets.Aviso] = []

        self.desplazable = widgets.MarcoDesplazable(padre)
        self.desplazable.pack(fill="both", expand=True)
        raiz = ttk.Frame(self.desplazable.interior, padding=18)
        raiz.pack(fill="both", expand=True)

        self._resumen(raiz)
        self._categorias(raiz)
        self._activos(raiz)
        self._compras(raiz)
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

    def _categorias(self, padre) -> None:
        """La cartera agrupada: cuánto hay en índices y cuánto en cada cosa.

        Con un solo fondo no dice nada, así que la tarjeta se esconde hasta
        que haya al menos dos grupos.
        """
        self.tarjeta_categorias = widgets.Tarjeta(padre, "Por categoría")
        self.tabla_categorias = widgets.Tabla(self.tarjeta_categorias.cuerpo, [
            widgets.Columna("categoria", "Categoría", 190, estira=True),
            widgets.Columna("cuantos", "Activos", 90, anclaje="e"),
            widgets.Columna("aportado", "Aportado", 130, anclaje="e"),
            widgets.Columna("valor", "Valor de mercado", 145, anclaje="e"),
            widgets.Columna("generado", "Generado", 125, anclaje="e"),
            widgets.Columna("peso", "De la cartera", 115, anclaje="e"),
        ], alto=4)
        self.tabla_categorias.pack(fill="x")
        # Se coloca ya, en su sitio, y se esconde o se enseña al refrescar:
        # asi vuelve siempre al mismo hueco entre el resumen y los activos.
        self.tarjeta_categorias.pack(fill="x", pady=(16, 0))

    def _compras(self, padre) -> None:
        """Las compras del activo elegido, una a una.

        Es lo que contesta a «los cien euros de cada semana, ¿cómo van?».
        Solo salen las que dicen cuántas participaciones compraron: las
        apuntadas a mano no lo dicen y de esas no se puede saber.
        """
        self.tarjeta_compras = widgets.Tarjeta(padre, "Compras")
        self.tabla_compras = widgets.Tabla(self.tarjeta_compras.cuerpo, [
            widgets.Columna("fecha", "Fecha", 110, estira=True),
            widgets.Columna("importe", "Invertido", 110, anclaje="e"),
            widgets.Columna("titulos", "Títulos", 105, anclaje="e"),
            widgets.Columna("pagado", "Precio pagado", 125, anclaje="e"),
            widgets.Columna("valor", "Vale hoy", 115, anclaje="e"),
            widgets.Columna("generado", "Generado", 115, anclaje="e"),
            widgets.Columna("rentabilidad", "Rentab.", 90, anclaje="e"),
        ], alto=8)
        self.tabla_compras.pack(fill="both", expand=True)
        self.compras_vacio = ttk.Label(self.tarjeta_compras.cuerpo,
                                       style="Tarjeta.Suave.TLabel",
                                       justify="center", text="")
        self.pie_compras = ttk.Label(self.tarjeta_compras.derecha, text="",
                                     style="Tarjeta.Suave.TLabel")
        self.pie_compras.pack(side="right")
        self.tarjeta_compras.pack(fill="x", pady=(16, 0))

    def _activos(self, padre) -> None:
        self.tarjeta_activos = widgets.Tarjeta(padre, "Activos")
        self.tarjeta_activos.pack(fill="x", pady=(16, 0))
        ttk.Button(self.tarjeta_activos.derecha, text="Añadir activo",
                   command=self.anadir_activo).pack(side="right")
        ttk.Button(self.tarjeta_activos.derecha, text="Importar de Trade Republic",
                   command=self.importar_extracto).pack(side="right", padx=(0, 8))

        self.tabla_activos = widgets.Tabla(self.tarjeta_activos.cuerpo, [
            widgets.Columna("nombre", "Activo", 150, estira=True),
            widgets.Columna("categoria", "Categoría", 105),
            widgets.Columna("inicial", "1 · Inicial", 95, anclaje="e"),
            widgets.Columna("banco", "2 · Del banco", 105, anclaje="e"),
            widgets.Columna("gratis", "3 · Gratis", 90, anclaje="e"),
            widgets.Columna("aportado", "Total aportado", 115, anclaje="e"),
            widgets.Columna("valor", "Valor de mercado", 125, anclaje="e"),
            widgets.Columna("generado", "Generado", 110, anclaje="e"),
            widgets.Columna("rentabilidad", "Rentab.", 80, anclaje="e"),
            widgets.Columna("valoracion", "Valorado", 100),
        ], alto=6, al_activar=lambda _c: self.editar_activo())
        self.tabla_activos.pack(fill="x")

        self.vacio_activos = ttk.Label(
            self.tarjeta_activos.cuerpo, style="Tarjeta.Suave.TLabel", justify="center",
            text="Todavía no has creado ningún activo.\n\nUn activo es cada sitio donde "
                 "tienes dinero invertido: un fondo, una cuenta remunerada, oro…")

        self.acciones_activos = ttk.Frame(self.tarjeta_activos.cuerpo, style="Tarjeta.TFrame")
        self.acciones_activos.pack(fill="x", pady=(10, 0))
        # Elegir un activo cambia las compras que se ensenan debajo.
        self.tabla_activos.arbol.bind(
            "<<TreeviewSelect>>", lambda _e: self._pintar_compras())

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
            dialogos.Opcion("categoria", "Categoría", self._categorias_de_activo(), "",
                            vacio="— sin categoría —",
                            ayuda="Para agrupar la cartera y ver cuánto tienes en "
                                  "cada cosa. Se puede dejar en blanco."),
        ], aceptar="Crear", validar=self._validar_nombre_libre).mostrar()
        if resultado is None:
            return

        nuevo = Activo(nombre=resultado["nombre"],
                       aportacion_inicial=resultado["inicial"],
                       valor_mercado=resultado["valor"],
                       ultima_valoracion=hoy(),
                       categoria=resultado["categoria"])
        self.app.cambiar(lambda libro: libro.activos.append(nuevo),
                         f"Activo «{nuevo.nombre}» creado.")

    # --- importar del banco ------------------------------------------------

    def _categorias_de_activo(self) -> list[str]:
        """Las que se ofrecen: las de siempre más las que ya estés usando."""
        usadas = [a.categoria for a in self.app.libro.activos if a.categoria]
        return list(dict.fromkeys(list(CATEGORIAS_ACTIVO) + sorted(set(usadas))))

    def _categorias_del_tipo(self, tipo: str) -> list[str]:
        return [c.nombre for c in self.app.libro.categorias if c.tipo == tipo]

    @staticmethod
    def _mejor_para_sobras(nombres: list[str]) -> str:
        """La categoria que menos chirria para lo que no encaja en ninguna.

        Los intereses del banco no son la nomina, y proponer la primera de la
        lista es proponer justo esa. Se busca una de «otros» y si no la hay se
        deja la ultima, que suele ser la cajon de sastre.
        """
        for nombre in nombres:
            if "otro" in nombre.lower():
                return nombre
        return nombres[-1] if nombres else ""

    def importar_extracto(self) -> None:
        """Trae del extracto de Trade Republic las compras del plan de inversión.

        Lo que hace falta y no está en ningún otro sitio son las
        participaciones que compró cada aportación: sin ellas solo se sabe
        cuánto dinero se metió, no cómo ha ido cada compra.
        """
        ruta = filedialog.askopenfilename(
            parent=self.app, title="Elige el extracto de Trade Republic",
            filetypes=[("Extractos en PDF", "*.pdf"), ("Todos los archivos", "*.*")])
        if not ruta:
            return

        try:
            lectura = traderepublic.leer(ruta)
        except traderepublic.NoEsUnExtracto as error:
            dialogos.error(self.app, "Ese PDF no parece un extracto",
                           f"{error}\n\nTiene que ser el «Certificado de saldo y "
                           "movimientos» que descargas desde la aplicación de "
                           "Trade Republic.")
            return
        except OSError as error:
            dialogos.error(self.app, "No se ha podido abrir el archivo", str(error))
            return
        except Exception as error:  # noqa: BLE001 - el mensaje es para el usuario
            dialogos.error(self.app, "No se ha podido leer el extracto",
                           f"El archivo ha dado este error:\n\n{error}")
            return

        if not lectura.apuntes:
            dialogos.avisar(self.app, "No he encontrado nada que apuntar",
                            "El extracto se ha leído, pero no trae compras del plan "
                            "de inversión ni intereses en el periodo que cubre.")
            return

        datos = self._preguntar_como_importar(lectura)
        if datos is None:
            return

        resultado = {}

        def aplicar(libro):
            hecho = traderepublic.aplicar(
                libro, lectura,
                categoria_inversion=datos["inversion"],
                categoria_ingreso=datos["ingreso"],
                categoria_activo=datos["categoria_activo"],
                sustituir=datos["a_sustituir"],
                categoria_bonificacion=datos["ingreso_bonificacion"])
            # Lo que vale hoy va al activo del extracto, lo acabe de crear la
            # importación o lo tuvieras de antes. Solo se pregunta cuando hay
            # uno, que es cuando un único número tiene sentido.
            for nombre, valor in datos["valores"].items():
                objetivo = libro.activo(nombre)
                if objetivo is not None and valor:
                    objetivo.valor_mercado = valor
                    objetivo.ultima_valoracion = hoy()
            resultado["hecho"] = hecho

        if not self.app.cambiar(aplicar):
            return
        self._contar_lo_importado(resultado["hecho"], lectura)

    def _preguntar_como_importar(self, lectura) -> dict | None:
        de_inversion = self._categorias_del_tipo(INVERSION)
        de_ingreso = self._categorias_del_tipo(INGRESO)
        if not de_inversion or not de_ingreso:
            dialogos.error(self.app, "Faltan categorías",
                           "Para importar hace falta al menos una categoría de "
                           "inversión y una de ingreso. Créalas en Ajustes.")
            return None

        fondos = self._fondos_del_extracto(lectura)
        intereses = [i for i in lectura.ingresos
                     if i.concepto == traderepublic.CONCEPTO_INTERESES]
        sueltas = [i for i in lectura.ingresos
                   if i.concepto == traderepublic.CONCEPTO_BONIFICACION]

        campos = [dialogos.Nota(self._desglose(lectura, fondos, intereses, sueltas))]

        if lectura.compras or lectura.gratis:
            campos += [
                dialogos.Opcion("inversion", "Categoría de las aportaciones",
                                de_inversion, de_inversion[0]),
                dialogos.Opcion("categoria_activo", "Categoría del activo",
                                self._categorias_de_activo(), CATEGORIAS_ACTIVO[0]),
            ]
            # Una casilla por fondo: con dos fondos, un solo número no vale
            # para los dos.
            # En blanco a propósito: rellenarlo con lo invertido sería
            # apuntar una valoración que nadie ha hecho, y el fondo se
            # quedaría diciendo que vale justo lo que costó. Vacío es
            # «todavía no lo sé», que es la verdad y además se avisa.
            for numero, (nombre, _compras, _metido, _regalado) in enumerate(fondos):
                tenia = self.app.libro.activo(nombre)
                campos.append(dialogos.Importe(
                    f"valor{numero}", f"¿Cuánto vale hoy {nombre}?",
                    tenia.valor_mercado if tenia and tenia.valor_mercado else None,
                    opcional=True,
                    ayuda="Míralo en el banco, o déjalo en blanco."))

        if intereses:
            campos.append(dialogos.Opcion(
                "ingreso", "Categoría de los intereses", de_ingreso,
                self._mejor_para_sobras(de_ingreso)))
        if sueltas:
            # Bonificaciones que no se reinvirtieron: son dinero que se quedó
            # en la cuenta, y no tienen por qué ir con los intereses.
            campos.append(dialogos.Opcion(
                "ingreso_bonificacion", "Categoría de las bonificaciones",
                de_ingreso, self._mejor_para_sobras(de_ingreso)))

        # Lo que ya tenías apuntado a mano de ese mismo dinero.
        a_mano = traderepublic.aportaciones_a_mano(self.app.libro, lectura)
        if a_mano:
            campos += [
                dialogos.Nota(self._texto_de_lo_apuntado(a_mano)),
                dialogos.Opcion("sustituir", "¿Qué hago con ellas?",
                                [SUSTITUIR, MANTENER], SUSTITUIR),
            ]

        datos = dialogos.Formulario(self.app, "Importar de Trade Republic", campos,
                                    aceptar="Importar").mostrar()
        if datos is None:
            return None

        por_defecto = self._mejor_para_sobras(de_ingreso)
        datos.setdefault("inversion", de_inversion[0])
        datos.setdefault("ingreso", por_defecto)
        datos.setdefault("ingreso_bonificacion", datos.get("ingreso", por_defecto))
        datos.setdefault("categoria_activo", "")
        datos["valores"] = {fondo[0]: datos.get(f"valor{numero}")
                            for numero, fondo in enumerate(fondos)}
        datos["a_sustituir"] = ([m.id for m in a_mano]
                                if datos.get("sustituir") == SUSTITUIR else [])
        return datos

    def _fondos_del_extracto(self, lectura) -> list[tuple]:
        """Cada fondo por separado: sus compras y lo que le han regalado.

        Con un MSCI World y un S&P 500 en el mismo extracto hay que poder ver
        cuánto va a cada uno, no un total en el que no se distinguen. Las
        bonificaciones se cuentan aparte para que las cifras del resumen
        sumen a la vista y no aparezca el mismo dinero en dos renglones.
        """
        cuenta: dict[str, list] = {}
        for apunte in lectura.compras + lectura.gratis:
            activo = (self.app.libro.activo_por_isin(apunte.isin)
                      or self.app.libro.activo(apunte.nombre_activo))
            nombre = activo.nombre if activo else apunte.nombre_activo
            fila = cuenta.setdefault(nombre, [0, 0.0, 0.0])
            if apunte.clase == traderepublic.GRATIS:
                fila[2] = calculos.redondea(fila[2] + apunte.importe)
            else:
                fila[0] += 1
                fila[1] = calculos.redondea(fila[1] + apunte.importe)
        return [(nombre, compras, metido, regalado)
                for nombre, (compras, metido, regalado) in cuenta.items()]

    def _desglose(self, lectura, fondos, intereses, sueltas) -> str:
        """El resumen en columnas en vez de en un párrafo."""
        lineas = [f"Del {formato.fecha_corta(lectura.desde)} al "
                  f"{formato.fecha_corta(lectura.hasta)}:", ""]
        for nombre, compras, metido, _regalado in fondos:
            lineas.append(f"   {nombre}   ·   {_cuantas(compras, 'compra')}   ·   "
                          f"{formato.euros(metido, True)}")
        if lectura.gratis:
            regalado = calculos.redondea(sum(g.importe for g in lectura.gratis))
            lineas.append(f"   Bonificaciones reinvertidas   ·   "
                          f"{len(lectura.gratis)}   ·   "
                          f"{formato.euros(regalado, True)}")
        for grupo, etiqueta in ((intereses, "Intereses"),
                                (sueltas, "Bonificaciones sin reinvertir")):
            if grupo:
                total = calculos.redondea(sum(i.importe for i in grupo))
                lineas.append(f"   {etiqueta}   ·   {len(grupo)}   ·   "
                              f"{formato.euros(total, True)}")
        return "\n".join(lineas)

    def _texto_de_lo_apuntado(self, a_mano: list) -> str:
        """La lista de lo que se quitaría, para poder mirarla antes de decidir."""
        total = calculos.redondea(sum(m.importe for m in a_mano))
        cabecera = (f"Ya tienes esto apuntado a mano en esos mismos meses, "
                    f"{_cuantas(len(a_mano), 'aportación')} "
                    f"por {formato.euros(total, True)}:")
        lineas = [f"   · {formato.fecha_corta(m.fecha)}  "
                  f"{formato.euros(m.importe, True)}"
                  f"{'  ' + m.descripcion if m.descripcion else ''}"
                  for m in sorted(a_mano, key=lambda m: m.fecha)[:6]]
        if len(a_mano) > 6:
            lineas.append(f"   · y {len(a_mano) - 6} más")
        return cabecera + "\n" + "\n".join(lineas)

    def _contar_lo_importado(self, hecho, lectura) -> None:
        partes = []
        if hecho.compras:
            partes.append(f"{hecho.compras} compras por {formato.euros(hecho.invertido, True)}")
        if hecho.gratis:
            partes.append(f"{hecho.gratis} bonificaciones por "
                          f"{formato.euros(hecho.regalado, True)}")
        if hecho.ingresos:
            partes.append(f"{hecho.ingresos} ingresos por {formato.euros(hecho.ingresado, True)}")
        if not partes:
            dialogos.avisar(self.app, "Ya estaba todo apuntado",
                            f"Los {hecho.repetidos} apuntes del extracto ya estaban "
                            "en el libro. No se ha duplicado nada.")
            return

        detalle = "Se han apuntado " + " y ".join(partes) + "."
        if hecho.sustituidas:
            detalle += (f"\n\nSe han quitado {hecho.sustituidas} aportaciones que "
                        f"tenías a mano por {formato.euros(hecho.sustituido, True)}: "
                        "eran ese mismo dinero, y ahora está con el detalle de cada "
                        "compra.")
        if hecho.activos_nuevos:
            detalle += f"\n\nActivo nuevo: {', '.join(hecho.activos_nuevos)}."
        if hecho.repetidos:
            detalle += f"\n\nOtros {hecho.repetidos} ya estaban y no se han repetido."
        if lectura.avisos:
            detalle += "\n\n" + "\n".join(lectura.avisos)
        if any(a.sin_valorar for a in calculos.cartera(self.app.libro).activos):
            detalle += ("\n\nPara ver cómo va cada compra, apunta con «Editar» lo que "
                        "vale hoy el activo: el precio por título sale solo.")
        dialogos.avisar(self.app, "Extracto importado", detalle)
        self.app.estado("Extracto de Trade Republic importado.", "bien")

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
            dialogos.Importe("valor", "Valor de mercado hoy",
                             activo.valor_mercado if activo.ultima_valoracion else None,
                             opcional=True,
                             ayuda="Déjalo en blanco si todavía no lo sabes: mejor "
                                   "eso que apuntar un número inventado."),
            dialogos.Fecha("valoracion", "Fecha de esa valoración",
                           activo.ultima_valoracion or hoy()),
            dialogos.Opcion("categoria", "Categoría", self._categorias_de_activo(),
                            activo.categoria, vacio="— sin categoría —"),
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
            # En blanco es «no lo sé»: se queda sin valorar, que no es lo
            # mismo que valer cero. Un cero escrito a mano sí se respeta.
            if resultado["valor"] is None:
                objetivo.valor_mercado = 0.0
                objetivo.ultima_valoracion = ""
            else:
                objetivo.valor_mercado = resultado["valor"]
                objetivo.ultima_valoracion = resultado["valoracion"]
            objetivo.categoria = resultado["categoria"]

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
        self._pintar_categorias(cartera)
        self._pintar_activos(cartera)
        self._pintar_compras()
        self._pintar_historico(cartera)
        self._pintar_gratis()

    def _pintar_categorias(self, cartera) -> None:
        """Con un solo grupo esta tabla no dice nada, así que se esconde."""
        grupos = calculos.por_categoria(cartera)
        if len(grupos) < 2:
            self.tarjeta_categorias.marco.pack_forget()
            return

        filas = []
        for grupo in grupos:
            cuantos = len(grupo.activos)
            filas.append((grupo.categoria, (
                grupo.categoria,
                "1 activo" if cuantos == 1 else f"{cuantos} activos",
                formato.euros(grupo.total_aportado),
                formato.euros(grupo.valor_mercado),
                formato.euros_con_signo(grupo.generado),
                formato.porcentaje(grupo.peso, 0),
            ), (_color(grupo.generado),)))
        self.tabla_categorias.poner(filas)
        self.tabla_categorias.ajustar_alto(len(filas), minimo=2, maximo=8)

        if not self.tarjeta_categorias.marco.winfo_ismapped():
            self.tarjeta_categorias.pack(fill="x", pady=(16, 0),
                                         before=self.tarjeta_activos.marco)

    def _pintar_compras(self) -> None:
        """Las compras del activo elegido arriba. Sin activo elegido, las del
        primero que tenga: es lo que se quiere ver casi siempre."""
        elegido = self.tabla_activos.seleccion()
        if elegido in (None, "__total__"):
            con_compras = [a for a in calculos.cartera(self.app.libro).activos
                           if a.hay_titulos]
            elegido = con_compras[0].nombre if con_compras else None

        compras = calculos.compras_de(self.app.libro, elegido) if elegido else []
        self.tarjeta_compras.titulo(f"Compras de {elegido}" if elegido else "Compras")

        filas = []
        for compra in compras:
            filas.append((compra.id, (
                formato.fecha_corta(compra.fecha),
                formato.euros(compra.importe),
                formato.numero(compra.titulos, 6),
                formato.euros(compra.precio_pagado),
                formato.euros(compra.valor_hoy) if compra.precio_hoy > 0 else "—",
                formato.euros_con_signo(compra.generado) if compra.precio_hoy > 0 else "—",
                formato.porcentaje(compra.rentabilidad) if compra.precio_hoy > 0 else "—",
            ), (_color(compra.generado) if compra.precio_hoy > 0 else "",)))

        self.tabla_compras.poner(filas)
        self.tabla_compras.ajustar_alto(len(filas), minimo=3, maximo=14)
        self._pie_de_compras(compras)

        hay = bool(filas)
        if hay:
            self.compras_vacio.pack_forget()
            if not self.tabla_compras.winfo_ismapped():
                self.tabla_compras.pack(fill="both", expand=True)
        else:
            self.tabla_compras.pack_forget()
            self.compras_vacio.configure(text=(
                "Aquí se ve cómo va cada compra por separado.\n\n"
                "Hacen falta las participaciones que compró cada una, y eso solo "
                "viene en el extracto del banco:\nusa «Importar de Trade Republic»."))
            if not self.compras_vacio.winfo_ismapped():
                self.compras_vacio.pack(pady=30)

    def _pie_de_compras(self, compras) -> None:
        if not compras:
            self.pie_compras.configure(text="")
            return
        titulos = sum(c.titulos for c in compras)
        medio = sum(c.importe for c in compras) / titulos
        partes = [f"{formato.numero(titulos, 4)} títulos",
                  f"pagados a {formato.euros(medio)} de media"]
        if compras[0].precio_hoy > 0:
            partes.append(f"hoy a {formato.euros(compras[0].precio_hoy)}")
        self.pie_compras.configure(text="   ·   ".join(partes))

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
        if cartera.sin_valorar:
            nombres = ", ".join(a.nombre for a in cartera.sin_valorar)
            mensajes.append(
                f"Todavía no has dicho lo que vale hoy: {nombres}. Mientras tanto se "
                f"da por hecho que vale lo aportado "
                f"({formato.euros(cartera.aportado_sin_valorar, True)}), así que sale "
                "sin ganancia ni pérdida. Pulsa «Editar» y apunta el valor de mercado.")

        for texto in mensajes:
            aviso = widgets.Aviso(self.zona_avisos, texto, "alerta")
            aviso.pack(fill="x", pady=(12, 0))
            self._avisos.append(aviso)

    def _pintar_activos(self, cartera) -> None:
        filas = []
        for activo in cartera.activos:
            filas.append((activo.nombre, (
                activo.nombre,
                activo.categoria or "—",
                formato.euros(activo.aportacion_inicial),
                formato.euros(activo.aportado_banco),
                formato.euros(activo.aportado_gratis),
                formato.euros(activo.total_aportado),
                formato.euros(activo.valor_mercado),
                "—" if activo.sin_valorar else formato.euros_con_signo(activo.generado),
                "—" if activo.sin_valorar or activo.total_aportado <= 0
                else formato.porcentaje(activo.rentabilidad),
                "sin valorar" if activo.sin_valorar
                else formato.fecha_corta(activo.ultima_valoracion),
            ), ("aviso" if activo.sin_valorar else "",)))

        if filas:
            filas.append(("__total__", (
                "TOTAL CARTERA",
                "",
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


def _cuantas(cuantas: int, singular: str) -> str:
    """«1 compra» y no «1 compras»."""
    return f"1 {singular}" if cuantas == 1 else f"{cuantas} {singular}s"


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
