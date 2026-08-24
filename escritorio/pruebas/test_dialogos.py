"""Pruebas de los formularios emergentes.

Se construyen de verdad (hace falta pantalla) pero no se llegan a mostrar:
`mostrar()` bloquearía esperando al usuario. Lo que se comprueba es la parte
que puede fallar en silencio: la validación y el enseñar u ocultar campos.
"""

from __future__ import annotations

import sys
import tkinter as tk
import unittest
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


class PruebasWidgets(ConVentana):
    def test_campo_fecha_ida_y_vuelta(self):
        campo = widgets.CampoFecha(self.raiz, "2026-08-24")
        self.addCleanup(campo.destroy)
        self.assertEqual(campo.variable.get(), "24/08/2026")
        self.assertEqual(campo.iso(), "2026-08-24")

    def test_campo_fecha_vacio(self):
        campo = widgets.CampoFecha(self.raiz, "")
        self.addCleanup(campo.destroy)
        self.assertIsNone(campo.iso())

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


if __name__ == "__main__":
    unittest.main()
