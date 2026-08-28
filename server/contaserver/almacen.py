"""Dónde guarda el servidor los usuarios y sus libros.

Hay dos implementaciones con la misma cara:

- ``AlmacenSQLite``: la biblioteca estándar, un archivo o memoria. Es la que
  usan las pruebas, que así corren sin Docker ni red en un segundo.
- ``AlmacenPostgres``: la de producción, contra el Postgres del docker-compose.

La aplicación no sabe cuál de las dos tiene delante: llama a los mismos
métodos. Cualquier otra base de datos que los implemente serviría igual.

Los precios van aparte y no cuelgan de ningún usuario: no son de nadie, son
del grupo. Lo que vale un fondo es lo mismo para todos, así que se pregunta
una vez y se guarda una vez.

La pieza delicada es ``guardar_libro``: es un *compara-y-cambia*. Solo graba
si la revisión que trae el cliente es exactamente la que hay en el servidor,
y lo comprueba y graba en una única sentencia, de forma que dos subidas a la
vez con la misma revisión de partida no pueden colarse las dos: una gana y
la otra recibe el conflicto.
"""

from __future__ import annotations

import json
import sqlite3
import threading

# psycopg solo hace falta en producción. Las pruebas y cualquier máquina sin
# él siguen funcionando con SQLite, así que el import no puede ser mortal.
try:
    import psycopg
except ImportError:  # pragma: no cover - en las pruebas no está instalado
    psycopg = None


class UsuarioYaExiste(Exception):
    """Alguien intenta registrarse con un nombre que ya está cogido."""


# --- SQLite: para las pruebas y para probar en local sin Docker --------------

class AlmacenSQLite:
    def __init__(self, ruta: str = ":memory:"):
        # check_same_thread=False porque el servidor de pruebas atiende desde
        # otro hilo; el candado de abajo es quien pone el orden.
        self._conexion = sqlite3.connect(ruta, check_same_thread=False)
        self._candado = threading.Lock()
        self._crear_esquema()

    def _crear_esquema(self) -> None:
        with self._candado:
            self._conexion.executescript("""
                CREATE TABLE IF NOT EXISTS usuarios (
                    id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario TEXT NOT NULL UNIQUE,
                    hash    TEXT NOT NULL,
                    sal     TEXT NOT NULL,
                    creado  TEXT NOT NULL DEFAULT (datetime('now'))
                );
                CREATE TABLE IF NOT EXISTS libros (
                    usuario_id  INTEGER PRIMARY KEY REFERENCES usuarios(id),
                    revision    INTEGER NOT NULL,
                    datos       TEXT NOT NULL,
                    actualizado TEXT NOT NULL DEFAULT (datetime('now'))
                );
                -- Los precios no son de nadie: son del grupo. Por eso no
                -- cuelgan de un usuario y se preguntan una sola vez.
                CREATE TABLE IF NOT EXISTS precios (
                    simbolo TEXT NOT NULL,
                    fecha   TEXT NOT NULL,
                    precio  REAL NOT NULL,
                    moneda  TEXT NOT NULL DEFAULT 'EUR',
                    PRIMARY KEY (simbolo, fecha)
                );
                CREATE TABLE IF NOT EXISTS consultas_precios (
                    simbolo TEXT PRIMARY KEY,
                    dia     TEXT NOT NULL
                );
            """)
            self._conexion.commit()

    def crear_usuario(self, usuario: str, hash_contrasena: str, sal: str) -> int:
        with self._candado:
            try:
                cursor = self._conexion.execute(
                    "INSERT INTO usuarios (usuario, hash, sal) VALUES (?, ?, ?)",
                    (usuario, hash_contrasena, sal),
                )
                self._conexion.commit()
            except sqlite3.IntegrityError:
                raise UsuarioYaExiste(usuario)
            return int(cursor.lastrowid)

    def buscar_usuario(self, usuario: str) -> tuple[int, str, str] | None:
        """(id, hash, sal) del usuario, o None si no existe."""
        with self._candado:
            fila = self._conexion.execute(
                "SELECT id, hash, sal FROM usuarios WHERE usuario = ?",
                (usuario,),
            ).fetchone()
        return (int(fila[0]), fila[1], fila[2]) if fila else None

    def leer_libro(self, usuario_id: int) -> tuple[int, dict | None]:
        """(revision, libro). Si nunca subió nada: (0, None)."""
        with self._candado:
            fila = self._conexion.execute(
                "SELECT revision, datos FROM libros WHERE usuario_id = ?",
                (usuario_id,),
            ).fetchone()
        if fila is None:
            return 0, None
        return int(fila[0]), json.loads(fila[1])

    def guardar_libro(self, usuario_id: int, revision_base: int, libro: dict) -> int | None:
        """Graba solo si revision_base coincide con lo que hay.

        Devuelve la revisión nueva, o None si hubo conflicto. La primera
        subida de un usuario es revision_base=0 (todavía no hay fila).
        """
        datos = json.dumps(libro, ensure_ascii=False)
        with self._candado:
            if revision_base == 0:
                # Primera subida: solo vale si todavía no existe la fila.
                cursor = self._conexion.execute(
                    "INSERT OR IGNORE INTO libros (usuario_id, revision, datos)"
                    " VALUES (?, 1, ?)",
                    (usuario_id, datos),
                )
            else:
                # Compara-y-cambia: el WHERE por revisión hace que solo una
                # de dos subidas simultáneas encuentre la fila que espera.
                cursor = self._conexion.execute(
                    "UPDATE libros SET revision = revision + 1, datos = ?,"
                    " actualizado = datetime('now')"
                    " WHERE usuario_id = ? AND revision = ?",
                    (datos, usuario_id, revision_base),
                )
            self._conexion.commit()
            if cursor.rowcount != 1:
                return None
            return revision_base + 1

    # --- precios ---

    def leer_precios(self, simbolo: str, desde: str) -> list:
        from .precios import Cotizacion
        with self._candado:
            filas = self._conexion.execute(
                "SELECT fecha, precio, moneda FROM precios"
                " WHERE simbolo = ? AND fecha >= ? ORDER BY fecha",
                (simbolo, desde),
            ).fetchall()
        return [Cotizacion(f[0], float(f[1]), f[2]) for f in filas]

    def ultimo_precio(self, simbolo: str) -> str:
        """La fecha del último cierre guardado, o cadena vacía."""
        with self._candado:
            fila = self._conexion.execute(
                "SELECT MAX(fecha) FROM precios WHERE simbolo = ?", (simbolo,),
            ).fetchone()
        return fila[0] or "" if fila else ""

    def guardar_precios(self, simbolo: str, cotizaciones: list) -> None:
        """Guarda o pisa. Un cierre puede corregirse el mismo día."""
        with self._candado:
            self._conexion.executemany(
                "INSERT OR REPLACE INTO precios (simbolo, fecha, precio, moneda)"
                " VALUES (?, ?, ?, ?)",
                [(simbolo, c.fecha, c.precio, c.moneda) for c in cotizaciones],
            )
            self._conexion.commit()

    def ultima_consulta(self, simbolo: str) -> str:
        with self._candado:
            fila = self._conexion.execute(
                "SELECT dia FROM consultas_precios WHERE simbolo = ?", (simbolo,),
            ).fetchone()
        return fila[0] if fila else ""

    def apuntar_consulta(self, simbolo: str, dia: str) -> None:
        with self._candado:
            self._conexion.execute(
                "INSERT OR REPLACE INTO consultas_precios (simbolo, dia)"
                " VALUES (?, ?)", (simbolo, dia))
            self._conexion.commit()


