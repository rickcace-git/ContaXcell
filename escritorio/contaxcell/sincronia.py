"""Hablar con el servidor de cuentas para tener los datos en más de un sitio.

La aplicación funciona igual con o sin internet: todo se guarda primero en el
disco, como siempre, y este módulo se encarga después de subirlo cuando haya
conexión. Si no la hay, se apunta que queda algo pendiente (y se apunta en un
archivo, para que sobreviva a cerrar la aplicación) y se reintenta solo.

Aquí no hay nada de tkinter a propósito: el hilo de fondo no puede tocar la
ventana, así que lo que tenga que ver el usuario se deja en una cola de avisos
que la ventana vacía desde el hilo principal. Por eso mismo se puede probar
entero sin abrir una pantalla.
"""

from __future__ import annotations

import json
import queue
import shutil
import threading
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from .almacen import CARPETA_COPIAS, NOMBRE_ARCHIVO

ARCHIVO_SESION = "sesion.json"
SERVIDOR_POR_DEFECTO = "http://localhost:8000"
SEGUNDOS_DE_ESPERA = 10
SEGUNDOS_ENTRE_REINTENTOS = 30
# Si el servidor cambia mientras subimos, se reintenta con su revisión nueva.
# Con un tope, por si dos aparatos se empeñan en escribir a la vez sin parar.
INTENTOS_POR_CONFLICTO = 3

MENSAJE_SIN_CONEXION = "Sin conexión: se subirá cuando vuelva internet."
MENSAJE_CADUCADA = ("La sesión ha caducado. Entra de nuevo desde Ajustes; "
                    "mientras tanto todo sigue funcionando sin conexión.")


class ErrorDeSincronia(Exception):
    """Algo que hay que contarle al usuario con sus palabras, no un fallo
    del programa: contraseña mala, usuario cogido, servidor apagado…"""


