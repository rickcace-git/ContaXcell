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
| `POST /api/cuentas/registro` | Crea la cuenta. Cuerpo: `{"usuario", "contrasena"}` y, si el servidor pide código, `"codigo"`. Devuelve `{"token", "usuario"}`. |
| `POST /api/cuentas/entrar` | Entra con usuario y contraseña. Devuelve `{"token", "usuario"}`. |
| `POST /api/cuentas/contrasena` | Cambia la contraseña. Cuerpo: `{"contrasena_actual", "contrasena_nueva"}`. Devuelve `{"token"}`, uno nuevo. |
| `GET /api/libro` | El libro guardado: `{"revision", "libro"}`. Revisión 0 y libro nulo si nunca se subió nada. |
| `PUT /api/libro` | Sube el libro. Cuerpo: `{"revision_base", "libro"}`. Devuelve `{"revision"}`, o 409 con el estado del servidor. |

El libro y el cambio de contraseña piden la cabecera
`Authorization: Bearer <token>`. El token dura treinta días; después hay que
volver a entrar. Las contraseñas se guardan pasadas por scrypt con sal por
usuario: en la base de datos nunca hay una contraseña.

Los errores que puede devolver, todos con el motivo en español en `detail`:

| Código | Cuándo |
|---|---|
| 401 | Falta el token, no vale, ha caducado, o usuario/contraseña incorrectos. |
| 403 | Falta el código de invitación (o no es el bueno), o la contraseña actual no es la que es. |
| 409 | El usuario ya está cogido, o la revisión del libro va desfasada. |
| 422 | El cuerpo no cuadra: falta algo, o el usuario o la contraseña no cumplen las medidas. |
| 429 | Demasiados intentos seguidos. Hay que esperar un rato. |

### Cambiar la contraseña cierra las demás sesiones

Cada usuario lleva un contador de *generación* que sube al cambiar la
contraseña, y el token guarda dentro la generación con la que se emitió. Al
cambiarla, todos los tokens de antes dejan de valer de golpe (los de los otros
ordenadores también) y hay que volver a entrar. Es lo que permite echar a la
calle una sesión que se haya quedado en un sitio donde no debía.

### Los intentos se cuentan

- Entrar: diez fallos por cuarto de hora, contados por IP y también por
  nombre de usuario, cada uno por su lado. Al pasarse, **429** hasta que la
  ventana corra. La cuenta se borra al acertar la contraseña.
- Registrarse: cinco intentos por hora y por IP, acierten o no.
- Los cambios de contraseña con la actual equivocada cuentan igual.

El corte va **antes** de amasar la contraseña, así que a quien está bloqueado
el servidor no le dedica ni un scrypt.

### El nombre de usuario se normaliza

Se pasa a minúsculas, se le quitan los espacios de los lados y las tildes se
juntan en un solo carácter (Unicode NFC). Así «Ana », «ana» y «ANA» son la
misma cuenta, y «josé» escrito de las dos maneras que permite Unicode también.
Los nombres con caracteres de control o invisibles se rechazan con un 422.

**Aviso al actualizar desde una versión anterior:** las cuentas creadas antes
con mayúsculas o con tildes escritas de la otra manera pueden dejar de
encontrarse al entrar. Son un puñado y un servidor de casa: lo más rápido es
volver a crearlas (el libro se sube otra vez desde el escritorio).

**Aviso al actualizar, otro:** el formato del token ha cambiado, así que los
tokens antiguos dan 401 y todo el mundo tiene que volver a entrar una vez. No
se pierde nada: los libros siguen donde estaban.

### Código de invitación

Si `CONTAXCELL_CODIGO_REGISTRO` tiene algo, para crear una cuenta hay que
mandar ese mismo texto en el campo `codigo`; si no, el registro contesta
**403**. Vacío o sin poner, el registro queda abierto a cualquiera que
conozca la dirección. Para un servidor personal en Internet, conviene
ponerlo.

## Probar en local

Las pruebas no necesitan ni Docker ni Postgres: usan SQLite en memoria.

```
cd server
pip install -r requirements-dev.txt
python -m unittest discover -s pruebas
```

Para levantar el servidor entero en local, con su Postgres y en HTTP a secas
(en el ordenador de casa no hace falta más):

