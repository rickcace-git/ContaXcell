"""La puerta de entrada: pedir usuario y contraseña antes de abrir la ventana.

Solo hace falta pasar por aquí una vez por ordenador. Después el token se
queda guardado en la sesión y la aplicación abre directa, con o sin internet;
la cuenta solo vuelve a pedirse si se cierra sesión o si el token caduca (y
aun entonces se puede seguir sin conexión).

Son tres pantallas en la misma ventana: la de inicio, que solo pregunta qué
quieres hacer, la de iniciar sesión y la de crear cuenta. Crear cuenta pide
además el correo y la contraseña dos veces, y el código de invitación va
después, en una ventanita aparte: es lo último que falta, y así no se
confunde con los datos de la cuenta.
"""

from __future__ import annotations

import tkinter as tk
import unicodedata
from tkinter import ttk

from . import dialogos, iconos, tema, widgets
from .sincronia import MENSAJE_EN_ESPERA, ErrorDeSincronia, FaltaCodigo, Sincronia

# Lo que puede devolver la ventana.
DENTRO = "dentro"
SIN_CONEXION = "sin-conexion"
CANCELADO = ""

AVISO_TEXTO_CLARO = "Ojo: sin https la contraseña viaja en claro por la red."
# Direcciones que son este mismo ordenador: ahí no hay red por la que espiar.
MAQUINAS_DE_CASA = ("localhost", "127.0.0.1", "::1")

# Las mismas medidas que pone el servidor (server/contaserver/aplicacion.py).
# Se miran aquí antes de mandar nada para decirlo al momento y en su sitio.
USUARIO_MINIMO, USUARIO_MAXIMO = 3, 30
CONTRASENA_MINIMA, CONTRASENA_MAXIMA = 8, 128
CORREO_MAXIMO = 254

ANCHO_TEXTO = 340


def correo_valido(correo: str) -> bool:
    """Que tenga pinta de correo: algo, una arroba y un dominio con punto.
    Que exista de verdad no se sabe hasta que se le escribe."""
    correo = correo.strip()
    usuario, arroba, dominio = correo.partition("@")
    return (bool(arroba) and bool(usuario) and "." in dominio and "@" not in dominio
            and not dominio.startswith(".") and not dominio.endswith(".")
            and len(correo) <= CORREO_MAXIMO
            and not any(c.isspace() or unicodedata.category(c).startswith("C")
                        for c in correo))


def fallo_cuenta_nueva(usuario: str, correo: str, contrasena: str, repetida: str) -> str:
    """Lo primero que no cuadra al crear la cuenta, o cadena vacía si todo va
    bien. Va en el orden de los campos, para que el aviso señale el de arriba."""
    usuario = usuario.strip()
    if not USUARIO_MINIMO <= len(usuario) <= USUARIO_MAXIMO:
        return (f"El usuario tiene que tener entre {USUARIO_MINIMO} y "
                f"{USUARIO_MAXIMO} caracteres.")
    if not correo.strip():
        return "Falta el correo electrónico."
    if not correo_valido(correo):
        return "El correo no parece válido. Revisa que esté bien escrito."
    if len(contrasena) < CONTRASENA_MINIMA:
        return f"La contraseña tiene que tener al menos {CONTRASENA_MINIMA} caracteres."
    if len(contrasena) > CONTRASENA_MAXIMA:
        return f"La contraseña no puede pasar de {CONTRASENA_MAXIMA} caracteres."
    if contrasena != repetida:
        return "Las dos contraseñas no son iguales."
    return ""