class SinPrecios(ErrorDeSincronia):
    """El servidor no ha podido dar precios. No es grave: se siguen usando
    los que ya hubiera guardados."""


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

    def hay_sesion(self) -> bool:
        """Si alguna vez se entró en este ordenador. El token puede estar
        caducado: eso se descubre al primer intento y no pasa nada."""
        return bool(self.sesion["token"])

    # --- entrar y salir -------------------------------------------------------

    def registrar(self, usuario: str, contrasena: str, servidor: str = "") -> None:
        self._acreditar("/api/cuentas/registro", usuario, contrasena, servidor)

    def entrar(self, usuario: str, contrasena: str, servidor: str = "") -> None:
        self._acreditar("/api/cuentas/entrar", usuario, contrasena, servidor)

    def _acreditar(self, ruta: str, usuario: str, contrasena: str, servidor: str) -> None:
        """Pide el token y deja la sesión lista. Si se entra con un usuario
        distinto al de la sesión anterior, los datos locales se apartan a una
        copia y se empieza de cero, para no mezclar contabilidades."""
        usuario = usuario.strip()
        servidor = (servidor or self.sesion["servidor"]).strip().rstrip("/")
        if not usuario or not contrasena:
            raise ErrorDeSincronia("Hace falta el usuario y la contraseña.")

        try:
            codigo, datos = self._pedir("POST", ruta, servidor=servidor, con_token=False,
                                        cuerpo={"usuario": usuario, "contrasena": contrasena})
        except _SinConexion:
            raise ErrorDeSincronia(
                "No se ha podido hablar con el servidor. Comprueba la conexión "
                f"y que la dirección sea la buena: {servidor}") from None

        if codigo == 409:
            raise ErrorDeSincronia("Ese nombre de usuario ya está cogido.")
        if codigo == 401:
            raise ErrorDeSincronia("El usuario o la contraseña no son correctos.")
        if codigo == 422:
            raise ErrorDeSincronia(_detalle(datos) or
                                   "El usuario o la contraseña no valen.")
        if codigo not in (200, 201) or not isinstance(datos, dict) or not datos.get("token"):
            raise ErrorDeSincronia(f"El servidor ha respondido algo inesperado ({codigo}).")

        anterior = self.sesion["usuario"]
        with self._candado:
            if anterior and anterior != usuario:
                self._apartar_datos_de_otro_usuario()
                self.sesion["ultima_revision"] = 0
                self.sesion["pendiente"] = False
            self.sesion["servidor"] = servidor
            self.sesion["usuario"] = str(datos.get("usuario") or usuario)
            self.sesion["token"] = str(datos["token"])
            self._guardar_sesion()
        self.caducada = False
        self._despertador.set()

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
        self.descargar()
        while not self._parar.is_set():
            if self.sesion["pendiente"] and self.hay_sesion() and not self.caducada:
                self.empujar()
            self._despertador.wait(timeout=SEGUNDOS_ENTRE_REINTENTOS)
            self._despertador.clear()

    def descargar(self) -> None:
        """Al arrancar (o al volver a entrar): traer lo que tenga el servidor.

        Solo se sustituye lo local si aquí no hay nada a medio subir y el
        servidor va por otra revisión. Y si el servidor está vacío pero aquí
        hay contabilidad, lo que toca es subirla, no borrarla.
        """
        if not self.hay_sesion():
            return
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
        if revision != self.sesion["ultima_revision"]:
            self.avisos.put(("descargar", libro, revision))

    def empujar(self) -> bool:
        """Sube el `datos.json` tal cual está en el disco. Devuelve si ha
        quedado todo al día."""
        if not self.hay_sesion() or not self.sesion["pendiente"]:
            return True
        with self._candado:
            generacion_leida = self._generacion
        try:
            crudo = json.loads(self.ruta_datos.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False  # Sin archivo legible no hay nada que subir todavía.

        revision_base = self.sesion["ultima_revision"]
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
                # en una copia fechada por si hiciera falta rescatarlo.
                self._guardar_copia_del_conflicto(datos.get("libro"))
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

    def _guardar_copia_del_conflicto(self, libro) -> None:
        if not isinstance(libro, dict):
            return
        try:
            self.ruta_copias.mkdir(parents=True, exist_ok=True)
            sello = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            destino = self.ruta_copias / f"{sello}-conflicto-sincronia.json"
            destino.write_text(json.dumps(libro, indent=2, ensure_ascii=False),
                               encoding="utf-8")
        except OSError:
            pass  # La copia es un salvavidas de más; la subida sigue igual.

    # --- la petición en sí ----------------------------------------------------------

    # --- precios ---
    #
    # Los sirve el servidor, no el proveedor: la clave está allí y no en el
    # `.exe`, donde sería pública. Aquí solo se piden y se guardan, para que
    # la cartera siga saliendo bien cuando no haya conexión.

    def buscar_cotizacion(self, texto: str) -> list[dict]:
        """Las cotizaciones que encajan con lo buscado.

        Se llama al elegir la cotización de un activo, que es cosa de una
        vez. Va en el hilo principal a propósito: el usuario está delante
        esperando la respuesta.
        """
        if not self.hay_sesion():
            raise SinPrecios("Hace falta una cuenta para buscar cotizaciones.")
        try:
            codigo, datos = self._pedir(
                "GET", "/api/precios/buscar?q=" + urllib.parse.quote(texto.strip()))
        except _SinConexion as error:
            raise SinPrecios("No se ha podido hablar con el servidor.") from error

        if codigo == 200 and isinstance(datos, dict):
            return datos.get("encontrados") or []
        if codigo == 503:
            raise SinPrecios(
                "El servidor no tiene configurada la clave de precios. "
                "Hay que ponerla en su archivo .env.")
        if codigo == 401:
            self._caducar()
            raise SinPrecios("La sesión ha caducado: entra de nuevo.")
        raise SinPrecios(_detalle(datos) or f"El servidor ha contestado {codigo}.")

    def traer_cotizaciones(self, simbolo: str, desde: str) -> list:
        """Los cierres diarios de una cotización. Lista vacía si no hay forma.

        Este no lanza nada cuando falla la red: se llama desde el hilo de
        fondo, y que hoy no haya precios nuevos no es un problema del que
        haya que avisar. Lo guardado sigue sirviendo.
        """
        from .modelo import Cotizacion

        if not self.hay_sesion():
            return []
        consulta = urllib.parse.urlencode({"simbolo": simbolo, "desde": desde})
        try:
            codigo, datos = self._pedir("GET", "/api/precios?" + consulta)
        except _SinConexion:
            return []
        if codigo != 200 or not isinstance(datos, dict):
            return []

        traidas = [Cotizacion.desde_json({**cruda, "simbolo": simbolo})
                   for cruda in (datos.get("cotizaciones") or [])
                   if isinstance(cruda, dict)]
        return [c for c in traidas if c.fecha and c.precio > 0]

    def pedir_precios_de_fondo(self, peticiones: list) -> None:
        """Trae los precios en un hilo aparte y los deja en la cola.

        `peticiones` son pares (símbolo, desde). El hilo no puede tocar la
        ventana, así que deja el resultado en `self.avisos` y es el hilo
        principal quien lo guarda en el libro, como todo lo demás de aquí.

        Si no hay conexión no avisa de nada: que hoy no haya precios nuevos
        no es un problema que merezca una línea en la barra de estado.
        """
        if not peticiones or not self.hay_sesion():
            return

        def trabajo():
            traidas = {}
            for simbolo, desde in peticiones:
                cotizaciones = self.traer_cotizaciones(simbolo, desde)
                if cotizaciones:
                    traidas[simbolo] = cotizaciones
            if traidas:
                self.avisos.put(("precios", traidas))

        hilo = threading.Thread(target=trabajo, daemon=True,
                                name="contaxcell-precios")
        hilo.start()

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