```
cd server
cp .env.ejemplo .env      # y rellenar CONTAXCELL_CLAVE_DB y CONTAXCELL_SECRETO
docker compose up -d
curl http://localhost:8000/api/salud
```

El puerto 8000 se abre solo en `127.0.0.1`, así que se ve desde la propia
máquina y de ningún otro sitio. Eso es a propósito y se explica más abajo.

También se puede arrancar la API suelta sin base de datos
(`uvicorn contaserver.aplicacion:app`): usa SQLite en memoria y avisa de que
los datos no sobreviven a un reinicio. Vale para trastear, no para usar.

## Desplegar en un EC2, con HTTPS

En Internet el tráfico va cifrado y punto: por ahí pasan las contraseñas. El
compose trae un **Caddy** que saca el certificado de Let's Encrypt él solo y
lo renueva sin que nadie se acuerde. Lo único que hace falta es un dominio.

1. Una máquina pequeña con Docker llega de sobra (una `t3.micro` va bien).
   Instalar Docker con el plugin de compose:

   ```
   sudo apt install docker.io docker-compose-v2    # Ubuntu/Debian
   sudo usermod -aG docker $USER                   # y volver a entrar
   ```

2. Copiar la carpeta `server/` a la máquina (con `scp -r` o clonando el
   repositorio).

3. **Apuntar un dominio a la máquina**: un registro `A` con la IP pública de
   la instancia (conviene que sea una IP elástica, para que no cambie al
   reiniciar). Sin dominio no hay certificado.

4. Rellenar el `.env` (`cp .env.ejemplo .env`):

   - `CONTAXCELL_CLAVE_DB`: `openssl rand -hex 16`.
   - `CONTAXCELL_SECRETO`: `openssl rand -hex 32`. Es lo que firma las
     sesiones y **tiene que tener 32 caracteres o más**; si es más corto el
     servidor no arranca y dice por qué. Si no se pone nada, arranca con uno
     aleatorio pero avisa: cada reinicio cerraría la sesión de todo el mundo.
   - `CONTAXCELL_DOMINIO`: el dominio del paso anterior.
   - `CONTAXCELL_CODIGO_REGISTRO`: algo inventado, para que nadie que dé con
     la dirección se cree una cuenta. Se lo pasas a quien tenga que entrar.

5. Arrancar, esta vez pidiendo el perfil del HTTPS:

   ```
   cd server
   docker compose --profile https up -d
   ```

   Sin `--profile https` arranca solo la API y la base de datos, en local.

6. Abrir los puertos: en el *security group* de la instancia, entrada TCP a
   **80** y **443**. El **8000 no se abre nunca**: la API solo escucha en
   `127.0.0.1` y quien tiene que llegar de fuera lo hace por el Caddy. La
   base de datos tampoco se publica: solo la ve la API por la red interna.

   > Esto no es una preferencia, es una condición. La API arranca con
   > `--proxy-headers`, o sea que se cree la cabecera que dice de qué IP
   > viene cada petición (la necesita para contar los intentos de cada uno).
   > Si el 8000 estuviera abierto a Internet, cualquiera podría inventarse
   > esa cabecera y esquivar el contador cambiando de IP falsa cada vez. Por
   > eso el compose lo ata a `127.0.0.1`.

7. Comprobar que respira (la primera vez el certificado tarda unos segundos):

   ```
   curl https://EL-DOMINIO/api/salud
   ```

Con `restart: unless-stopped` los contenedores vuelven a levantarse solos si
la máquina se reinicia. Para actualizar el servidor: copiar el código nuevo y
`docker compose --profile https up -d --build`; los datos no se tocan, viven
en el volumen.

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
│   ├── aplicacion.py     las seis rutas de la API
│   ├── almacen.py        guardar y leer: SQLite (pruebas) y Postgres (producción)
│   ├── seguridad.py      contraseñas (scrypt) y fichas de sesión (HMAC)
│   └── limites.py        contar intentos para frenar a quien prueba a lo bruto
├── pruebas/              sin red y sin Docker, con SQLite en memoria
├── Dockerfile            la imagen de la API
├── Caddyfile             el HTTPS de delante (perfil `https`)
└── docker-compose.yml    la API, su Postgres y el Caddy
```

La separación que importa: `aplicacion.py` no sabe qué base de datos tiene
debajo. Habla con un almacén de unos pocos métodos, y por eso las pruebas
corren en un momento con SQLite mientras producción usa Postgres.
