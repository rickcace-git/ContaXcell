"""Dónde guarda el servidor los usuarios y sus libros.

Hay dos implementaciones con la misma cara:

- ``AlmacenSQLite``: la biblioteca estándar, un archivo o memoria. Es la que
  usan las pruebas, que así corren sin Docker ni red en un segundo.
- ``AlmacenPostgres``: la de producción, contra el Postgres del docker-compose.

La aplicación no sabe cuál de las dos tiene delante: llama a los mismos
métodos. Cualquier otra base de datos que los implemente serviría igual.

Cada usuario guarda además una *generación*: un contador que sube en uno cada
vez que cambia su contraseña. Las fichas de sesión llevan dentro la generación
con la que se emitieron, así que subirla invalida de golpe todas las fichas
antiguas de ese usuario.

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
from datetime import datetime, timezone

# psycopg solo hace falta en producción. Las pruebas y cualquier máquina sin
# él siguen funcionando con SQLite, así que el import no puede ser mortal.
try:
    import psycopg
except ImportError:  # pragma: no cover - en las pruebas no está instalado
    psycopg = None


class UsuarioYaExiste(Exception):
    """Alguien intenta registrarse con un nombre que ya está cogido."""


# El último uso de cada usuario se apunta como mucho una vez cada tanto: para
# saber quién usa el servidor basta con eso, y así no se escribe en la base
# con cada petición que llega.
MINUTOS_ENTRE_USOS = 5


def _momento_sqlite(texto: str | None) -> datetime | None:
    """Las fechas de SQLite son texto en UTC; aquí pasan a fecha con su zona,
    que es como las devuelve Postgres."""
    if not texto:
        return None
    return datetime.fromisoformat(texto).replace(tzinfo=timezone.utc)


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
                    id         INTEGER PRIMARY KEY AUTOINCREMENT,
                    usuario    TEXT NOT NULL UNIQUE,
                    hash       TEXT NOT NULL,
                    sal        TEXT NOT NULL,
                    generacion INTEGER NOT NULL DEFAULT 0,
                    creado     TEXT NOT NULL DEFAULT (datetime('now')),
                    ultimo_uso TEXT,
                    vetado     TEXT,
                    en_espera  INTEGER NOT NULL DEFAULT 0
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
            # Para una base que ya existía de antes: el CREATE de arriba no la
            # toca, así que las columnas nuevas hay que añadirlas aparte. Si
            # ya están, SQLite protesta y no pasa nada.
            for columna in ("generacion INTEGER NOT NULL DEFAULT 0",
                            "ultimo_uso TEXT", "vetado TEXT",
                            "en_espera INTEGER NOT NULL DEFAULT 0"):
                try:
                    self._conexion.execute(
                        f"ALTER TABLE usuarios ADD COLUMN {columna}"
                    )
                except sqlite3.OperationalError:
                    pass
            self._conexion.commit()

    def crear_usuario(self, usuario: str, hash_contrasena: str, sal: str,
                      en_espera: bool = False) -> int:
        """Con `en_espera`, la cuenta existe pero no guarda nada hasta que el
        administrador la acepte (`./usuarios aceptar`)."""
        with self._candado:
            try:
                cursor = self._conexion.execute(
                    "INSERT INTO usuarios (usuario, hash, sal, en_espera)"
                    " VALUES (?, ?, ?, ?)",
                    (usuario, hash_contrasena, sal, 1 if en_espera else 0),
                )
                self._conexion.commit()
            except sqlite3.IntegrityError:
                raise UsuarioYaExiste(usuario)
            return int(cursor.lastrowid)

    def buscar_usuario(self, usuario: str) -> tuple[int, str, str, int] | None:
        """(id, hash, sal, generacion) del usuario, o None si no existe."""
        with self._candado:
            fila = self._conexion.execute(
                "SELECT id, hash, sal, generacion FROM usuarios WHERE usuario = ?",
                (usuario,),
            ).fetchone()
        return (int(fila[0]), fila[1], fila[2], int(fila[3])) if fila else None

    def generacion_de(self, usuario_id: int) -> int | None:
        """La generación actual del usuario, o None si ya no existe."""
        with self._candado:
            fila = self._conexion.execute(
                "SELECT generacion FROM usuarios WHERE id = ?",
                (usuario_id,),
            ).fetchone()
        return int(fila[0]) if fila else None

    def credenciales_por_id(self, usuario_id: int) -> tuple[str, str] | None:
        """(hash, sal) del usuario, o None si no existe."""
        with self._candado:
            fila = self._conexion.execute(
                "SELECT hash, sal FROM usuarios WHERE id = ?",
                (usuario_id,),
            ).fetchone()
        return (fila[0], fila[1]) if fila else None

    def cambiar_contrasena(self, usuario_id: int, hash_contrasena: str, sal: str) -> int | None:
        """Cambia la contraseña y sube la generación. Devuelve la nueva.

        Subir la generación es lo que tira por tierra las fichas viejas: la
        que llevaba la generación de antes deja de valer. Devuelve None si el
        usuario no existe.
        """
        with self._candado:
            cursor = self._conexion.execute(
                "UPDATE usuarios SET hash = ?, sal = ?, generacion = generacion + 1"
                " WHERE id = ?",
                (hash_contrasena, sal, usuario_id),
            )
            self._conexion.commit()
            if cursor.rowcount != 1:
                return None
            fila = self._conexion.execute(
                "SELECT generacion FROM usuarios WHERE id = ?",
                (usuario_id,),
            ).fetchone()
        return int(fila[0]) if fila else None

    def apuntar_uso(self, usuario_id: int) -> None:
        """Apunta que el usuario acaba de usar el servidor.

        Solo escribe si la marca anterior tiene más de MINUTOS_ENTRE_USOS:
        quien sincroniza diez veces seguidas no deja diez escrituras.
        """
        with self._candado:
            self._conexion.execute(
                "UPDATE usuarios SET ultimo_uso = datetime('now')"
                " WHERE id = ? AND (ultimo_uso IS NULL"
                " OR ultimo_uso < datetime('now', ?))",
                (usuario_id, f"-{MINUTOS_ENTRE_USOS} minutes"),
            )
            self._conexion.commit()

    def estado_de(self, usuario_id: int) -> tuple[int, bool, bool] | None:
        """(generacion, vetado, en_espera) del usuario, o None si no existe.
        Todo de una vez: es lo que se mira en cada petición con sesión."""
        with self._candado:
            fila = self._conexion.execute(
                "SELECT generacion, vetado, en_espera FROM usuarios WHERE id = ?",
                (usuario_id,),
            ).fetchone()
        return (int(fila[0]), bool(fila[1]), bool(fila[2])) if fila else None

    def aceptar(self, usuario: str) -> bool:
        """Saca la cuenta de la espera. Devuelve si existía."""
        with self._candado:
            cursor = self._conexion.execute(
                "UPDATE usuarios SET en_espera = 0 WHERE usuario = ?", (usuario,))
            self._conexion.commit()
        return cursor.rowcount == 1

    def rechazar(self, usuario: str) -> bool:
        """Borra una cuenta **en espera**. Una aceptada no se toca nunca por
        aquí: para echar a alguien que ya usa el servidor está el veto, que
        no tira nada. Devuelve si se borró."""
        with self._candado:
            self._conexion.execute(
                "DELETE FROM libros WHERE usuario_id IN"
                " (SELECT id FROM usuarios WHERE usuario = ? AND en_espera = 1)",
                (usuario,))
            cursor = self._conexion.execute(
                "DELETE FROM usuarios WHERE usuario = ? AND en_espera = 1", (usuario,))
            self._conexion.commit()
        return cursor.rowcount == 1

    def vetar(self, usuario: str, vetado: bool) -> bool:
        """Veta al usuario (o le quita el veto). Devuelve si existía.

        Se guarda el momento, no un sí o un no: así se sabe desde cuándo. Su
        libro no se toca: vetar es cerrarle la puerta, no tirar sus cosas.
        """
        with self._candado:
            cursor = self._conexion.execute(
                "UPDATE usuarios SET vetado = CASE WHEN ? THEN"
                " COALESCE(vetado, datetime('now')) ELSE NULL END"
                " WHERE usuario = ?",
                (1 if vetado else 0, usuario),
            )
            self._conexion.commit()
        return cursor.rowcount == 1

    def resumen_usuarios(self) -> list[dict]:
        """Quién tiene cuenta, cuándo la creó, cuándo la usó y cuánto subió.

        «subidas» es la revisión del libro: sube en uno con cada grabación.
        «tamano» son los bytes del libro. Lo de dentro no sale de aquí.
        Primero los que esperan a ser aceptados, para que se vean; luego
        los que lo usaron hace menos, y los que nunca, al final.
        """
        with self._candado:
            filas = self._conexion.execute(
                "SELECT u.usuario, u.creado, u.ultimo_uso,"
                " COALESCE(l.revision, 0),"
                " COALESCE(length(CAST(l.datos AS BLOB)), 0), u.vetado, u.en_espera"
                " FROM usuarios u LEFT JOIN libros l ON l.usuario_id = u.id"
                " ORDER BY u.en_espera DESC, u.ultimo_uso DESC NULLS LAST, u.usuario"
            ).fetchall()
        return [
            {
                "usuario": f[0],
                "creado": _momento_sqlite(f[1]),
                "ultimo_uso": _momento_sqlite(f[2]),
                "subidas": int(f[3]),
                "tamano": int(f[4]),
                "vetado": _momento_sqlite(f[5]),
                "en_espera": bool(f[6]),
            }
            for f in filas
        ]

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
                id         SERIAL PRIMARY KEY,
                usuario    TEXT NOT NULL UNIQUE,
                hash       TEXT NOT NULL,
                sal        TEXT NOT NULL,
                generacion INTEGER NOT NULL DEFAULT 0,
                creado     TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)
        # Para una base que ya venía de una versión anterior: el CREATE de
        # arriba no la toca y la columna nueva hay que añadirla aparte.
        self._ejecutar("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS generacion INTEGER NOT NULL DEFAULT 0
        """)
        self._ejecutar("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS ultimo_uso TIMESTAMPTZ
        """)
        self._ejecutar("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS vetado TIMESTAMPTZ
        """)
        self._ejecutar("""
            ALTER TABLE usuarios
            ADD COLUMN IF NOT EXISTS en_espera BOOLEAN NOT NULL DEFAULT false
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

    def crear_usuario(self, usuario: str, hash_contrasena: str, sal: str,
                      en_espera: bool = False) -> int:
        try:
            cursor = self._ejecutar(
                "INSERT INTO usuarios (usuario, hash, sal, en_espera)"
                " VALUES (%s, %s, %s, %s) RETURNING id",
                (usuario, hash_contrasena, sal, en_espera),
            )
        except psycopg.errors.UniqueViolation:
            raise UsuarioYaExiste(usuario)
        return int(cursor.fetchone()[0])

    def buscar_usuario(self, usuario: str) -> tuple[int, str, str, int] | None:
        cursor = self._ejecutar(
            "SELECT id, hash, sal, generacion FROM usuarios WHERE usuario = %s",
            (usuario,),
        )
        fila = cursor.fetchone()
        return (int(fila[0]), fila[1], fila[2], int(fila[3])) if fila else None

    def generacion_de(self, usuario_id: int) -> int | None:
        cursor = self._ejecutar(
            "SELECT generacion FROM usuarios WHERE id = %s",
            (usuario_id,),
        )
        fila = cursor.fetchone()
        return int(fila[0]) if fila else None

    def credenciales_por_id(self, usuario_id: int) -> tuple[str, str] | None:
        cursor = self._ejecutar(
            "SELECT hash, sal FROM usuarios WHERE id = %s",
            (usuario_id,),
        )
        fila = cursor.fetchone()
        return (fila[0], fila[1]) if fila else None

    def cambiar_contrasena(self, usuario_id: int, hash_contrasena: str, sal: str) -> int | None:
        """Cambia la contraseña y sube la generación. Devuelve la nueva."""
        cursor = self._ejecutar(
            "UPDATE usuarios SET hash = %s, sal = %s, generacion = generacion + 1"
            " WHERE id = %s RETURNING generacion",
            (hash_contrasena, sal, usuario_id),
        )
        fila = cursor.fetchone()
        return int(fila[0]) if fila else None

    def apuntar_uso(self, usuario_id: int) -> None:
        """Apunta que el usuario acaba de usar el servidor, como mucho una
        vez cada MINUTOS_ENTRE_USOS."""
        self._ejecutar(
            "UPDATE usuarios SET ultimo_uso = now()"
            " WHERE id = %s AND (ultimo_uso IS NULL"
            " OR ultimo_uso < now() - make_interval(mins => %s))",
            (usuario_id, MINUTOS_ENTRE_USOS),
        )

    def estado_de(self, usuario_id: int) -> tuple[int, bool, bool] | None:
        cursor = self._ejecutar(
            "SELECT generacion, vetado, en_espera FROM usuarios WHERE id = %s",
            (usuario_id,))
        fila = cursor.fetchone()
        return (int(fila[0]), fila[1] is not None, bool(fila[2])) if fila else None

    def aceptar(self, usuario: str) -> bool:
        cursor = self._ejecutar(
            "UPDATE usuarios SET en_espera = false WHERE usuario = %s", (usuario,))
        return cursor.rowcount == 1

    def rechazar(self, usuario: str) -> bool:
        """Borra una cuenta en espera; ver la versión de SQLite."""
        self._ejecutar(
            "DELETE FROM libros WHERE usuario_id IN"
            " (SELECT id FROM usuarios WHERE usuario = %s AND en_espera)",
            (usuario,))
        cursor = self._ejecutar(
            "DELETE FROM usuarios WHERE usuario = %s AND en_espera", (usuario,))
        return cursor.rowcount == 1

    def vetar(self, usuario: str, vetado: bool) -> bool:
        """Veta al usuario o le quita el veto; ver la versión de SQLite."""
        cursor = self._ejecutar(
            "UPDATE usuarios SET vetado = CASE WHEN %s THEN"
            " COALESCE(vetado, now()) ELSE NULL END"
            " WHERE usuario = %s",
            (vetado, usuario),
        )
        return cursor.rowcount == 1

    def resumen_usuarios(self) -> list[dict]:
        """Quién tiene cuenta y cuánto lo usa; ver la versión de SQLite."""
        cursor = self._ejecutar(
            "SELECT u.usuario, u.creado, u.ultimo_uso,"
            " COALESCE(l.revision, 0),"
            " COALESCE(octet_length(l.datos::text), 0), u.vetado, u.en_espera"
            " FROM usuarios u LEFT JOIN libros l ON l.usuario_id = u.id"
            " ORDER BY u.en_espera DESC, u.ultimo_uso DESC NULLS LAST, u.usuario"
        )
        return [
            {
                "usuario": f[0],
                "creado": f[1],
                "ultimo_uso": f[2],
                "subidas": int(f[3]),
                "tamano": int(f[4]),
                "vetado": f[5],
                "en_espera": bool(f[6]),
            }
            for f in cursor.fetchall()
        ]

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
