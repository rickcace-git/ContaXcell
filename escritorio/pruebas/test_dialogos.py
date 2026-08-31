"""Pruebas de los formularios emergentes.

Se construyen de verdad (hace falta pantalla) pero no se llegan a mostrar:
`mostrar()` bloquearía esperando al usuario. Lo que se comprueba es la parte
que puede fallar en silencio: la validación y el enseñar u ocultar campos.
"""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk
import unittest
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from contaxcell import dialogos, tema, widgets  # noqa: E402


class ConVentana(unittest.TestCase):
    """Base para las pruebas que necesitan una ventana de tkinter."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.raiz = tk.Tk()
        except tk.TclError as error:
            raise unittest.SkipTest(f"no hay pantalla disponible: {error}") from error
        cls.raiz.withdraw()
        fuentes = tema.Fuentes()
        tema.aplicar(cls.raiz, tema.CLARA, fuentes)
        widgets.usar(tema.CLARA, fuentes)

    @classmethod
    def tearDownClass(cls):
        cls.raiz.destroy()

    def formulario(self, campos, **kw) -> dialogos.Formulario:
        ventana = dialogos.Formulario(self.raiz, "Prueba", campos, **kw)
        self.addCleanup(ventana.destroy)
        return ventana


class PruebasValidacion(ConVentana):
    def test_recoge_los_cuatro_tipos_de_campo(self):
        ventana = self.formulario([
            dialogos.Texto("concepto", "Concepto", "Cerveza"),
            dialogos.Importe("importe", "Importe", 4.5),
            dialogos.Fecha("fecha", "Fecha", "2026-08-16"),
            dialogos.Opcion("categoria", "Categoría", ["Ocio", "Casa"], "Ocio"),
            dialogos.Nota("Esto es solo una explicación."),
        ])
        self.assertEqual(ventana._recoger(), {
            "concepto": "Cerveza", "importe": 4.5,
            "fecha": "2026-08-16", "categoria": "Ocio",
        })

    def test_importe_con_coma(self):
        ventana = self.formulario([dialogos.Importe("importe", "Importe")])
        ventana._variables["importe"].set("1.234,56")
        self.assertEqual(ventana._recoger()["importe"], 1234.56)

    def test_importe_que_no_es_numero(self):
        ventana = self.formulario([dialogos.Importe("importe", "Importe")])
        ventana._variables["importe"].set("dos euros")
        self.assertIsNone(ventana._recoger())
        self.assertIn("número", ventana.error.cget("text"))

    def test_importe_negativo_se_rechaza_con_explicacion(self):
        ventana = self.formulario([dialogos.Importe("importe", "Importe")])
        ventana._variables["importe"].set("-10")
        self.assertIsNone(ventana._recoger())
        self.assertIn("categoría", ventana.error.cget("text"))

    def test_importe_cero_cuando_no_se_permite(self):
        ventana = self.formulario([
            dialogos.Importe("importe", "Importe", permitir_cero=False)])
        ventana._variables["importe"].set("0")
        self.assertIsNone(ventana._recoger())
        self.assertIn("mayor que cero", ventana.error.cget("text"))

    def test_fecha_imposible(self):
        ventana = self.formulario([dialogos.Fecha("fecha", "Fecha", "2026-08-16")])
        ventana._variables["fecha"].set("31/02/2026")
        self.assertIsNone(ventana._recoger())
        self.assertIn("fecha", ventana.error.cget("text").lower())

    def test_importe_opcional_en_blanco_es_none_y_no_cero(self):
        """«No lo sé» no es «vale cero», y hay que poder distinguirlo.

        Rellenar el valor de un fondo con lo invertido apuntaba una
        valoración que nadie había hecho: el fondo decía valer justo lo que
        costó, y cualquier diferencia salía como pérdida.
        """
        ventana = self.formulario([
            dialogos.Importe("valor", "Valor de mercado hoy", None, opcional=True)])
        self.assertIsNone(ventana._recoger()["valor"])

    def test_importe_opcional_con_un_cero_escrito_sí_es_cero(self):
        ventana = self.formulario([
            dialogos.Importe("valor", "Valor de mercado hoy", None, opcional=True)])
        ventana._variables["valor"].set("0")
        self.assertEqual(ventana._recoger()["valor"], 0.0)

    def test_un_importe_normal_en_blanco_sigue_siendo_un_error(self):
        ventana = self.formulario([dialogos.Importe("importe", "Importe")])
        self.assertIsNone(ventana._recoger())

    def test_fecha_opcional_en_blanco_vale(self):
        # Es la fecha de fin de un pago periódico: en blanco es «no se acaba».
        ventana = self.formulario([dialogos.Fecha("hasta", "Último pago", "",
                                                  opcional=True)])
        self.assertEqual(ventana._recoger(), {"hasta": ""})

    def test_fecha_opcional_con_valor_se_recoge_igual(self):
        ventana = self.formulario([dialogos.Fecha("hasta", "Último pago",
                                                  "2026-12-10", opcional=True)])
        self.assertEqual(ventana._recoger(), {"hasta": "2026-12-10"})

    def test_fecha_opcional_mal_escrita_sigue_siendo_un_error(self):
        ventana = self.formulario([dialogos.Fecha("hasta", "Último pago", "",
                                                  opcional=True)])
        ventana._variables["hasta"].set("el mes que viene")
        self.assertIsNone(ventana._recoger())

    def test_texto_obligatorio_vacio(self):
        ventana = self.formulario([
            dialogos.Texto("nombre", "Nombre", obligatorio=True)])
        self.assertIsNone(ventana._recoger())
        self.assertIn("vacío", ventana.error.cget("text"))

    def test_el_texto_de_ejemplo_no_cuenta_como_escrito(self):
        # La pista gris no es algo que haya tecleado el usuario.
        ventana = self.formulario([
            dialogos.Texto("nombre", "Nombre", pista="Fondo indexado",
                           obligatorio=True)])
        self.assertEqual(ventana._variables["nombre"].get(), "Fondo indexado")
        self.assertEqual(ventana.valor("nombre"), "")
        self.assertIsNone(ventana._recoger())

    def test_escribir_justo_el_texto_de_ejemplo_sí_cuenta(self):
        """Llamar «Fondo indexado» a un fondo indexado tiene que valer.

        Se reconocía la pista comparando el texto, así que escribir el
        ejemplo pasaba por no haber escrito nada y saltaba «no puede quedar
        vacío». Pasaba con las cuatro pistas que hay: «Gimnasio»,
        «Fondo indexado», «Suscripciones» y la del cashback.
        """
        ventana = self.formulario([
            dialogos.Texto("nombre", "Nombre", pista="Fondo indexado",
                           obligatorio=True)])
        control = ventana._controles["nombre"]

        control.event_generate("<FocusIn>")   # entra en la casilla: se borra
        ventana._variables["nombre"].set("Fondo indexado")   # y lo teclea

        self.assertEqual(ventana.valor("nombre"), "Fondo indexado")
        self.assertEqual(ventana._recoger(), {"nombre": "Fondo indexado"})

    def test_dejarlo_vacío_devuelve_la_pista_y_vuelve_a_estar_vacío(self):
        ventana = self.formulario([
            dialogos.Texto("nombre", "Nombre", pista="Gimnasio")])
        control = ventana._controles["nombre"]

        control.event_generate("<FocusIn>")
        self.assertEqual(ventana._variables["nombre"].get(), "")
        control.event_generate("<FocusOut>")

        self.assertEqual(ventana._variables["nombre"].get(), "Gimnasio")
        self.assertEqual(ventana.valor("nombre"), "")

    def test_opcion_vacia_devuelve_cadena_vacia(self):
        ventana = self.formulario([
            dialogos.Opcion("activo", "Activo", ["Fondo"], "", vacio="— sin asignar —")])
        self.assertEqual(ventana._recoger()["activo"], "")

    def test_validacion_propia(self):
        ventana = self.formulario(
            [dialogos.Texto("nombre", "Nombre", "Repetido")],
            validar=lambda valores: "Ya existe una categoría con ese nombre."
            if valores["nombre"] == "Repetido" else None)
        self.assertIsNone(ventana._recoger())
        self.assertIn("Ya existe", ventana.error.cget("text"))


class PruebasParrafoYCasilla(ConVentana):
    """Los dos campos que no llevan una variable de texto detrás.

    El párrafo se lee del propio control, y por eso es el que se rompe en
    silencio si alguien toca `valor()`.
    """

    def test_el_parrafo_se_recoge_entero(self):
        ventana = self.formulario([dialogos.Parrafo("nota", "Nota", "Primera")])
        ventana._controles["nota"].insert("end", "\nSegunda")

        self.assertEqual(ventana._recoger()["nota"], "Primera\nSegunda")

    def test_un_parrafo_vacio_es_cadena_vacia(self):
        ventana = self.formulario([dialogos.Parrafo("nota", "Nota")])
        self.assertEqual(ventana._recoger()["nota"], "")

    def test_un_parrafo_obligatorio_avisa(self):
        ventana = self.formulario([dialogos.Parrafo("nota", "Nota", obligatorio=True)])
        self.assertIsNone(ventana._recoger())
        self.assertIn("vacío", ventana.error.cget("text"))

    def test_enter_dentro_del_parrafo_no_guarda_el_formulario(self):
        # Si la ventana siguiera oyendo el Enter, escribir una segunda línea
        # cerraría el formulario a media nota.
        ventana = self.formulario([dialogos.Parrafo("nota", "Nota")])
        self.assertNotIn(str(ventana), ventana._controles["nota"].bindtags())

    def test_la_casilla_devuelve_si_o_no(self):
        ventana = self.formulario([dialogos.Casilla("apuntar", "Apuntar", False)])
        self.assertIs(ventana._recoger()["apuntar"], False)

        ventana._variables["apuntar"].set(True)
        self.assertIs(ventana._recoger()["apuntar"], True)

    def test_la_casilla_puede_enseñar_otro_campo(self):
        def al_cambiar(formulario, _evento):
            formulario.mostrar_campo("categoria", bool(formulario.valor("apuntar")))

        ventana = self.formulario([
            dialogos.Casilla("apuntar", "Apuntar", False),
            dialogos.Opcion("categoria", "Categoría", ["Ocio"], "Ocio"),
        ], al_cambiar=al_cambiar)

        self.assertFalse(ventana.campo_visible("categoria"))
        ventana._variables["apuntar"].set(True)
        ventana._cambio()
        self.assertTrue(ventana.campo_visible("categoria"))


class PruebasCamposCondicionales(ConVentana):
    def test_ocultar_y_volver_a_enseñar_respeta_el_orden(self):
        campos = [
            dialogos.Texto("uno", "Uno"),
            dialogos.Texto("dos", "Dos"),
            dialogos.Texto("tres", "Tres"),
        ]
        ventana = self.formulario(campos)
        ventana.update_idletasks()

        ventana.mostrar_campo("dos", False)
        ventana.update_idletasks()
        self.assertFalse(ventana._bloques["dos"].winfo_ismapped())

        ventana.mostrar_campo("dos", True)
        ventana.update_idletasks()
        colocados = [h for h in ventana.zona_campos.pack_slaves()]
        self.assertEqual(colocados.index(ventana._bloques["dos"]),
                         colocados.index(ventana._bloques["uno"]) + 1)

    def test_cambiar_las_opciones_de_una_lista(self):
        ventana = self.formulario([
            dialogos.Opcion("activo", "Activo", ["Fondo"], "Fondo")])
        ventana.poner_opciones("activo", ["Otro", "Tercero"])
        # El valor anterior ya no existe, así que se queda el primero nuevo.
        self.assertEqual(ventana.valor("activo"), "Otro")

    def test_al_cambiar_se_llama_al_construir(self):
        llamadas = []
        self.formulario([dialogos.Opcion("tipo", "Tipo", ["A", "B"], "A")],
                        al_cambiar=lambda ventana, _e: llamadas.append(1))
        self.assertEqual(len(llamadas), 1)

    def test_el_campo_que_nace_oculto_no_se_queda_puesto(self):
        """Esconder un campo desde `al_cambiar` tiene que funcionar.

        Es el momento en el que la ventana aún no está dibujada. Cuando esto
        se preguntaba con `winfo_ismapped`, que ahí contesta que no a todo, el
        campo se quedaba a la vista: «Editar movimiento» enseñaba la casilla
        del activo aunque fuera un gasto.
        """
        ventana = self.formulario(
            [dialogos.Texto("uno", "Uno"), dialogos.Texto("dos", "Dos")],
            al_cambiar=lambda formulario, _e: formulario.mostrar_campo("dos", False))
        ventana.update_idletasks()

        self.assertFalse(ventana.campo_visible("dos"))
        self.assertFalse(ventana._bloques["dos"].winfo_ismapped())

    def test_volver_a_enseñarlo_lo_devuelve_a_su_sitio(self):
        ventana = self.formulario(
            [dialogos.Texto("uno", "Uno"), dialogos.Texto("dos", "Dos"),
             dialogos.Texto("tres", "Tres")],
            al_cambiar=lambda formulario, _e: formulario.mostrar_campo("dos", False))
        ventana.mostrar_campo("dos", True)
        ventana.update_idletasks()

        colocados = list(ventana.zona_campos.pack_slaves())
        self.assertEqual(colocados.index(ventana._bloques["dos"]),
                         colocados.index(ventana._bloques["uno"]) + 1)


class PruebasCampoFecha(ConVentana):
    def campo(self, iso: str = "2026-08-24") -> widgets.CampoFecha:
        casilla = widgets.CampoFecha(self.raiz, iso)
        self.addCleanup(casilla.destroy)
        return casilla

    def test_campo_fecha_ida_y_vuelta(self):
        casilla = self.campo()
        self.assertEqual(casilla.variable.get(), "24/08/2026")
        self.assertEqual(casilla.iso(), "2026-08-24")

    def test_campo_fecha_vacio(self):
        self.assertIsNone(self.campo("").iso())

    def test_no_deja_teclear_letras(self):
        # En una fecha no pintan nada, y rechazarlas mientras se escribe
        # ahorra el error de después.
        casilla = self.campo()
        for imposible in ("hola", "26/ago/2026", "26x08", "ayer", "26/08/2026 "):
            self.assertFalse(casilla._admite(imposible), imposible)

    def test_deja_teclear_lo_que_sí_es_una_fecha(self):
        casilla = self.campo()
        for vale in ("", "2", "26", "26/", "26/08/2026", "2026-08-26", "1.1.27"):
            self.assertTrue(casilla._admite(vale), vale)

    def test_no_deja_pasarse_de_largo(self):
        self.assertFalse(self.campo()._admite("26/08/20260"))

    def test_el_calendario_se_abre_en_el_mes_de_la_fecha(self):
        casilla = self.campo("2026-03-09")
        casilla.abrir_calendario()
        self.addCleanup(casilla.calendario.cerrar)
        self.assertEqual(casilla.calendario.mes, date(2026, 3, 1))
        self.assertEqual(casilla.calendario.elegido, date(2026, 3, 9))

    def test_elegir_un_día_lo_escribe_en_la_casilla(self):
        casilla = self.campo("2026-08-24")
        casilla.abrir_calendario()
        casilla.calendario._elegir(date(2026, 3, 9))

        self.assertEqual(casilla.iso(), "2026-03-09")
        self.assertEqual(casilla.variable.get(), "09/03/2026")

    def test_el_calendario_pasa_de_diciembre_a_enero(self):
        casilla = self.campo("2026-12-15")
        casilla.abrir_calendario()
        self.addCleanup(casilla.calendario.cerrar)

        casilla.calendario._mover(1)
        self.assertEqual(casilla.calendario.mes, date(2027, 1, 1))
        casilla.calendario._mover(-1)
        casilla.calendario._mover(-1)
        self.assertEqual(casilla.calendario.mes, date(2026, 11, 1))

    def test_pulsar_el_botón_otra_vez_lo_cierra(self):
        casilla = self.campo()
        casilla.abrir_calendario()
        abierto = casilla.calendario
        self.assertTrue(abierto.winfo_exists())

        casilla.abrir_calendario()
        self.assertIsNone(casilla.calendario)
        self.assertFalse(abierto.winfo_exists())

    def test_al_cerrarse_devuelve_el_ratón_a_quien_lo_tenía(self):
        """El calendario se abre dentro de formularios que son modales.

        Si al cerrarse no devuelve el agarre del ratón, la ventana de detrás
        se vuelve pulsable con el formulario todavía abierto.
        """
        dueno = tk.Toplevel(self.raiz)
        self.addCleanup(dueno.destroy)
        dueno.grab_set()

        casilla = widgets.CampoFecha(dueno, "2026-08-24")
        casilla.abrir_calendario()
        self.assertEqual(str(casilla.calendario.agarraba), str(dueno))

        casilla.calendario.cerrar()
        self.assertEqual(str(dueno.grab_current()), str(dueno))

    def test_con_la_casilla_vacía_el_calendario_se_abre_en_hoy(self):
        casilla = self.campo("")
        casilla.abrir_calendario()
        self.addCleanup(casilla.calendario.cerrar)
        self.assertEqual(casilla.calendario.mes, date.today().replace(day=1))


class PruebasWidgets(ConVentana):

    def test_la_barra_aguanta_valores_raros(self):
        barra = widgets.Barra(self.raiz)
        self.addCleanup(barra.destroy)
        for valor in (0, 0.5, 1, 1.7, float("inf"), float("nan"), -3):
            barra.dibujar(valor, semaforo=True)  # no debe lanzar nada

    def test_panel_de_cifras_actualiza_sin_duplicar(self):
        panel = widgets.PanelCifras(self.raiz, columnas=2)
        self.addCleanup(panel.destroy)
        panel.poner("a", "Uno", "1,00 €")
        panel.poner("a", "Uno", "2,00 €", "Gasto")
        self.assertEqual(len(panel._cifras), 1)
        self.assertEqual(panel._cifras["a"].etiqueta_valor.cget("text"), "2,00 €")

    def test_la_casilla_tambien_se_cambia_de_rotulo(self):
        # La misma casilla dice «gastos del año» o «gastos del mes» según lo
        # que se esté mirando en el resumen.
        panel = widgets.PanelCifras(self.raiz, columnas=2)
        self.addCleanup(panel.destroy)
        panel.poner("a", "Gastos del año", "1,00 €")
        panel.poner("a", "Gastos del mes", "2,00 €")
        self.assertEqual(panel._cifras["a"].etiqueta_rotulo.cget("text"),
                         "GASTOS DEL MES")

    def test_quitar_una_tarjeta_no_deja_el_marco_puesto(self):
        # Quitando solo la tarjeta se quedaba el marco del borde, vacío y con
        # el alto que tenía: un hueco gris en medio de la pantalla.
        padre = ttk.Frame(self.raiz)
        self.addCleanup(padre.destroy)
        tarjeta = widgets.Tarjeta(padre, "Prueba")
        tarjeta.pack(fill="x")
        self.raiz.update_idletasks()

        tarjeta.pack_forget()
        self.assertEqual(padre.pack_slaves(), [])


if __name__ == "__main__":
    unittest.main()
