"""La puerta de entrada: pedir usuario y contraseña antes de abrir la ventana.

Solo hace falta pasar por aquí una vez por ordenador. Después el token se
queda guardado en la sesión y la aplicación abre directa, con o sin internet;
la cuenta solo vuelve a pedirse si se cierra sesión o si el token caduca (y
aun entonces se puede seguir sin conexión).
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from . import tema, widgets
from .sincronia import ErrorDeSincronia, FaltaCodigo, Sincronia

# Lo que puede devolver la ventana.
DENTRO = "dentro"
SIN_CONEXION = "sin-conexion"
CANCELADO = ""

AVISO_TEXTO_CLARO = "Ojo: sin https la contraseña viaja en claro por la red."
# Direcciones que son este mismo ordenador: ahí no hay red por la que espiar.
MAQUINAS_DE_CASA = ("localhost", "127.0.0.1", "::1")


class VentanaAcceso(tk.Toplevel):
    """Un formulario pequeño: usuario, contraseña y, plegada, la dirección
    del servidor. `mostrar()` devuelve DENTRO, SIN_CONEXION o CANCELADO."""

    def __init__(self, padre, sincronia: Sincronia, permitir_sin_conexion: bool):
        super().__init__(padre)
        self.sincronia = sincronia
        self.resultado = CANCELADO

        self.title("ContaXcell — Tu cuenta")
        self.resizable(False, False)
        self.configure(background=widgets.PALETA.tarjeta)

        cuerpo = ttk.Frame(self, style="Tarjeta.TFrame", padding=22)
        cuerpo.pack(fill="both", expand=True)
        ttk.Label(cuerpo, text="Tu cuenta de ContaXcell",
                  style="Tarjeta.Negrita.TLabel").pack(anchor="w")
        ttk.Label(cuerpo, style="Tarjeta.Suave.TLabel", wraplength=340, justify="left",
                  text="Con una cuenta, tu contabilidad se guarda también en el "
                       "servidor y puedes seguirla desde otro ordenador. Solo se "
                       "pide una vez: después la aplicación abre directa, haya "
                       "internet o no.").pack(anchor="w", pady=(4, 10))

        zona = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
        zona.pack(fill="x")

        widgets.etiqueta_campo(zona, "Usuario")
        self.var_usuario = tk.StringVar(value=sincronia.sesion["usuario"])
        campo_usuario = ttk.Entry(zona, textvariable=self.var_usuario, width=34)
        campo_usuario.pack(fill="x")

        widgets.etiqueta_campo(zona, "Contraseña")
        self.var_contrasena = tk.StringVar()
        ttk.Entry(zona, textvariable=self.var_contrasena, width=34,
                  show="•").pack(fill="x")

        # El código de invitación no lo piden todos los servidores, así que se
        # queda escondido hasta que el servidor lo reclame. El hueco vacío no
        # se ve y guarda el sitio, para que al aparecer salga donde toca.
        hueco_codigo = ttk.Frame(zona, style="Tarjeta.TFrame")
        hueco_codigo.pack(fill="x")
        self.bloque_codigo = ttk.Frame(hueco_codigo, style="Tarjeta.TFrame")
        widgets.etiqueta_campo(self.bloque_codigo, "Código de invitación")
        self.var_codigo = tk.StringVar()
        self.campo_codigo = ttk.Entry(self.bloque_codigo, textvariable=self.var_codigo,
                                      width=34)
        self.campo_codigo.pack(fill="x")

        # El servidor va escondido tras un enlace: casi nadie lo cambia.
        self.enlace_servidor = ttk.Button(zona, text="Cambiar el servidor…",
                                          style="Enlace.TButton",
                                          command=self._ensenar_servidor)
        self.enlace_servidor.pack(anchor="w", pady=(8, 0))
        self.bloque_servidor = ttk.Frame(zona, style="Tarjeta.TFrame")
        widgets.etiqueta_campo(self.bloque_servidor, "Dirección del servidor")
        self.var_servidor = tk.StringVar(value=sincronia.sesion["servidor"])
        ttk.Entry(self.bloque_servidor, textvariable=self.var_servidor,
                  width=34).pack(fill="x")

        # Aviso, no error: si el servidor va por http y no es este mismo
        # ordenador, la contraseña cruza la red a la vista de cualquiera. Se
        # queda puesto mientras la dirección lo merezca, no unos segundos.
        self.aviso = ttk.Label(cuerpo, text="", style="Tarjeta.Aviso.TLabel",
                               wraplength=340, justify="left")
        self._aviso_puesto = False

        self.error = ttk.Label(cuerpo, text="", style="Tarjeta.Gasto.TLabel",
                               wraplength=340, justify="left")
        self.error.pack(anchor="w", pady=(8, 0))

        self.var_servidor.trace_add("write", lambda *_a: self._revisar_cifrado())
        self._revisar_cifrado()

        pie = ttk.Frame(cuerpo, style="Tarjeta.TFrame")
        pie.pack(fill="x", pady=(12, 0))
        self.boton_entrar = ttk.Button(pie, text="Entrar", style="Principal.TButton",
                                       command=lambda: self._enviar(registro=False))
        self.boton_entrar.pack(side="left")
        self.boton_crear = ttk.Button(pie, text="Crear cuenta",
                                      command=lambda: self._enviar(registro=True))
        self.boton_crear.pack(side="left", padx=(8, 0))
        if permitir_sin_conexion:
            # Solo tiene sentido si ya se entró alguna vez: la primera vez no
            # hay cuenta a la que atribuir los datos.
            ttk.Button(pie, text="Seguir sin conexión", style="Enlace.TButton",
                       command=self._sin_conexion).pack(side="right")

        self.bind("<Return>", lambda _e: self._enviar(registro=False))
        self.bind("<Escape>", lambda _e: self._cerrar())
        self.protocol("WM_DELETE_WINDOW", self._cerrar)
        campo_usuario.focus_set()

    def _ensenar_servidor(self) -> None:
        self.enlace_servidor.pack_forget()
        self.bloque_servidor.pack(fill="x")

    def _ensenar_codigo(self) -> None:
        """El servidor pide invitación: se saca el campo y se pone el cursor
        dentro, que es lo único que falta para poder seguir."""
        if not self.bloque_codigo.winfo_ismapped():
            self.bloque_codigo.pack(fill="x")
        self.campo_codigo.focus_set()

    def _revisar_cifrado(self) -> None:
        """Pone o quita el aviso según la dirección que haya escrita. Nunca
        impide entrar: es un aviso, no un candado.

        Si está puesto o no se lleva a mano y no se le pregunta a tkinter:
        mientras se construye la ventana, `winfo_ismapped` contesta que no
        a todo.
        """
        texto = aviso_de_texto_claro(self.var_servidor.get())
        self.aviso.configure(text=texto)
        if texto and not self._aviso_puesto:
            self.aviso.pack(anchor="w", pady=(8, 0), before=self.error)
            self._aviso_puesto = True
        elif not texto and self._aviso_puesto:
            self.aviso.pack_forget()
            self._aviso_puesto = False

    def _enviar(self, registro: bool) -> None:
        self.error.configure(text="Hablando con el servidor…")
        self.update_idletasks()
        try:
            if registro:
                # El código solo pinta algo al crear la cuenta.
                self.sincronia.registrar(self.var_usuario.get(),
                                         self.var_contrasena.get(),
                                         self.var_servidor.get(),
                                         self.var_codigo.get())
            else:
                self.sincronia.entrar(self.var_usuario.get(),
                                      self.var_contrasena.get(),
                                      self.var_servidor.get())
        except FaltaCodigo as error:
            self._ensenar_codigo()
            self.error.configure(text=str(error))
            self.bell()
            return
        except ErrorDeSincronia as error:
            self.error.configure(text=str(error))
            self.bell()
            return
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
        ancho, alto = self.winfo_width(), self.winfo_height()
        padre = self.master
        if padre is not None and padre.winfo_viewable():
            x = padre.winfo_rootx() + (padre.winfo_width() - ancho) // 2
            y = padre.winfo_rooty() + (padre.winfo_height() - alto) // 3
        else:
            x = (self.winfo_screenwidth() - ancho) // 2
            y = (self.winfo_screenheight() - alto) // 3
        self.geometry(f"+{max(0, x)}+{max(0, y)}")


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