# --- Postgres: producción -----------------------------------------------------

class AlmacenPostgres:
    """Igual que el de SQLite pero contra Postgres, vía psycopg.

    Una única conexión con autocommit y un candado delante. Para un servidor
    personal con un puñado de usuarios sobra; si algún día hiciera falta más,
    aquí es donde iría un pool de conexiones sin tocar nada más.
    """

    def __init__(self, url: str):
        if psycopg is None:
            raise RuntimeError(
                "psycopg no está instalado; hace falta para usar Postgres"
            )
        self._url = url
        self._candado = threading.Lock()
        self._conexion = psycopg.connect(url, autocommit=True)
        self._crear_esquema()

    def _ejecutar(self, sql: str, parametros: tuple = ()):
        """Ejecuta reintentando una vez si la conexión se había caído."""
        with self._candado:
            try:
                return self._conexion.execute(sql, parametros)
            except psycopg.OperationalError:
                self._conexion = psycopg.connect(self._url, autocommit=True)
                return self._conexion.execute(sql, parametros)

    def _crear_esquema(self) -> None:
        self._ejecutar("""
            CREATE TABLE IF NOT EXISTS usuarios (
                id      SERIAL PRIMARY KEY,
                usuario TEXT NOT NULL UNIQUE,
                hash    TEXT NOT NULL,
                sal     TEXT NOT NULL,
                creado  TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        self._ejecutar("""
            CREATE TABLE IF NOT EXISTS libros (
                usuario_id  INTEGER PRIMARY KEY REFERENCES usuarios(id),
                revision    INTEGER NOT NULL,
                datos       JSONB NOT NULL,
                actualizado TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        # Los precios no son de nadie: son del grupo. Por eso no cuelgan de
        # un usuario y se preguntan una sola vez para todos.
        self._ejecutar("""
            CREATE TABLE IF NOT EXISTS precios (
                simbolo TEXT NOT NULL,
                fecha   DATE NOT NULL,
                precio  DOUBLE PRECISION NOT NULL,
                moneda  TEXT NOT NULL DEFAULT 'EUR',
                PRIMARY KEY (simbolo, fecha)
            )
        """)
        self._ejecutar("""
            CREATE TABLE IF NOT EXISTS consultas_precios (
                simbolo TEXT PRIMARY KEY,
                dia     DATE NOT NULL
            )
        """)

    def crear_usuario(self, usuario: str, hash_contrasena: str, sal: str) -> int:
        try:
            cursor = self._ejecutar(
                "INSERT INTO usuarios (usuario, hash, sal) VALUES (%s, %s, %s)"
                " RETURNING id",
                (usuario, hash_contrasena, sal),
            )
        except psycopg.errors.UniqueViolation:
            raise UsuarioYaExiste(usuario)
        return int(cursor.fetchone()[0])

    def buscar_usuario(self, usuario: str) -> tuple[int, str, str] | None:
        cursor = self._ejecutar(
            "SELECT id, hash, sal FROM usuarios WHERE usuario = %s",
            (usuario,),
        )
        fila = cursor.fetchone()
        return (int(fila[0]), fila[1], fila[2]) if fila else None

    def leer_libro(self, usuario_id: int) -> tuple[int, dict | None]:
        cursor = self._ejecutar(
            "SELECT revision, datos FROM libros WHERE usuario_id = %s",
            (usuario_id,),
        )
        fila = cursor.fetchone()
        if fila is None:
            return 0, None
        datos = fila[1]
        # psycopg devuelve el JSONB ya convertido a dict; si llegara como
        # texto (según la configuración), lo convertimos nosotros.
        if isinstance(datos, str):
            datos = json.loads(datos)
        return int(fila[0]), datos

    def guardar_libro(self, usuario_id: int, revision_base: int, libro: dict) -> int | None:
        datos = json.dumps(libro, ensure_ascii=False)
        if revision_base == 0:
            # Primera subida: ON CONFLICT DO NOTHING hace que si dos llegan a
            # la vez, Postgres solo deje pasar una. La otra no devuelve fila.
            cursor = self._ejecutar(
                "INSERT INTO libros (usuario_id, revision, datos)"
                " VALUES (%s, 1, %s::jsonb)"
                " ON CONFLICT (usuario_id) DO NOTHING"
                " RETURNING revision",
                (usuario_id, datos),
            )
        else:
            # Compara-y-cambia en una sola sentencia: el UPDATE solo toca la
            # fila si la revisión sigue siendo la esperada, y Postgres
            # garantiza que dos UPDATE así no pueden acertar los dos.
            cursor = self._ejecutar(
                "UPDATE libros SET revision = revision + 1, datos = %s::jsonb,"
                " actualizado = now()"
                " WHERE usuario_id = %s AND revision = %s"
                " RETURNING revision",
                (datos, usuario_id, revision_base),
            )
        fila = cursor.fetchone()
        return int(fila[0]) if fila else None

    # --- precios ---

    def leer_precios(self, simbolo: str, desde: str) -> list:
        from .precios import Cotizacion
        cursor = self._ejecutar(
            "SELECT fecha, precio, moneda FROM precios"
            " WHERE simbolo = %s AND fecha >= %s ORDER BY fecha",
            (simbolo, desde))
        return [Cotizacion(f[0].isoformat(), float(f[1]), f[2])
                for f in cursor.fetchall()]

    def ultimo_precio(self, simbolo: str) -> str:
        """La fecha del ultimo cierre guardado, o cadena vacia."""
        cursor = self._ejecutar(
            "SELECT MAX(fecha) FROM precios WHERE simbolo = %s", (simbolo,))
        fila = cursor.fetchone()
        return fila[0].isoformat() if fila and fila[0] else ""

    def guardar_precios(self, simbolo: str, cotizaciones: list) -> None:
        """Guarda o pisa. Un cierre puede corregirse el mismo dia."""
        for c in cotizaciones:
            self._ejecutar(
                "INSERT INTO precios (simbolo, fecha, precio, moneda)"
                " VALUES (%s, %s, %s, %s)"
                " ON CONFLICT (simbolo, fecha) DO UPDATE"
                " SET precio = EXCLUDED.precio, moneda = EXCLUDED.moneda",
                (simbolo, c.fecha, c.precio, c.moneda))

    def ultima_consulta(self, simbolo: str) -> str:
        cursor = self._ejecutar(
            "SELECT dia FROM consultas_precios WHERE simbolo = %s", (simbolo,))
        fila = cursor.fetchone()
        return fila[0].isoformat() if fila and fila[0] else ""

    def apuntar_consulta(self, simbolo: str, dia: str) -> None:
        self._ejecutar(
            "INSERT INTO consultas_precios (simbolo, dia) VALUES (%s, %s)"
            " ON CONFLICT (simbolo) DO UPDATE SET dia = EXCLUDED.dia",
            (simbolo, dia))
