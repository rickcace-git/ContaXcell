"""La guía de uso: «Ayuda ▸ Guía de uso», o F1 desde cualquier pestaña.

Un apartado por pestaña, más uno para empezar y otro para la cuenta. El texto
vive aquí como datos y no dentro de la ventana, para que las pruebas puedan
comprobar que hay un apartado por cada pestaña sin abrir nada.

Formato de cada texto, lo justo para que se lea bien:
    «## Título»   un subtítulo en negrita
    «• algo»      un punto de una lista
    «1. algo»     un paso numerado
    lo demás      un párrafo normal (las líneas en blanco los separan)
"""

from __future__ import annotations

import re
import tkinter as tk
from dataclasses import dataclass
from tkinter import ttk

from . import iconos, widgets


@dataclass(frozen=True)
class Apartado:
    clave: str      # la de la pestaña, para que F1 abra el suyo
    titulo: str
    texto: str


APARTADOS: tuple[Apartado, ...] = (
    Apartado("empezar", "Para empezar", """
ContaXcell lleva la cuenta de tu dinero: lo que entra, lo que sale y lo que tienes invertido. Cada pestaña de arriba es una parte del programa, y aquí tienes una explicación de cada una.

## Lo primero, una sola vez
1. En Ajustes, escribe el saldo inicial: lo que tenías en el banco el día antes del primer movimiento que vayas a apuntar.
2. Revisa las categorías (Comida, Casa, Sueldo…). Cada una es de un tipo: gasto, ingreso o inversión. Crea las que te falten.
3. Si tienes dinero invertido, crea tus activos en Inversiones.

## Después, el día a día
• Apunta lo que gastas y lo que cobras en la pestaña Apuntar.
• Lo que se repite solo cada mes (alquiler, nómina, suscripciones) ponlo una vez en Periódicos y se apuntará solo.
• De vez en cuando, mira el Resumen y el Presupuesto para ver cómo vas.

## Dos ideas que explican casi todos los números
• La inversión no es un gasto. El dinero sale del banco, pero sigue siendo tuyo: baja el saldo, pero no baja tu ahorro.
• Solo el mercado da rentabilidad. Lo que metes tú, o lo que te regalan, no es ganancia. La ganancia es lo que vale hoy menos todo lo que has metido.

## Atajos de teclado
• F1: abre esta guía por el apartado de la pestaña en la que estás.
• Ctrl+1 a Ctrl+8: saltan a cada pestaña, en el orden en que salen arriba.
• Ctrl+H: tapa o destapa todos los importes, por si hay alguien mirando.
"""),

    Apartado("apuntar", "Apuntar", """
Es la pestaña de todos los días: importe, concepto, categoría y listo.

## Apuntar un gasto o un ingreso
1. Pulsa «Gasto» o «Ingreso», arriba del formulario.
2. Escribe el importe. Siempre en positivo: el signo lo pone la categoría.
3. Escribe un concepto corto («Mercadona», «Nómina de mayo»).
4. Elige la categoría.
5. Comprueba la fecha: sale la de hoy, pero se puede cambiar escribiéndola (24/08/2026) o con el calendario de al lado.
6. Pulsa «Guardar» o la tecla Intro.

## Apuntar una aportación a una inversión
Pulsa «Gasto» y elige una categoría de tipo inversión. Aparece una casilla más para decir a qué activo va el dinero. Si todavía no tienes activos, puedes apuntarla igual y asignarla más tarde desde Inversiones.

## Algo que se repite
Si marcas «Se repite» y eliges cada cuánto, además de apuntarlo ahora se creará un pago periódico que se apuntará solo las próximas veces. Para cambiarlo o apagarlo, ve a la pestaña Periódicos.

## A la derecha
• Cómo va el mes: lo que llevas ingresado, gastado e invertido.
• Los últimos movimientos. Doble clic en uno para corregirlo, o elige uno y pulsa «Borrar».
"""),

    Apartado("movimientos", "Movimientos", """
Aquí está todo lo que has apuntado, del más nuevo al más viejo. La columna «Balance» dice cuánto quedaba en el banco después de cada movimiento.

## Buscar
• Escribe en «Buscar» una palabra del concepto.
• Filtra por categoría o por mes con los desplegables.
• «Limpiar» quita todos los filtros.

## Corregir o borrar
• Doble clic en una fila para editarla. También puedes elegirla y pulsar «Editar».
• Para quitar uno, elígelo y pulsa «Borrar». Te pedirá confirmación.

Los ingresos y los gastos van en columnas separadas, como en la hoja de cálculo: por la columna en la que está ya sabes si sumó o restó.
"""),

    Apartado("periodicos", "Periódicos", """
Lo que se repite solo: alquiler, nómina, gimnasio, suscripciones o la aportación de todos los meses a un fondo. Aquí no se apunta dinero: se explica qué se repite y cada cuánto, y el programa lo apunta solo cuando llega el día.

## Crear uno
1. Pulsa «Nuevo».
2. Escribe el nombre (será el concepto de cada movimiento), el importe y la categoría.
3. Elige cada cuánto se repite.
4. En «Primer pago» pon su fecha. De ahí sale el día: si es el 31, vuelve al 31 aunque febrero sea más corto.
5. «Último pago» déjalo en blanco si no se acaba nunca. Si tiene un último pago (las cuotas de un préstamo), pon esa fecha y parará solo.

Si el primer pago ya ha pasado, te preguntará si apunta también los pagos anteriores (útil para rellenar el histórico) o si empieza a contar desde hoy.

## Apagar o borrar
• «Apagar» es lo que hay que hacer al darte de baja de algo: deja de apuntarse, pero lo que ya se pagó se queda. Se puede volver a encender, y no recupera los meses que estuvo apagado.
• «Borrar» quita la regla. Los movimientos que ya apuntó siguen en Movimientos. Si solo quieres que pare, mejor apágalo.

## Arriba
Lo que se te va cada mes en cosas que se pagan solas. Lo que no es mensual se reparte para poder sumarlo: un seguro de 120 € al año cuenta como 10 € al mes. En Movimientos se apunta el día que toca y por su importe entero. La inversión no entra aquí: va en su propia casilla.

## Si tienes cuenta
Al abrir el programa, los periódicos esperan a que se compruebe el servidor antes de apuntarse. Así no se apuntan sobre una copia vieja de tus datos.
"""),

    Apartado("deudas", "Deudas", """
Una libreta para las cuentas con la gente: lo que te deben y lo que debes. No es dinero del banco, así que nada de esto toca tu saldo.

## Apuntar una deuda
1. Pulsa «Nueva».
2. Elige «Me deben» si el dinero te tiene que llegar, o «Debo» si tienes que pagar tú.
3. Escribe quién es. Todo lo que pongas con el mismo nombre se suma en la cuenta con esa persona.
4. Pon de qué es, el importe y desde cuándo.

Con «Nota…» puedes escribir lo que no cabe en las casillas: de qué era, quién más estaba, qué se acordó.

## Cuando alguien paga
1. Elige la deuda y pulsa «Cobrar…» (o «Pagar…» si la debes tú).
2. Escribe cuánto. Se puede devolver a trozos.
3. Marca «Apuntar también el movimiento» solo si ese dinero entra o sale de verdad de tu cuenta.

¿Por qué no se apunta siempre? Si pagaste tú la cena entera, ese gasto ya lo apuntaste. Lo que te devuelven solo lo compensa: apuntarlo como otro movimiento lo contaría dos veces.

## Arriba
La cuenta con cada persona: en positivo lo que te tiene que dar, en negativo lo que le debes tú. Solo cuenta lo que queda pendiente.
"""),

    Apartado("resumen", "Resumen", """
La pantalla para mirar hacia atrás: cómo ha ido un periodo.

## Elegir qué mirar
Arriba a la derecha, en «Ver», elige:
• Un año: los doce meses, uno por uno.
• Varios años: un tramo por cada año.
• Un mes suelto: sus cifras y en qué se fue el dinero.

## Qué sale
• Los indicadores: ingresos, gastos, ahorro, inversión y medias. Las medias son siempre por mes, mires el periodo que mires. Donde veas una interrogación junto a una cifra, púlsala para ver de dónde sale.
• Mes a mes: el gráfico y la tabla de cada tramo.
• En qué se va el dinero y de dónde viene: el reparto por categorías.

Recuerda: el ahorro es lo que ingresas menos lo que gastas. Lo que inviertes no lo resta, porque ese dinero sigue siendo tuyo.
"""),

    Apartado("presupuesto", "Presupuesto", """
Cuánto tenías previsto gastar en cada cosa y cuánto llevas este mes.

## Poner el presupuesto
Escribe directamente en la columna «Presupuesto» de cada categoría. Se guarda solo al salir de la casilla. Es la misma cifra para todos los meses: lo que cambia es lo que gastas.

## Leerlo
• Cada fila tiene una barra con lo que llevas consumido.
• Arriba a la derecha puedes elegir otro mes para ver cómo te fue.
• Abajo, el mes en conjunto: lo presupuestado, lo gastado y lo que queda.

## Inversión
Aparte, puedes poner un objetivo de inversión al mes y ver cuánto llevas. La inversión no cuenta como gasto, así que no se mezcla con el presupuesto.

Solo salen las categorías de gasto. Si no hay ninguna, créalas en Ajustes.
"""),

    Apartado("inversiones", "Inversiones", """
Tu cartera: lo que has metido, lo que vale hoy y lo que ha ganado o perdido el mercado.

## Los activos
Un activo es cada sitio donde tienes dinero invertido: un fondo, una acción, una cuenta remunerada, oro…
1. Pulsa «Añadir activo».
2. Escribe el nombre y, si ya tenías dinero dentro antes de empezar a usar el programa, la aportación inicial.
3. Si sabes cuántas participaciones son esa aportación inicial, escríbelas con todos los decimales que diga el banco. Así el activo se valorará solo en cuanto le pongas su cotización. Si no lo sabes, déjalo en blanco.
4. Pon lo que vale hoy y, si quieres, una categoría para agruparlos (Indexados, Acciones, Cripto…).

## Precios automáticos
Elige un activo y pulsa «Cotización…» para enlazarlo con su fondo o acción en bolsa. Desde entonces el precio se actualiza solo una vez al día. Hace falta tener cuenta, porque los precios los da el servidor.

## Traer las compras del banco
«Importar de Trade Republic» lee el extracto en PDF y apunta las compras con sus participaciones, para que no tengas que hacerlo a mano. Si ya habías apuntado a mano aportaciones de esos mismos meses, te preguntará si las sustituye por las del extracto. Si no, se contarían dos veces.

## Compras
Al elegir un activo, abajo sale cómo va cada compra por separado: lo que pagaste, lo que vale hoy y lo que ha generado. Solo aparecen las compras que traen participaciones (las del extracto y la aportación inicial si pusiste las suyas).

## Histórico y aportaciones gratis
• «Apuntar valoración»: cada cierto tiempo, por ejemplo a fin de mes, apunta lo que vale la cartera entera. Lo aportado hasta esa fecha se calcula solo, y la diferencia es lo que ha hecho el mercado.
• «Aportaciones gratis»: el dinero que entra en la cartera sin salir de tu cuenta, como el cashback. No es ganancia: es dinero aportado, solo que gratis.
"""),

    Apartado("ajustes", "Ajustes", """
Lo que se toca una vez y ya.

## El banco
El saldo inicial: lo que tenías en la cuenta antes del primer movimiento. El saldo de hoy es ese más todo lo ingresado, menos todo lo gastado e invertido.

## Categorías
• «Añadir categoría» crea una nueva. Elige bien el tipo (gasto, ingreso o inversión): el tipo manda, y cambiarlo recalcula todo el histórico de esa categoría.
• «Subir» y «Bajar» cambian el orden en que salen en los desplegables.
• Antes de borrar una categoría con movimientos, piénsalo: esos movimientos se quedan con un nombre que ya no existe y pasan a contar como gasto suelto. Si lo que quieres es juntarla con otra, cámbiale el nombre.

## Aspecto
Tema claro, oscuro o como el sistema. El botón del ojo de la barra de arriba (o Ctrl+H) tapa todos los importes de golpe.

## Tus datos
• «Guardar copia» guarda tu contabilidad entera en un archivo. Sirve para tener una copia de seguridad o para llevarla a otro sitio.
• «Restaurar copia…» vuelve a una copia anterior. Antes guarda la de ahora, por si acaso.
• «Abrir la carpeta» te enseña dónde están tus datos y tus copias.
"""),

    Apartado("cuenta", "Tu cuenta y el móvil", """
Con una cuenta, tu contabilidad se guarda también en tu servidor y la puedes llevar de un ordenador a otro, o al móvil.

## Cómo funciona
• Todo se guarda primero en este ordenador. Luego, si hay conexión, se sube solo.
• Si no hay internet, sigues apuntando igual. Lo pendiente se sube cuando vuelve la conexión.
• Al abrir el programa, se trae lo que hayas cambiado en otro sitio.

## Al crear la cuenta
Al abrir el programa por primera vez, elige «Crear cuenta». Pide usuario, correo electrónico y la contraseña dos veces; el ojo junto a cada una la enseña, para comprobarla. Antes de crearla hay que aceptar las condiciones de uso: pulsa en ellas para leerlas (cuentan qué se guarda, dónde y quién puede verlo). Luego sale una ventanita para el código de invitación que te haya dado quien administra ContaXcell.
Apúntate bien la contraseña: por ahora no hay forma de recuperarla. El correo se guarda para poder hacerlo más adelante.
Es posible que tu cuenta tenga que esperar a que la acepten. Mientras tanto usas el programa igual y todo se guarda en este ordenador; el día que te acepten, se sube solo, sin hacer nada.

## En Ajustes ▸ Tu cuenta
• «Cambiar la contraseña…»: este ordenador sigue dentro, pero en los demás habrá que volver a entrar.
• «Cerrar sesión»: tus datos se quedan en este ordenador.
• «Condiciones de uso»: para volver a leerlas cuando quieras.
• «Entrar de nuevo»: aparece si la sesión ha caducado.

## Si alguna vez hay un conflicto
Si cambiaste lo mismo en dos sitios sin conexión, gana lo de este ordenador y la versión del servidor se guarda como copia en la carpeta de tus datos. No se pierde nada.
"""),
)


