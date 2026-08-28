"""Hablar con el servidor de cuentas para tener los datos en más de un sitio.

La aplicación funciona igual con o sin internet: todo se guarda primero en el
disco, como siempre, y este módulo se encarga después de subirlo cuando haya
conexión. Si no la hay, se apunta que queda algo pendiente (y se apunta en un
archivo, para que sobreviva a cerrar la aplicación) y se reintenta solo.

Aquí no hay nada de interfaz gráfica a propósito: el hilo de fondo no puede
tocar la ventana, así que lo que tenga que ver el usuario se deja en una cola
de avisos que la ventana vacía desde el hilo principal. Por eso mismo se puede
probar entero sin abrir una pantalla.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from .almacen import CARPETA_COPIAS, NOMBRE_ARCHIVO

ARCHIVO_SESION = "sesion.json"
SERVIDOR_POR_DEFECTO = "http://localhost:8000"
SEGUNDOS_DE_ESPERA = 10
SEGUNDOS_ENTRE_REINTENTOS = 30
# Cada cuánto se vuelve a mirar qué hay en el servidor. Sin esto, el segundo
# ordenador no se enteraría de nada hasta la próxima vez que se abriera.
SEGUNDOS_ENTRE_DESCARGAS = 120
# Si el servidor cambia mientras subimos, se reintenta con su revisión nueva.
# Con un tope, por si dos aparatos se empeñan en escribir a la vez sin parar.
INTENTOS_POR_CONFLICTO = 3

MENSAJE_SIN_CONEXION = "Sin conexión: se subirá cuando vuelva internet."
MENSAJE_CADUCADA = ("La sesión ha caducado. Entra de nuevo desde Ajustes; "
                    "mientras tanto todo sigue funcionando sin conexión.")
MENSAJE_DEMASIADOS_INTENTOS = ("Demasiados intentos seguidos. El servidor ha "
                               "pedido esperar un rato antes de volver a probar.")
MENSAJE_FALTA_CODIGO = ("Este servidor solo deja crear cuentas con un código de "
                        "invitación. Pídeselo a quien lo administra y escríbelo "
                        "abajo.")
# Lo del conflicto se le cuenta al usuario con el nombre del archivo dentro,
# porque es lo único que le sirve para rescatar la versión del otro ordenador.
MENSAJE_CONFLICTO = ("Otro ordenador había subido cambios a tu cuenta antes que "
                     "este. Su versión se ha guardado en {donde} y encima se ha "
                     "subido la de aquí, que es la que tienes delante. Si echas "
                     "algo en falta, esa copia se puede volver a poner desde "
                     "Ajustes → Restaurar copia.")


class ErrorDeSincronia(Exception):
    """Algo que hay que contarle al usuario con sus palabras, no un fallo
    del programa: contraseña mala, usuario cogido, servidor apagado…"""


class FaltaCodigo(ErrorDeSincronia):
    """El servidor pide un código de invitación para crear la cuenta y aquí
    no se ha puesto (o no era el bueno). Es un error como los demás, pero la
    ventana de acceso lo distingue para enseñar el campo del código."""


class _SinConexion(Exception):
    """No se ha llegado al servidor. No es un error del usuario ni del
    programa: se guarda el pendiente y se vuelve a intentar más tarde."""


class Sincronia:
    """El estado de la cuenta y el hilo que sube y baja el libro.

    La regla de oro: el disco manda. Antes de subir nada, el cambio ya está
    guardado en `datos.json`; lo que se sube es lo que hay en ese archivo, no
    lo que haya en memoria, así el hilo de fondo nunca pisa al principal.
    """

    def __init__(self, carpeta: Path, abrir_url=None):
        self.carpeta = Path(carpeta)
        self.ruta_sesion = self.carpeta / ARCHIVO_SESION
        self.ruta_datos = self.carpeta / NOMBRE_ARCHIVO
        self.ruta_copias = self.carpeta / CARPETA_COPIAS
        # Se puede enchufar un servidor de mentira en las pruebas.
        self._abrir_url = abrir_url or urllib.request.urlopen

        # Lo que la ventana tiene que enseñar. Cada aviso es una tupla que
        # empieza por su tipo; la ventana los recoge desde el hilo principal.
        self.avisos: queue.Queue = queue.Queue()

        self.sesion = self._sesion_vacia()
        self.caducada = False
        # Cuenta cuántas veces se ha marcado algo pendiente. Sirve para no
        # dar por subido un cambio que llegó mientras la subida ya volaba.
        self._generacion = 0
        self._candado = threading.Lock()
        self._despertador = threading.Event()
        self._parar = threading.Event()
        self._hilo: threading.Thread | None = None
        self._sin_conexion_avisado = False
        # Cuándo se intentó bajar el libro por última vez, en el reloj de
        # `time.monotonic()` (que no se mueve si el usuario cambia la hora).
        # A None significa «todavía nunca», o sea, que toca ya.
        self._ultima_descarga: float | None = None

        self._cargar_sesion()

    # --- la sesión en disco -------------------------------------------------

    @staticmethod
    def _sesion_vacia() -> dict:
        return {"servidor": SERVIDOR_POR_DEFECTO, "usuario": "", "token": "",
                "ultima_revision": 0, "pendiente": False}

    def _cargar_sesion(self) -> None:
        try:
            crudo = json.loads(self.ruta_sesion.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if not isinstance(crudo, dict):
            return
        sesion = self._sesion_vacia()
        sesion["servidor"] = str(crudo.get("servidor") or SERVIDOR_POR_DEFECTO).rstrip("/")
        sesion["usuario"] = str(crudo.get("usuario") or "")
        sesion["token"] = str(crudo.get("token") or "")
        try:
            sesion["ultima_revision"] = int(crudo.get("ultima_revision") or 0)
        except (TypeError, ValueError):
            sesion["ultima_revision"] = 0
        sesion["pendiente"] = bool(crudo.get("pendiente"))
        self.sesion = sesion

    def _guardar_sesion(self) -> None:
        try:
            self.carpeta.mkdir(parents=True, exist_ok=True)
            self.ruta_sesion.write_text(
                json.dumps(self.sesion, indent=2, ensure_ascii=False),
                encoding="utf-8")
        except OSError:
            pass  # Sin sesión grabada se pedirá entrar otra vez; no se pierde nada.
        try:
            # Dentro va el token, que es la llave de la cuenta: que solo lo
            # pueda leer su dueño. En Windows esto no hace gran cosa, pero
            # tampoco molesta, y en ningún caso debe impedir guardar.
            os.chmod(self.ruta_sesion, 0o600)
        except OSError:
            pass

    def hay_sesion(self) -> bool:
        """Si alguna vez se entró en este ordenador. El token puede estar
        caducado: eso se descubre al primer intento y no pasa nada."""
        return bool(self.sesion["token"])

    # --- entrar y salir -------------------------------------------------------

    def registrar(self, usuario: str, contrasena: str, servidor: str = "",
                  codigo: str = "") -> None:
        """Crea la cuenta. Algunos servidores piden un código de invitación;
        si aquí no se pone, el propio servidor lo reclamará."""
        self._acreditar("/api/cuentas/registro", usuario, contrasena, servidor,
                        codigo=codigo)

    def entrar(self, usuario: str, contrasena: str, servidor: str = "") -> None:
        self._acreditar("/api/cuentas/entrar", usuario, contrasena, servidor)

    def _acreditar(self, ruta: str, usuario: str, contrasena: str, servidor: str,
                   codigo: str = "") -> None:
        """Pide el token y deja la sesión lista. Si se entra con un usuario
        distinto al de la sesión anterior, los datos locales se apartan a una
        copia y se empieza de cero, para no mezclar contabilidades."""
        usuario = usuario.strip()
        servidor = (servidor or self.sesion["servidor"]).strip().rstrip("/")
        if not usuario or not contrasena:
            raise ErrorDeSincronia("Hace falta el usuario y la contraseña.")

        cuerpo = {"usuario": usuario, "contrasena": contrasena}
        # El código solo se manda si hay algo que mandar: los servidores que
        # no piden invitación no tienen por qué recibir un campo vacío.
        if codigo.strip():
            cuerpo["codigo"] = codigo.strip()

        try:
            # Aquí «estado» es el código HTTP; «codigo», el de invitación.
            estado, datos = self._pedir("POST", ruta, servidor=servidor,
                                        con_token=False, cuerpo=cuerpo)
        except _SinConexion:
            raise ErrorDeSincronia(
                "No se ha podido hablar con el servidor. Comprueba la conexión "
                f"y que la dirección sea la buena: {servidor}") from None

        if estado == 409:
            raise ErrorDeSincronia("Ese nombre de usuario ya está cogido.")
        if estado == 401:
            raise ErrorDeSincronia("El usuario o la contraseña no son correctos.")
        if estado == 403:
            # Al crear la cuenta esto es siempre el código de invitación, y la
            # ventana de acceso necesita distinguirlo para enseñar su campo.
            mensaje = _detalle(datos) or MENSAJE_FALTA_CODIGO
            if ruta.endswith("/registro"):
                raise FaltaCodigo(mensaje)
            raise ErrorDeSincronia(mensaje)
        if estado == 422:
            raise ErrorDeSincronia(_detalle(datos) or
                                   "El usuario o la contraseña no valen.")
        if estado == 429:
            raise ErrorDeSincronia(MENSAJE_DEMASIADOS_INTENTOS)
        if (estado not in (200, 201) or not isinstance(datos, dict)
                or not datos.get("token")):
            raise ErrorDeSincronia(
                f"El servidor ha respondido algo inesperado ({estado}).")

        # Quién somos lo dice el servidor, no lo que se haya escrito en el
        # campo: él puede dejar el nombre en minúsculas y sin espacios. Si se
        # comparara lo tecleado, entrar como «Pablo» teniendo la sesión de
        # «pablo» parecería otra cuenta y apartaría la contabilidad por nada.
        de_verdad = str(datos.get("usuario") or usuario)
        anterior = self.sesion["usuario"]
        with self._candado:
            if anterior and anterior != de_verdad:
                self._apartar_datos_de_otro_usuario()
                self.sesion["ultima_revision"] = 0
                self.sesion["pendiente"] = False
            self.sesion["servidor"] = servidor
            self.sesion["usuario"] = de_verdad
            self.sesion["token"] = str(datos["token"])
            self._guardar_sesion()
        self.caducada = False
        self._despertador.set()

    def cambiar_contrasena(self, actual: str, nueva: str) -> None:
        """Cambia la contraseña de la cuenta y se queda con el token nuevo.

        El servidor devuelve un token recién hecho y tira los demás, así que
        este ordenador sigue dentro y los otros verán la sesión caducada y
        tendrán que entrar otra vez. Es lo que se quiere: si la contraseña se
        cambia porque alguien la sabía, no vale dejarle la sesión abierta.

        Esto sí necesita servidor: no hay manera de cambiar una contraseña
        sin conexión, así que sin ella se dice y se queda como estaba.
        """
        if not self.hay_sesion():
            raise ErrorDeSincronia("En este ordenador todavía no hay ninguna cuenta.")
        if not actual or not nueva:
            raise ErrorDeSincronia("Hacen falta la contraseña de ahora y la nueva.")

        try:
            estado, datos = self._pedir(
                "POST", "/api/cuentas/contrasena",
                cuerpo={"contrasena_actual": actual, "contrasena_nueva": nueva})
        except _SinConexion:
            raise ErrorDeSincronia(
                "No se ha podido hablar con el servidor, y la contraseña solo "
                "se puede cambiar estando conectado. Prueba más tarde.") from None

        if estado == 403:
            raise ErrorDeSincronia("La contraseña actual no es correcta.")
        if estado == 422:
            raise ErrorDeSincronia(_detalle(datos) or
                                   "La contraseña nueva no vale: tiene que "
                                   "tener al menos 8 letras o números.")
        if estado == 429:
            raise ErrorDeSincronia(MENSAJE_DEMASIADOS_INTENTOS)
        if estado == 401:
            self._caducar()
            raise ErrorDeSincronia(
                "La sesión ha caducado antes de poder cambiarla. Entra de "
                "nuevo y vuelve a intentarlo.")
        if estado != 200 or not isinstance(datos, dict) or not datos.get("token"):
            raise ErrorDeSincronia(
                f"El servidor ha respondido algo inesperado ({estado}).")

        with self._candado:
            self.sesion["token"] = str(datos["token"])
            self._guardar_sesion()
        self.caducada = False

    def salir(self) -> None:
        """Olvida la cuenta en este ordenador. Los datos locales se quedan."""
        with self._candado:
            self.sesion = self._sesion_vacia()
            try:
                self.ruta_sesion.unlink()
            except OSError:
                pass
        self.caducada = False

    def _apartar_datos_de_otro_usuario(self) -> None:
        """La contabilidad que había era de otra cuenta: a la carpeta de
        copias, con su motivo, y se empieza en blanco para el usuario nuevo."""
        if not self.ruta_datos.exists():
            return
        try:
            self.ruta_copias.mkdir(parents=True, exist_ok=True)
            sello = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            shutil.copy2(self.ruta_datos, self.ruta_copias / f"{sello}-cambio-de-usuario.json")
            self.ruta_datos.unlink()
        except OSError:
            pass  # Peor sería no dejar entrar; los datos siguen donde estaban.

    # --- lo que llama la ventana ----------------------------------------------

    def marcar_pendiente(self) -> None:
        """Después de cada guardado en disco: apuntar que hay algo por subir
        (en el archivo de sesión, para que aguante un cierre) y despertar al
        hilo para que lo intente ya."""
        if not self.hay_sesion():
            return
        with self._candado:
            self._generacion += 1
            self.sesion["pendiente"] = True
            self._guardar_sesion()
        self._despertador.set()

    def confirmar_descarga(self, revision: int) -> None:
        """La ventana ya ha aplicado el libro que bajó del servidor: se apunta
        con qué revisión estamos al día."""
        with self._candado:
            self.sesion["ultima_revision"] = int(revision)
            self._guardar_sesion()

    def estado_actual(self) -> str:
        """Una frase para la pestaña de Ajustes."""
        if not self.hay_sesion():
            return "Sin cuenta."
        if self.caducada:
            return "Sesión caducada: hay que entrar de nuevo para seguir subiendo."
        if self.sesion["pendiente"]:
            return "Hay cambios pendientes de subir. Se subirán solos al haber conexión."
        return "Al día con el servidor."

    def arrancar_fondo(self) -> None:
        """Pone en marcha el hilo: primero mira qué hay en el servidor y luego
        se queda subiendo lo pendiente cada vez que haga falta."""
        if self._hilo is not None or not self.hay_sesion():
            return
        self._hilo = threading.Thread(target=self._bucle, daemon=True,
                                      name="contaxcell-sincronia")
        self._hilo.start()

    def detener(self) -> None:
        self._parar.set()
        self._despertador.set()

    # --- el hilo de fondo -------------------------------------------------------

    def _bucle(self) -> None:
        while not self._parar.is_set():
            if self.sesion["pendiente"] and self.hay_sesion() and not self.caducada:
                self.empujar()
            elif self.toca_descargar(time.monotonic()):
                # Subir es lo urgente; bajar, de vez en cuando. Si no se
                # mirara cada tanto, el otro ordenador podría estar horas
                # trabajando sin que aquí se enterara nadie.
                self.descargar()
            self._despertador.wait(timeout=SEGUNDOS_ENTRE_REINTENTOS)
            self._despertador.clear()

    def toca_descargar(self, ahora: float) -> bool:
        """Si ya va tocando mirar qué hay en el servidor.

        `ahora` es el reloj de `time.monotonic()`. Se pasa desde fuera para
        poder probar la decisión sin esperar dos minutos de verdad.
        """
        if not self.hay_sesion() or self.caducada or self.sesion["pendiente"]:
            return False
        if self._ultima_descarga is None:
            return True  # Recién arrancada: todavía no se ha mirado nada.
        return ahora - self._ultima_descarga >= SEGUNDOS_ENTRE_DESCARGAS

    def descargar(self) -> None:
        """Traer lo que tenga el servidor: al arrancar, al volver a entrar y
        cada `SEGUNDOS_ENTRE_DESCARGAS` mientras la aplicación esté abierta.

        Solo se sustituye lo local si aquí no hay nada a medio subir y el
        servidor va por otra revisión. Y si el servidor está vacío pero aquí
        hay contabilidad, lo que toca es subirla, no borrarla.
        """
        if not self.hay_sesion():
            return
        # Se apunta el intento, no el acierto: si el servidor no contesta,
        # tampoco hay que insistir cada treinta segundos.
        self._ultima_descarga = time.monotonic()
        try:
            codigo, datos = self._pedir("GET", "/api/libro")
        except _SinConexion:
            self._avisar_sin_conexion()
            return

        if codigo == 401:
            self._caducar()
            return
        if codigo != 200 or not isinstance(datos, dict):
            return
        self._sin_conexion_avisado = False

        revision = int(datos.get("revision") or 0)
        libro = datos.get("libro")

        if libro is None:
            # Cuenta recién estrenada: lo local es lo único que existe.
            with self._candado:
                self.sesion["ultima_revision"] = revision
                if self.ruta_datos.exists():
                    self.sesion["pendiente"] = True
                self._guardar_sesion()
            if self.sesion["pendiente"]:
                self._despertador.set()
            return

        if self.sesion["pendiente"]:
            # Lo de aquí todavía no está subido: primero se sube (y el propio
            # servidor avisará del conflicto si lo hay).
            return
        if revision == self.sesion["ultima_revision"]:
            return

        local = self._libro_local()
        if local is not None and local == libro:
            # El servidor va por otra revisión, pero su libro es exactamente
            # el archivo que hay aquí: no hay nada que traer. Pasa siempre al
            # volver a entrar sin haber cambiado nada, y avisar de una
            # descarga que no cambia ni una coma solo asusta.
            with self._candado:
                self.sesion["ultima_revision"] = revision
                self._guardar_sesion()
            return

        # Sin revisión apuntada no se sabe de dónde viene lo de aquí: puede
        # ser trabajo hecho sin conexión después de cerrar sesión, y está a
        # punto de ser reemplazado. Eso la ventana lo cuenta en voz alta.
        local_sin_vinculo = (self.sesion["ultima_revision"] == 0
                             and self.ruta_datos.exists())
        self.avisos.put(("descargar", libro, revision, local_sin_vinculo))

    def empujar(self) -> bool:
        """Sube el `datos.json` tal cual está en el disco. Devuelve si ha
        quedado todo al día."""
        if not self.hay_sesion() or not self.sesion["pendiente"]:
            return True
        with self._candado:
            generacion_leida = self._generacion
        crudo = self._libro_local()
        if crudo is None:
            return False  # Sin archivo legible no hay nada que subir todavía.

        revision_base = self.sesion["ultima_revision"]
        conflicto_avisado = False
        for _ in range(1 + INTENTOS_POR_CONFLICTO):
            try:
                codigo, datos = self._pedir(
                    "PUT", "/api/libro",
                    cuerpo={"revision_base": revision_base, "libro": crudo})
            except _SinConexion:
                self._avisar_sin_conexion()
                return False

            if codigo == 200 and isinstance(datos, dict):
                with self._candado:
                    self.sesion["ultima_revision"] = int(datos.get("revision") or 0)
                    # Si mientras subíamos se guardó otro cambio, lo subido ya
                    # está viejo: el pendiente se queda puesto y se repite.
                    if self._generacion == generacion_leida:
                        self.sesion["pendiente"] = False
                    self._guardar_sesion()
                self._sin_conexion_avisado = False
                self.avisos.put(("estado", "Sincronizado.", "bien"))
                return True

            if codigo == 409 and isinstance(datos, dict):
                # Alguien subió antes que nosotros. Gana lo de aquí, que es lo
                # que el usuario tiene delante, pero lo del servidor se guarda
                # en una copia fechada por si hiciera falta rescatarlo. Y se
                # dice: esto puede ser trabajo de otro que se queda atrás.
                copia = self._guardar_copia_del_conflicto(datos.get("libro"))
                if not conflicto_avisado:
                    # Un aviso por conflicto resuelto, no uno por reintento.
                    conflicto_avisado = True
                    donde = (f"{CARPETA_COPIAS}/{copia.name}" if copia is not None
                             else f"la carpeta «{CARPETA_COPIAS}»")
                    self.avisos.put(("conflicto", MENSAJE_CONFLICTO.format(donde=donde)))
                revision_base = int(datos.get("revision") or 0)
                continue

            if codigo == 401:
                self._caducar()
                return False

            return False  # Respuesta rara: mejor reintentar más tarde.
        return False

    # --- avisos ------------------------------------------------------------------

    def _avisar_sin_conexion(self) -> None:
        # Solo la primera vez de cada racha: repetirlo cada medio minuto
        # sería un incordio, y el estado ya se ve en Ajustes.
        if self._sin_conexion_avisado:
            return
        self._sin_conexion_avisado = True
        self.avisos.put(("estado", MENSAJE_SIN_CONEXION, ""))

    def _caducar(self) -> None:
        # El pendiente no se toca: en cuanto se entre otra vez, se sube.
        if not self.caducada:
            self.caducada = True
            self.avisos.put(("caducada", MENSAJE_CADUCADA))

    def _guardar_copia_del_conflicto(self, libro) -> Path | None:
        """Deja la versión del servidor en copias y devuelve dónde, que es lo
        que hay que decirle al usuario para que pueda rescatarla."""
        if not isinstance(libro, dict):
            return None
        try:
            self.ruta_copias.mkdir(parents=True, exist_ok=True)
            sello = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            destino = self.ruta_copias / f"{sello}-conflicto-sincronia.json"
            destino.write_text(json.dumps(libro, indent=2, ensure_ascii=False),
                               encoding="utf-8")
            return destino
        except OSError:
            return None  # La copia es un salvavidas de más; la subida sigue igual.

    # --- el archivo de datos --------------------------------------------------------

    def _libro_local(self):
        """Lo que hay ahora mismo en `datos.json`, tal cual, o None si no hay
        archivo o no se entiende. El disco manda: es esto lo que se sube y con
        esto se compara lo que baja."""
        try:
            return json.loads(self.ruta_datos.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    # --- la petición en sí ----------------------------------------------------------

    def _pedir(self, metodo: str, ruta: str, cuerpo: dict | None = None,
               servidor: str = "", con_token: bool = True) -> tuple[int, object]:
        """Una petición al servidor y su respuesta como (código, JSON).

        Los códigos de error HTTP se devuelven igual que los buenos, porque
        aquí un 409 o un 401 no son excepciones: son respuestas con las que
        hay que hacer algo. La excepción de verdad es no llegar al servidor.
        """
        base = (servidor or self.sesion["servidor"]).rstrip("/")
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        peticion = urllib.request.Request(base + ruta, data=datos, method=metodo)
        peticion.add_header("Content-Type", "application/json")
        if con_token:
            peticion.add_header("Authorization", f"Bearer {self.sesion['token']}")

        try:
            with self._abrir_url(peticion, timeout=SEGUNDOS_DE_ESPERA) as respuesta:
                return respuesta.status, _json_de(respuesta.read())
        except urllib.error.HTTPError as error:
            try:
                return error.code, _json_de(error.read())
            except OSError:
                return error.code, None
        except (urllib.error.URLError, OSError, TimeoutError) as error:
            raise _SinConexion(str(error)) from error


def _json_de(crudo: bytes):
    try:
        return json.loads(crudo.decode("utf-8")) if crudo else None
    except (ValueError, UnicodeDecodeError):
        return None


def _detalle(datos) -> str:
    """El mensaje de error que manda el servidor, esté donde esté."""
    if isinstance(datos, dict):
        detalle = datos.get("detail") or datos.get("detalle")
        if isinstance(detalle, str):
            return detalle
        if isinstance(detalle, list) and detalle:
            primero = detalle[0]
            if isinstance(primero, dict) and isinstance(primero.get("msg"), str):
                return primero["msg"]
    return ""