class VentanaAcceso(tk.Toplevel):
    """Inicio, iniciar sesión y crear cuenta, en una sola ventana.
    `mostrar()` devuelve DENTRO, SIN_CONEXION o CANCELADO.

    Si ya hubo sesión en este ordenador (la que ha caducado, por ejemplo),
    se empieza directamente en «Iniciar sesión»: preguntar otra vez qué se
    quiere hacer sería un paso de más."""

    def __init__(self, padre, sincronia: Sincronia, permitir_sin_conexion: bool):
        super().__init__(padre)
        self.sincronia = sincronia
        self.resultado = CANCELADO
        self.permitir_sin_conexion = permitir_sin_conexion

        self.title("ContaXcell — Tu cuenta")
        self.resizable(False, False)
        self.configure(background=widgets.PALETA.tarjeta)

        # Hay que guardar las imágenes: si Python las tira, el botón queda vacío.
        self._ojos = {visible: iconos.imagen(self, "ojo_tachado" if visible else "ojo",
                                             18, widgets.PALETA.suave)
                      for visible in (False, True)}

        self.cuerpo = ttk.Frame(self, style="Tarjeta.TFrame", padding=22)
        self.cuerpo.pack(fill="both", expand=True)

        # Lo que comparten las dos pantallas de formulario: el servidor y el
        # aviso de https. Se escriben una vez y se pasan de una a otra.
        self.var_servidor = tk.StringVar(value=sincronia.sesion["servidor"])
        self.var_usuario = tk.StringVar(value=sincronia.sesion["usuario"])

        self.pantallas = {
            "inicio": self._pantalla_inicio(),
            "entrar": self._pantalla_entrar(),
            "crear": self._pantalla_crear(),
        }
        self.var_servidor.trace_add("write", lambda *_a: self._revisar_cifrado())

        self.bind("<Escape>", lambda _e: self._cerrar())
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        self.ir_a("entrar" if sincronia.hay_sesion() else "inicio")

    # --- las pantallas ----------------------------------------------------------

    def _pantalla_inicio(self) -> ttk.Frame:
        marco = ttk.Frame(self.cuerpo, style="Tarjeta.TFrame")
        ttk.Label(marco, text="Tu cuenta de ContaXcell",
                  style="Tarjeta.Negrita.TLabel").pack(anchor="w")
        ttk.Label(marco, style="Tarjeta.Suave.TLabel", wraplength=ANCHO_TEXTO,
                  justify="left",
                  text="Con una cuenta, tu contabilidad se guarda también en el "
                       "servidor y puedes seguirla desde otro ordenador o desde "
                       "el móvil. Solo se pide una vez: después la aplicación "
                       "abre directa, haya internet o no.").pack(anchor="w", pady=(4, 16))
        ttk.Button(marco, text="Iniciar sesión", style="Principal.TButton",
                   command=lambda: self.ir_a("entrar")).pack(fill="x")
        ttk.Label(marco, text="Ya tengo cuenta", style="Tarjeta.Suave.TLabel").pack(
            anchor="w", pady=(2, 12))
        ttk.Button(marco, text="Crear cuenta",
                   command=lambda: self.ir_a("crear")).pack(fill="x")
        ttk.Label(marco, text="Es la primera vez", style="Tarjeta.Suave.TLabel").pack(
            anchor="w", pady=(2, 0))
        if self.permitir_sin_conexion:
            # Solo tiene sentido si ya se entró alguna vez: la primera vez no
            # hay cuenta a la que atribuir los datos.
            ttk.Button(marco, text="Seguir sin conexión", style="Enlace.TButton",
                       command=self._sin_conexion).pack(anchor="e", pady=(12, 0))
        return marco

    def _pantalla_entrar(self) -> ttk.Frame:
        marco = ttk.Frame(self.cuerpo, style="Tarjeta.TFrame")
        ttk.Label(marco, text="Iniciar sesión", style="Tarjeta.Negrita.TLabel").pack(anchor="w")
        zona = ttk.Frame(marco, style="Tarjeta.TFrame")
        zona.pack(fill="x", pady=(6, 0))
        widgets.etiqueta_campo(zona, "Usuario")
        self.campo_usuario_entrar = ttk.Entry(zona, textvariable=self.var_usuario, width=34)
        self.campo_usuario_entrar.pack(fill="x")
        widgets.etiqueta_campo(zona, "Contraseña")
        self.var_contrasena = tk.StringVar()
        self.campo_contrasena = self._campo_contrasena(zona, self.var_contrasena)
        self._bloque_servidor(marco, "entrar")
        self.error_entrar = self._linea_error(marco)

        pie = ttk.Frame(marco, style="Tarjeta.TFrame")
        pie.pack(fill="x", pady=(12, 0))
        self.boton_entrar = ttk.Button(pie, text="Entrar", style="Principal.TButton",
                                       command=self._entrar)
        self.boton_entrar.pack(side="left")
        self.boton_volver_entrar = ttk.Button(pie, text="Volver",
                                              command=lambda: self.ir_a("inicio"))
        self.boton_volver_entrar.pack(side="left", padx=(8, 0))
        return marco

    def _pantalla_crear(self) -> ttk.Frame:
        marco = ttk.Frame(self.cuerpo, style="Tarjeta.TFrame")
        ttk.Label(marco, text="Crear cuenta", style="Tarjeta.Negrita.TLabel").pack(anchor="w")
        zona = ttk.Frame(marco, style="Tarjeta.TFrame")
        zona.pack(fill="x", pady=(6, 0))
        widgets.etiqueta_campo(zona, "Usuario")
        self.var_usuario_nuevo = tk.StringVar()
        self.campo_usuario_crear = ttk.Entry(zona, textvariable=self.var_usuario_nuevo, width=34)
        self.campo_usuario_crear.pack(fill="x")
        widgets.etiqueta_campo(zona, "Correo electrónico")
        self.var_correo = tk.StringVar()
        ttk.Entry(zona, textvariable=self.var_correo, width=34).pack(fill="x")
        ttk.Label(zona, style="Tarjeta.Suave.TLabel", wraplength=ANCHO_TEXTO, justify="left",
                  text="Por si algún día hay que restablecer la contraseña.").pack(anchor="w")
        widgets.etiqueta_campo(zona, "Contraseña")
        self.var_contrasena_nueva = tk.StringVar()
        self.campo_contrasena_nueva = self._campo_contrasena(zona, self.var_contrasena_nueva)
        widgets.etiqueta_campo(zona, "Repite la contraseña")
        self.var_repetida = tk.StringVar()
        self.campo_repetida = self._campo_contrasena(zona, self.var_repetida)
        # Las condiciones de uso: hay que marcarlas para crear la cuenta, y
        # se pueden leer ahí mismo (las da el servidor).
        fila = ttk.Frame(zona, style="Tarjeta.TFrame")
        fila.pack(anchor="w", pady=(10, 0))
        self.var_acepta = tk.BooleanVar(value=False)
        ttk.Checkbutton(fila, text="He leído y acepto las", variable=self.var_acepta).pack(
            side="left")
        ttk.Button(fila, text="condiciones de uso", style="Enlace.TButton", cursor="hand2",
                   command=self.leer_condiciones).pack(side="left")
        self._bloque_servidor(marco, "crear")
        self.error_crear = self._linea_error(marco)

        pie = ttk.Frame(marco, style="Tarjeta.TFrame")
        pie.pack(fill="x", pady=(12, 0))
        ttk.Button(pie, text="Crear cuenta", style="Principal.TButton",
                   command=self._crear).pack(side="left")
        ttk.Button(pie, text="Volver", command=lambda: self.ir_a("inicio")).pack(
            side="left", padx=(8, 0))
        return marco

    # --- piezas que se repiten -------------------------------------------------------

    def _campo_contrasena(self, padre, variable: tk.StringVar) -> ttk.Entry:
        """Una casilla de contraseña con su ojo al lado, para comprobar lo
        escrito: una letra de más al crear la cuenta obliga luego a pedir ayuda."""
        fila = ttk.Frame(padre, style="Tarjeta.TFrame")
        fila.pack(fill="x")
        campo = ttk.Entry(fila, textvariable=variable, width=34, show="•")
        campo.pack(side="left", fill="x", expand=True)
        ojo = ttk.Button(fila, image=self._ojos[False], style="Enlace.TButton",
                         cursor="hand2")
        ojo.configure(command=lambda: self._alternar(campo, ojo))
        ojo.pack(side="left", padx=(4, 0))
        campo.ojo = ojo
        return campo

    def _alternar(self, campo: ttk.Entry, ojo: ttk.Button) -> None:
        visible = not self.visible(campo)
        campo.configure(show="" if visible else "•")
        ojo.configure(image=self._ojos[visible])

    @staticmethod
    def visible(campo: ttk.Entry) -> bool:
        return not campo.cget("show")

    def _bloque_servidor(self, padre, pantalla: str) -> None:
        """El servidor va escondido tras un enlace: casi nadie lo cambia. Y el
        aviso de https, que se queda puesto mientras la dirección lo merezca."""
        enlace = ttk.Button(padre, text="Cambiar el servidor…", style="Enlace.TButton")
        enlace.pack(anchor="w", pady=(8, 0))
        bloque = ttk.Frame(padre, style="Tarjeta.TFrame")
        widgets.etiqueta_campo(bloque, "Dirección del servidor")
        ttk.Entry(bloque, textvariable=self.var_servidor, width=34).pack(fill="x")

        def ensenar():
            # Donde estaba el enlace: justo antes de la línea de errores.
            enlace.pack_forget()
            bloque.pack(fill="x", before=getattr(self, f"error_{pantalla}"))
        enlace.configure(command=ensenar)

        # El aviso no se coloca hasta que haga falta: vacío dejaría un hueco.
        aviso = ttk.Label(padre, text="", style="Tarjeta.Aviso.TLabel",
                          wraplength=ANCHO_TEXTO, justify="left")
        aviso.puesto = False
        setattr(self, f"aviso_{pantalla}", aviso)

    def _linea_error(self, padre) -> ttk.Label:
        error = ttk.Label(padre, text="", style="Tarjeta.Gasto.TLabel",
                          wraplength=ANCHO_TEXTO, justify="left")
        error.pack(anchor="w", pady=(8, 0))
        return error

    # --- moverse entre pantallas ----------------------------------------------------

    def ir_a(self, nombre: str) -> None:
        for marco in self.pantallas.values():
            marco.pack_forget()
        self.pantallas[nombre].pack(fill="both", expand=True)
        self.pantalla = nombre
        self._revisar_cifrado()
        # Intro hace lo de la pantalla en la que se está.
        accion = {"entrar": self._entrar, "crear": self._crear}.get(nombre)
        if accion is None:
            self.unbind("<Return>")
        else:
            self.bind("<Return>", lambda _e: accion())
        foco = {"entrar": (self.campo_contrasena if self.var_usuario.get()
                           else self.campo_usuario_entrar),
                "crear": self.campo_usuario_crear}.get(nombre)
        if foco is not None:
            foco.focus_set()
        if self.winfo_ismapped():
            self.update_idletasks()
            self._centrar()

    def _revisar_cifrado(self) -> None:
        """Pone o quita el aviso según la dirección que haya escrita. Nunca
        impide entrar: es un aviso, no un candado.

        Si está puesto o no se lleva a mano y no se le pregunta a tkinter:
        mientras se construye la ventana, `winfo_ismapped` contesta que no
        a todo."""
        texto = aviso_de_texto_claro(self.var_servidor.get())
        for nombre in ("entrar", "crear"):
            aviso = getattr(self, f"aviso_{nombre}")
            aviso.configure(text=texto)
            if texto and not aviso.puesto:
                aviso.pack(anchor="w", pady=(8, 0), before=getattr(self, f"error_{nombre}"))
            elif not texto and aviso.puesto:
                aviso.pack_forget()
            aviso.puesto = bool(texto)

    # --- lo que hacen los botones -----------------------------------------------------

    def _entrar(self) -> None:
        self.error_entrar.configure(text="Hablando con el servidor…")
        self.update_idletasks()
        try:
            self.sincronia.entrar(self.var_usuario.get(), self.var_contrasena.get(),
                                  self.var_servidor.get())
        except ErrorDeSincronia as error:
            self.error_entrar.configure(text=str(error))
            self.bell()
            return
        self._dentro()

    def _crear(self) -> None:
        fallo = fallo_cuenta_nueva(self.var_usuario_nuevo.get(), self.var_correo.get(),
                                   self.var_contrasena_nueva.get(), self.var_repetida.get())
        if fallo:
            self.error_crear.configure(text=fallo)
            self.bell()
            return
        if not self.var_acepta.get():
            self.error_crear.configure(
                text="Para crear la cuenta tienes que aceptar las condiciones de uso. "
                     "Puedes leerlas pulsando en ellas.")
            self.bell()
            return
        # Se piden otra vez justo ahora: lo que se acepta es lo vigente.
        self.error_crear.configure(text="Hablando con el servidor…")
        self.update_idletasks()
        try:
            condiciones = self.sincronia.condiciones(self.var_servidor.get())
        except ErrorDeSincronia as error:
            self.error_crear.configure(text=str(error))
            self.bell()
            return
        self.error_crear.configure(text="")
        codigo = PedirCodigo(self).mostrar()
        if codigo is None:
            return  # ha cancelado: se queda en el formulario con todo escrito
        self.error_crear.configure(text="Hablando con el servidor…")
        self.update_idletasks()
        try:
            self.sincronia.registrar(self.var_usuario_nuevo.get(),
                                     self.var_contrasena_nueva.get(),
                                     self.var_servidor.get(), codigo,
                                     correo=self.var_correo.get(),
                                     condiciones=condiciones[0] if condiciones else "")
        except FaltaCodigo as error:
            self.error_crear.configure(
                text=f"{error}\nPulsa «Crear cuenta» otra vez para escribirlo.")
            self.bell()
            return
        except ErrorDeSincronia as error:
            self.error_crear.configure(text=str(error))
            self.bell()
            return
        self._dentro()

    def leer_condiciones(self) -> None:
        self.error_crear.configure(text="Pidiendo las condiciones al servidor…")
        self.update_idletasks()
        try:
            condiciones = self.sincronia.condiciones(self.var_servidor.get())
        except ErrorDeSincronia as error:
            self.error_crear.configure(text=str(error))
            self.bell()
            return
        self.error_crear.configure(text="")
        if condiciones is None:
            self.error_crear.configure(text="Este servidor no tiene condiciones de uso.")
            return
        dialogos.Lectura(self, "Condiciones de uso", condiciones[1]).mostrar()

    def _dentro(self) -> None:
        if self.sincronia.en_espera:
            # Ha entrado, pero el servidor no le guardará nada hasta que lo
            # acepten: mejor saberlo ahora que creer que ya está sincronizado.
            dialogos.avisar(self, "Cuenta creada. Falta que te acepten.",
                            MENSAJE_EN_ESPERA)
        self.resultado = DENTRO
        self.destroy()

    def _sin_conexion(self) -> None:
        self.resultado = SIN_CONEXION
        self.destroy()

    def _cerrar(self) -> None:
        self.resultado = CANCELADO
        self.destroy()

    def mostrar(self) -> str:
        self.update_idletasks()
        self._centrar()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.wait_window()
        return self.resultado

    def _centrar(self) -> None:
        _centrar_sobre(self, self.master)