def apartado(clave: str) -> Apartado:
    """El apartado de esa pestaña, o el primero si no tiene uno propio."""
    return next((a for a in APARTADOS if a.clave == clave), APARTADOS[0])


_PASO = re.compile(r"^\d+\.\s")


def trozos(texto: str) -> list[tuple[str, str]]:
    """Parte un texto en (tipo, contenido): «titulo», «punto», «paso» o
    «parrafo». Es lo que la ventana pinta, cada uno con su estilo."""
    resultado = []
    for linea in texto.strip().splitlines():
        linea = linea.strip()
        if not linea:
            continue
        if linea.startswith("## "):
            resultado.append(("titulo", linea[3:]))
        elif linea.startswith("• "):
            resultado.append(("punto", linea))
        elif _PASO.match(linea):
            resultado.append(("paso", linea))
        else:
            resultado.append(("parrafo", linea))
    return resultado


class Guia(tk.Toplevel):
    """La ventana de la guía: los apartados a la izquierda, el texto a la
    derecha. No es modal: se puede dejar abierta al lado mientras se usa el
    programa, que es para lo que sirve una guía."""

    def __init__(self, padre, clave: str = "empezar", direccion_app: str | None = None):
        super().__init__(padre)
        # La dirección de descarga de la app del móvil: si la hay, el apartado
        # de la cuenta acaba con su QR. Sin cuenta, no hay servidor del que bajarla.
        self.direccion_app = direccion_app
        self._imagen_qr = None
        self.title("Guía de uso de ContaXcell")
        self.configure(background=widgets.PALETA.fondo)
        self.geometry("860x600")
        self.minsize(640, 420)
        self.transient(padre)

        p, f = widgets.PALETA, widgets.FUENTES

        lado = ttk.Frame(self, style="Tarjeta.TFrame", padding=(10, 14))
        lado.pack(side="left", fill="y")
        tk.Frame(self, background=p.borde, width=1).pack(side="left", fill="y")
        ttk.Label(lado, text="APARTADOS", style="Tarjeta.Suave.TLabel").pack(
            anchor="w", padx=6, pady=(0, 8))
        # Un Treeview sin columnas y no un Listbox: es lo que deja poner un
        # icono delante de cada apartado. Filas algo más altas que en las
        # tablas, que esto es un menú y no una lista de datos.
        estilo = ttk.Style(self)
        estilo.configure("Guia.Treeview", rowheight=int(f.normal.metrics("linespace") * 2.1))
        # Sin el marco que llevan las tablas: aquí sobra.
        estilo.layout("Guia.Treeview", [("Treeview.treearea", {"sticky": "nswe"})])
        self.lista = ttk.Treeview(lado, show="tree", selectmode="browse",
                                  style="Guia.Treeview", height=len(APARTADOS))
        # Dos colores por icono, como en las pestañas: gris, y azul el elegido.
        # Hay que guardarlos: si Python los tira, el icono se queda en blanco.
        tam = round(16 * f.escala)
        # Ancho para el título más largo, más el icono y el margen de la fila.
        largo = max(f.normal.measure(f"  {a.titulo}") for a in APARTADOS)
        self.lista.column("#0", width=largo + tam + round(40 * f.escala))
        self._iconos = {a.clave: (iconos.imagen(self, a.clave, tam, p.suave),
                                  iconos.imagen(self, a.clave, tam, p.acento))
                        for a in APARTADOS}
        for a in APARTADOS:
            self.lista.insert("", "end", iid=a.clave, text=f"  {a.titulo}",
                              image=self._iconos[a.clave][0])
        self.lista.pack(fill="y", expand=True)
        self.lista.bind("<<TreeviewSelect>>", lambda _e: self._al_elegir())
        # Las flechas las lleva la guía, no el Treeview: si no, con la lista
        # enfocada se moverían dos apartados de golpe.
        for widget in (self, self.lista):
            widget.bind("<Up>", lambda _e: self._mover(-1))
            widget.bind("<Down>", lambda _e: self._mover(1))

        derecha = ttk.Frame(self, style="Tarjeta.TFrame")
        derecha.pack(side="left", fill="both", expand=True)
        barra = ttk.Scrollbar(derecha, orient="vertical")
        barra.pack(side="right", fill="y")
        self.texto = tk.Text(
            derecha, wrap="word", font=f.normal, relief="flat", borderwidth=0,
            highlightthickness=0, padx=28, pady=22, spacing1=2, spacing3=4,
            background=p.tarjeta, foreground=p.texto, cursor="arrow",
            yscrollcommand=barra.set)
        self.texto.pack(side="left", fill="both", expand=True)
        barra.configure(command=self.texto.yview)

        self.texto.tag_configure("cabecera", font=f.cifra, foreground=p.texto,
                                 spacing3=10)
        self.texto.tag_configure("titulo", font=f.negrita, foreground=p.acento,
                                 spacing1=14, spacing3=4)
        self.texto.tag_configure("parrafo", spacing3=8)
        self.texto.tag_configure("punto", lmargin1=12, lmargin2=26)
        self.texto.tag_configure("paso", lmargin1=12, lmargin2=28)

        self.bind("<Escape>", lambda _e: self.destroy())

        self.ir_a(clave)
        self._colocar_a_la_derecha(padre)

    def _colocar_a_la_derecha(self, padre) -> None:
        """En la pantalla del programa (sin esto, Windows la ponía donde le
        parecía, a veces en la otra) y pegada a su lado derecho: es para
        leerla mientras se usa el programa, así que cuanto menos tape, mejor.
        De alto, a la altura del programa."""
        self.update_idletasks()
        centro = (padre.winfo_rootx() + padre.winfo_width() // 2,
                  padre.winfo_rooty() + padre.winfo_height() // 2)
        _izquierda, _arriba, derecha, _abajo = widgets.area_de_pantalla(self, *centro)
        x = derecha - self.winfo_width() - 16
        y = padre.winfo_rooty() + (padre.winfo_height() - self.winfo_height()) // 3
        widgets.colocar(self, x, y, referencia=centro)

    def ir_a(self, clave: str) -> None:
        clave = apartado(clave).clave
        self.lista.selection_set(clave)
        self.lista.focus(clave)
        self.lista.see(clave)
        self._pintar(apartado(clave))

    def _al_elegir(self) -> None:
        elegido = self.lista.selection()
        if elegido:
            self._pintar(apartado(elegido[0]))

    def _mover(self, paso: int) -> str:
        indice = APARTADOS.index(self.apartado_actual) + paso
        if 0 <= indice < len(APARTADOS):
            self.ir_a(APARTADOS[indice].clave)
        return "break"

    def _pintar(self, a: Apartado) -> None:
        self.apartado_actual = a
        for clave, (normal, elegido) in self._iconos.items():
            self.lista.item(clave, image=elegido if clave == a.clave else normal)
        self.texto.configure(state="normal")
        self.texto.delete("1.0", "end")
        self.texto.insert("end", a.titulo + "\n", "cabecera")
        for tipo, contenido in trozos(a.texto):
            self.texto.insert("end", contenido + "\n", tipo)
        if a.clave == "cuenta" and self.direccion_app:
            self._pintar_qr()
        # Solo lectura: que no se pueda escribir encima de la guía.
        self.texto.configure(state="disabled")
        self.texto.yview_moveto(0)

    def _pintar_qr(self) -> None:
        if self._imagen_qr is None:
            self._imagen_qr = widgets.imagen_qr(self, self.direccion_app)
        self.texto.insert("end", "Descarga la app del móvil\n", "titulo")
        self.texto.insert("end", "Escanea el código con la cámara del móvil. Al abrir "
                                 "el archivo, el móvil pedirá permiso para instalar "
                                 "apps de fuera de la tienda: es normal.\n", "parrafo")
        self.texto.image_create("end", image=self._imagen_qr)
        self.texto.insert("end", "\n" + self.direccion_app + "\n", "parrafo")

    def mostrar(self) -> None:
        self.update_idletasks()
        self.lift()
        self.focus_set()
