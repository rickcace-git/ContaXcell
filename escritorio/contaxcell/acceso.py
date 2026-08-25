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
from .sincronia import ErrorDeSincronia, Sincronia

# Lo que puede devolver la ventana.
DENTRO = "dentro"
SIN_CONEXION = "sin-conexion"
CANCELADO = ""


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

        self.error = ttk.Label(cuerpo, text="", style="Tarjeta.Gasto.TLabel",
                               wraplength=340, justify="left")
        self.error.pack(anchor="w", pady=(8, 0))

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

    def _enviar(self, registro: bool) -> None:
        self.error.configure(text="Hablando con el servidor…")
        self.update_idletasks()
        try:
            if registro:
                self.sincronia.registrar(self.var_usuario.get(),
                                         self.var_contrasena.get(),
                                         self.var_servidor.get())
            else:
                self.sincronia.entrar(self.var_usuario.get(),
                                      self.var_contrasena.get(),
                                      self.var_servidor.get())
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