class PedirCodigo(tk.Toplevel):
    """La ventanita del código de invitación, después de rellenar la cuenta.
    `mostrar()` devuelve el código (puede ir vacío) o None si se cancela."""

    def __init__(self, padre):
        super().__init__(padre)
        self.resultado = None
        self.title("Código de invitación")
        self.resizable(False, False)
        self.transient(padre)
        self.configure(background=widgets.PALETA.tarjeta)

        cuerpo = ttk.Frame(self, style="Tarjeta.TFrame", padding=22)
        cuerpo.pack(fill="both", expand=True)
        ttk.Label(cuerpo, text="Código de invitación",
                  style="Tarjeta.Negrita.TLabel").pack(anchor="w")
        ttk.Label(cuerpo, style="Tarjeta.Suave.TLabel", wraplength=300, justify="left",
                  text="Te lo da quien administra ContaXcell. Sin él, el servidor "
                       "no deja crear cuentas.").pack(anchor="w", pady=(4, 10))
        self.var_codigo = tk.StringVar()
        self.campo = ttk.Entry(cuerpo, textvariable=self.var_codigo, width=30)
        self.campo.pack(fill="x")
        pie = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
        pie.pack(fill="x", pady=(14, 0))
        ttk.Button(pie, text="Crear la cuenta", style="Principal.TButton",
                   command=self._aceptar).pack(side="left")
        ttk.Button(pie, text="Cancelar", command=self.destroy).pack(side="left", padx=(8, 0))
        self.bind("<Return>", lambda _e: self._aceptar())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _aceptar(self) -> None:
        self.resultado = self.var_codigo.get().strip()
        self.destroy()

    def mostrar(self) -> str | None:
        self.update_idletasks()
        _centrar_sobre(self, self.master)
        self.campo.focus_set()
        try:
            self.grab_set()
        except tk.TclError:
            pass
        self.wait_window()
        # Al cerrarse, la ventana de la cuenta vuelve a llevar el mando.
        try:
            self.master.grab_set()
        except tk.TclError:
            pass
        return self.resultado


