# El servidor de sincronización

La aplicación de escritorio funciona sola y sin conexión, como siempre. Este
servidor añade lo único que le faltaba: una cuenta con usuario y contraseña
donde guardar una copia del libro, para poder llevarlo de un ordenador a otro.

El servidor no calcula nada ni mira el libro por dentro: recibe el mismo JSON
que la aplicación guarda en `datos.json` y lo devuelve tal cual. Toda la
lógica de las cuentas sigue viviendo en el escritorio.

## Cómo funciona la sincronización

Cada libro guardado lleva un número de **revisión** que sube en uno con cada
grabación. Quien sube tiene que decir de qué revisión partía:

- Si coincide con la del servidor, se graba y la revisión sube.
- Si no coincide (alguien grabó antes desde otro sitio), el servidor contesta
  **409** con su estado actual, y es el cliente quien decide cómo juntar las
  dos versiones. El servidor nunca machaca nada en silencio.

La comprobación y la grabación van en una sola sentencia SQL, así que dos
subidas a la vez no pueden ganar las dos.

## La API

| Ruta | Qué hace |
|---|---|
| `GET /api/salud` | Contesta `{"estado": "bien"}` si está vivo. |
| `POST /api/cuentas/registro` | Crea la cuenta. Cuerpo: `{"usuario", "contrasena"}`. Devuelve `{"token", "usuario"}`. |
| `POST /api/cuentas/entrar` | Entra con usuario y contraseña. Devuelve `{"token", "usuario"}`. |
| `GET /api/libro` | El libro guardado: `{"revision", "libro"}`. Revisión 0 y libro nulo si nunca se subió nada. |
| `PUT /api/libro` | Sube el libro. Cuerpo: `{"revision_base", "libro"}`. Devuelve `{"revision"}`, o 409 con el estado del servidor. |
| `GET /api/precios/buscar?q=` | Busca la cotización de un fondo. Devuelve `{"encontrados": [{"simbolo", "nombre", "bolsa", "moneda", "pais"}]}`. |
| `GET /api/precios?simbolo=&desde=` | Los cierres diarios: `{"simbolo", "cotizaciones": [{"fecha", "precio", "moneda"}]}`. |

Todas menos `salud` y las dos de cuentas piden la cabecera
`Authorization: Bearer <token>`.

### Por qué los precios están aquí

**No hace falta ninguna clave.** Los precios se sacan de Yahoo, que no la
pide. Aun así están aquí y no en cada aplicación, por tres razones:

1. **Yahoo no es una API oficial y puede romperse cualquier día.** Estando
   aquí se arregla en una máquina; estando dentro del `.exe` habría que
   repartir un ejecutable nuevo a todo el mundo.
2. **Se pregunta una vez al día por fondo, para todo el grupo.** Ocho amigos
   abriendo la ventana cinco veces al día son 120 peticiones al servidor y
   tres viajes a internet, uno por fondo.
3. **El histórico se acumula en un sitio.** Quien entre mañana se encuentra
   los precios de todo el año ya guardados.

