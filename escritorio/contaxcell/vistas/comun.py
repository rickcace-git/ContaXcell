"""Cosas que usan varias pestañas.

Editar y borrar un movimiento se hace desde «Apuntar» y desde «Movimientos»,
así que el formulario y la confirmación viven aquí y no duplicados en las dos.
"""

from __future__ import annotations

from .. import dialogos, formato
from ..modelo import INGRESO, INVERSION, Movimiento

SIN_ASIGNAR = "— sin asignar —"


def categorias_para(libro, tipo_boton: str) -> list[str]:
    """Las categorías que tienen sentido según el botón elegido.

    Un gasto puede ser también una aportación a inversión: el dinero sale del
    banco igual. Un ingreso solo puede ser una categoría de ingreso.
    """
    if tipo_boton == "ingreso":
        return [c.nombre for c in libro.categorias if c.tipo == INGRESO]
    return [c.nombre for c in libro.categorias if c.tipo != INGRESO]


def es_aportacion(libro, categoria: str) -> bool:
    return libro.tipo_de(categoria) == INVERSION


def etiqueta_de(libro, movimiento: Movimiento) -> str:
    """Una línea que identifica el movimiento en una confirmación."""
    piezas = [formato.fecha_corta(movimiento.fecha)]
    if movimiento.descripcion:
        piezas.append(movimiento.descripcion)
    piezas.append(movimiento.categoria)
    piezas.append(formato.euros(movimiento.importe, siempre_visible=True))
    return " · ".join(p for p in piezas if p)


def editar_movimiento(app, movimiento: Movimiento) -> bool:
    """Abre el formulario de edición. Devuelve si se llegó a guardar."""
    libro = app.libro
    nombres_activos = [a.nombre for a in libro.activos]

    campos = [
        dialogos.Fecha("fecha", "Fecha", movimiento.fecha),
        dialogos.Texto("descripcion", "Descripción", movimiento.descripcion),
        dialogos.Opcion("categoria", "Categoría",
                        [c.nombre for c in libro.categorias], movimiento.categoria),
        dialogos.Importe("importe", "Importe", movimiento.importe, permitir_cero=False),
        dialogos.Opcion("activo", "¿A qué activo?", nombres_activos,
                        movimiento.activo, vacio=SIN_ASIGNAR),
    ]

    def al_cambiar(formulario, _evento):
        # La casilla del activo solo tiene sentido si es una aportación.
        formulario.mostrar_campo("activo", es_aportacion(libro, formulario.valor("categoria")))

    resultado = dialogos.Formulario(
        app, "Editar movimiento", campos, aceptar="Guardar cambios",
        al_cambiar=al_cambiar).mostrar()
    if resultado is None:
        return False

    if not es_aportacion(libro, resultado["categoria"]):
        resultado["activo"] = ""

    def aplicar(libro_actual):
        objetivo = libro_actual.movimiento(movimiento.id)
        if objetivo is None:
            raise ValueError("Ese movimiento ya no existe.")
        objetivo.fecha = resultado["fecha"]
        objetivo.descripcion = resultado["descripcion"]
        objetivo.categoria = resultado["categoria"]
        objetivo.importe = abs(resultado["importe"])
        objetivo.activo = resultado["activo"]

    return app.cambiar(aplicar, "Movimiento actualizado.")


def borrar_movimiento(app, movimiento: Movimiento) -> bool:
    if not dialogos.confirmar(app, "¿Borrar este movimiento?",
                              etiqueta_de(app.libro, movimiento) +
                              "\n\nEsto no se puede deshacer."):
        return False

    def aplicar(libro_actual):
        objetivo = libro_actual.movimiento(movimiento.id)
        if objetivo is None:
            raise ValueError("Ese movimiento ya no existe.")
        libro_actual.movimientos.remove(objetivo)

    return app.cambiar(aplicar, "Movimiento borrado.")


def etiqueta_por_tipo(tipo: str) -> str:
    """El color con el que se pinta la fila de la tabla.

    Los gastos van sin color aposta: son la inmensa mayoría de las filas y
    pintarlas todas de rojo no distingue nada, solo cansa. El signo «−» del
    importe ya dice lo que son. Se resaltan los ingresos y las aportaciones,
    que son los que interesa encontrar de un vistazo.
    """
    if tipo == INGRESO:
        return "ingreso"
    if tipo == INVERSION:
        return "inversion"
    return ""


def importe_con_signo(tipo: str, importe: float) -> str:
    """«+ 1.500,00 €» o «− 82,40 €». El signo se ve aunque el ojo tape la
    cifra, y eso está bien: dice el sentido, no la cantidad."""
    marca = "+" if tipo == INGRESO else "−"
    return f"{marca} {formato.euros(importe)}"