def _centrar_sobre(ventana: tk.Toplevel, padre) -> None:
    if padre is not None and padre.winfo_viewable():
        # Sobre la ventana de detrás, en su pantalla (no siempre la principal).
        widgets.centrar_sobre(ventana, padre)
        return
    # Al arrancar no hay nada detrás: en medio de la pantalla principal.
    ancho, alto = ventana.winfo_width(), ventana.winfo_height()
    x = (ventana.winfo_screenwidth() - ancho) // 2
    y = (ventana.winfo_screenheight() - alto) // 3
    ventana.geometry(f"+{max(0, x)}+{max(0, y)}")


def aviso_de_texto_claro(direccion: str) -> str:
    """El aviso que toca para esa dirección, o cadena vacía si no hace falta.

    Con `http://` la contraseña sale del ordenador legible, así que conviene
    decirlo. Salvo cuando el servidor es este mismo ordenador: ahí no hay red
    de por medio y avisar solo daría miedo para nada.
    """
    direccion = direccion.strip().lower()
    if not direccion.startswith("http://"):
        return ""
    maquina = direccion[len("http://"):].split("/")[0].split("@")[-1]
    if maquina.startswith("["):  # IPv6, que lleva el puerto fuera de corchetes
        maquina = maquina[1:].split("]")[0]
    else:
        maquina = maquina.split(":")[0]
    if maquina in MAQUINAS_DE_CASA or maquina.startswith("127."):
        return ""
    return AVISO_TEXTO_CLARO


def pedir_cuenta(sincronia: Sincronia, padre: tk.Misc | None = None) -> str:
    """Enseña la ventana de la cuenta y espera a que el usuario decida.

    Antes de arrancar todavía no existe la ventana principal, así que en ese
    caso se monta una raíz invisible solo para sostener el diálogo.
    """
    raiz = None
    if padre is None:
        raiz = tk.Tk()
        raiz.withdraw()
        fuentes = tema.Fuentes(1.0)
        paleta = tema.paleta_para("auto")
        tema.aplicar(raiz, paleta, fuentes)
        widgets.usar(paleta, fuentes)
        padre = raiz

    resultado = VentanaAcceso(padre, sincronia,
                              permitir_sin_conexion=sincronia.hay_sesion()).mostrar()
    if raiz is not None:
        raiz.destroy()
    return resultado