Se probó antes con [Twelve Data](https://twelvedata.com), que sí es oficial
y con contrato, pero su plan gratuito **solo cubre bolsas de Estados
Unidos**: cualquier fondo europeo contesta «available starting with the Grow
plan», y eso son 29 dólares al mes. El cliente está aislado en una clase con
dos métodos (`buscar` e `historico`), así que volver a un proveedor con clave
sería reescribir esa clase y poner la clave en `.env`, no dentro del
ejecutable.

Si el proveedor se cae no falla nada: se sirve el último precio guardado en
vez de dar un error. Para una cartera, el precio de ayer vale mucho más que
una pantalla en blanco.

Un aviso: el mismo fondo cotiza en varias bolsas y monedas. El iShares Core
MSCI World sale en libras en Londres, en euros en Milán y en dólares en
Dublín. Por eso hay que elegir la cotización buena una vez por fondo, y la
buena es aquella en la que compraste.
El token dura treinta días; después hay que volver a entrar. Las contraseñas
se guardan pasadas por scrypt con sal por usuario: en la base de datos nunca
hay una contraseña.

## Probar en local

Las pruebas no necesitan ni Docker ni Postgres: usan SQLite en memoria.

```
cd server
pip install -r requirements-dev.txt
python -m unittest discover -s pruebas
```

Para levantar el servidor entero en local, con su Postgres:

```
cd server
docker compose up -d
curl http://localhost:8000/api/salud
```

También se puede arrancar la API suelta sin base de datos
(`uvicorn contaserver.aplicacion:app`): usa SQLite en memoria y avisa de que
los datos no sobreviven a un reinicio. Vale para trastear, no para usar.

## Desplegar en un EC2

1. Una máquina pequeña con Docker llega de sobra (una `t3.micro` va bien).
   Instalar Docker con el plugin de compose:

   ```
   sudo apt install docker.io docker-compose-v2    # Ubuntu/Debian
   sudo usermod -aG docker $USER                   # y volver a entrar
   ```

2. Copiar la carpeta `server/` a la máquina (con `scp -r` o clonando el
   repositorio).

3. **Cambiar los secretos** en `docker-compose.yml` antes del primer
   arranque:

   - `CONTAXCELL_SECRETO`: generar uno con `openssl rand -hex 32`. Es lo que
     firma las sesiones. Si no se pone, el servidor arranca igualmente con
     uno aleatorio, pero avisa: cada reinicio cerraría la sesión de todo el
     mundo.
   - `POSTGRES_PASSWORD` y su copia dentro de `CONTAXCELL_BASE_DATOS`
     (tienen que coincidir).

4. Arrancar:

   ```
   cd server
   docker compose up -d
   ```

5. Abrir el puerto: en el *security group* de la instancia, una regla de
   entrada TCP al puerto **8000** (o solo desde las IP que interesen). La
   base de datos no se publica: solo la ve la API por la red interna de
   compose.

6. Comprobar que respira:

   ```
   curl http://LA-IP-DE-LA-MAQUINA:8000/api/salud
   ```

Con `restart: unless-stopped` los dos contenedores vuelven a levantarse solos
si la máquina se reinicia. Para actualizar el servidor: copiar el código
nuevo y `docker compose up -d --build`; los datos no se tocan, viven en el
volumen.

Si el servidor va a estar expuesto a Internet de verdad, conviene ponerle
HTTPS delante (un Caddy o un nginx con certificado); tal cual, el tráfico va
en claro por el puerto 8000.

## Copias de seguridad de la base de datos

Los datos viven en el volumen `datos_postgres`. Borrar los contenedores no
los toca; solo `docker volume rm` los borraría.

La copia buena es un volcado de Postgres, que se puede hacer con el servidor
en marcha:

```
docker compose exec db pg_dump -U contaxcell contaxcell > copia-$(date +%F).sql
```

Y para restaurarla sobre una base recién levantada:

```
docker compose exec -T db psql -U contaxcell contaxcell < copia-2026-08-24.sql
```

Una línea en el cron de la máquina lo deja hecho cada noche:

```
0 4 * * * cd /home/ubuntu/server && docker compose exec -T db pg_dump -U contaxcell contaxcell > /home/ubuntu/copias/contaxcell-$(date +\%F).sql
```

Conviene llevarse las copias fuera de la máquina de vez en cuando (a un S3,
o simplemente un `scp` al ordenador de casa). Una copia que vive en el mismo
disco que el original solo protege a medias.

## Cómo está montado

```
server/
├── contaserver/
│   ├── aplicacion.py     las siete rutas de la API
│   ├── precios.py        cotizaciones: proveedor y caché
│   ├── almacen.py        guardar y leer: SQLite (pruebas) y Postgres (producción)
│   └── seguridad.py      contraseñas (scrypt) y fichas de sesión (HMAC)
├── pruebas/              sin red y sin Docker, con SQLite en memoria
├── Dockerfile            la imagen de la API
└── docker-compose.yml    la API y su Postgres
```

La separación que importa: `aplicacion.py` no sabe qué base de datos tiene
debajo. Habla con un almacén de cuatro métodos, y por eso las pruebas corren
en un segundo con SQLite mientras producción usa Postgres.
