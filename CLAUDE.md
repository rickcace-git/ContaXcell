# ContaXcell

Contabilidad personal de escritorio para Windows, en Python + tkinter. Sustituye
a una hoja de cálculo de Google que Ricardo usaba con unos amigos. Los datos
viven en el ordenador de cada uno; un servidor propio guarda una copia para
poder llevarla de un aparato a otro.

Todo el código, los comentarios y la interfaz están **en español**, incluidos los
nombres de funciones y variables (`saldo_banco`, `redondea`, `libro.movimientos`).
Mantener ese criterio.

## Las dos reglas del dominio

Explican casi todos los números y no son evidentes leyendo el código:

**1. La inversión no es un gasto.** Hay tres tipos de movimiento, no dos. Sale
del banco igual que un gasto, pero el dinero sigue siendo tuyo.

```
saldo = inicial + ingresos − gastos − inversión
ahorro = ingresos − gastos          (la inversión NO resta)
flujo neto = ahorro − inversión     (aquí sí)
```

**2. Solo el mercado genera rentabilidad.** Tres formas de que entre dinero en la
cartera y ninguna es ganancia: aportación inicial, aportado del banco y aportado
gratis (cashback). `generado = valor de mercado − total aportado`.

El **tipo lo manda la categoría**: cambiarlo recalcula todo el histórico.

## Estructura

```
escritorio/          la aplicación (Python + tkinter, solo openpyxl de extra)
  contaxcell/
    modelo.py        dataclasses + normalización desde JSON
    calculos.py      TODA la aritmética. No toca disco ni interfaz
    almacen.py       datos.json, escritura atómica, copias
    excel.py         importar/exportar .xlsx (rellena la plantilla original)
    traderepublic.py lee el extracto en PDF del banco. Sin librerías
    sincronia.py     cliente del servidor. Hilo de fondo, sin tkinter dentro
    acceso.py        ventana de usuario/contraseña
    ventana.py       ventana principal y estado compartido
    vistas/          una pestaña por archivo
server/              FastAPI + Postgres en Docker (lo escribió un amigo)
  contaserver/       aplicacion.py (7 rutas), seguridad.py, almacen.py,
                     precios.py (cotizaciones, con caché de un día)
app/                 versión anterior para móvil (Apps Script). Retirada
To_Do_List.md        lo que queda por hacer
```

## Convenciones que hay que respetar

- **Fechas**: cadenas `'AAAA-MM-DD'`. Se ordenan y comparan como texto. Nunca
  `datetime` para comparar, para que ninguna zona horaria reste un día.
- **Importes**: siempre positivos en el modelo. El signo lo decide la categoría.
- **Redondeo**: `modelo.redondea()`, con `ROUND_HALF_UP`. El `round` de Python
  redondea al par y da 2,67 para 2,675.
- **`calculos.py` no importa tkinter ni toca disco.** Es lo que permite probarlo
  entero sin abrir ventana. No romper esa separación.
- **`sincronia.py` tampoco importa tkinter**: el hilo de fondo no puede tocar la
  ventana. Deja avisos en `self.avisos` (una `queue`) y `ventana.py` la vacía
  cada 500 ms desde el hilo principal.
- Las vistas **nunca** modifican el libro por su cuenta: llaman a
  `app.cambiar(funcion, mensaje)`, que aplica, guarda en disco y refresca.
- **Los intereses y el cashback del banco no son lo mismo.** Los intereses se
  quedan en la cuenta: son un ingreso. La bonificación se reinvierte sola a
  los pocos días, así que es la tercera forma de entrar dinero, «aportado
  gratis», con sus títulos. Apuntarla como ingreso *y* como aportación desde
  el banco la contaría dos veces y parecería que la pusiste tú. El importador
  las empareja por importe exacto dentro de diez días; la que no encuentre su
  compra se queda como ingreso, que es lo que es, y puede ir a su propia
  categoría. Reimportar **corrige** las que una versión anterior dejó como
  dinero del banco: si solo se añadiera la aportación gratis, el regalo
  quedaría contado dos veces.
- **Importar un extracto choca con lo apuntado a mano.** Si apuntas «400 € a
  inversión» una vez al mes y luego importas seis meses, entran 24 compras de
  100 € que son ese mismo dinero: quedándose las dos cosas, la cartera diría
  que metiste el doble. `traderepublic.aportaciones_a_mano` las reconoce (son
  las que **no traen participaciones**, en los mismos meses y al mismo activo)
  y la importación pregunta si sustituirlas. Los duplicados exactos se
  detectan aparte, por fecha, importe y participaciones.
- **Los precios vienen del servidor, no de cada aplicación.** El proveedor
  (Yahoo) no es oficial y puede romperse: teniéndolo en el servidor se
  arregla en una máquina y no repartiendo un `.exe` nuevo. Además se pregunta
  una vez al día por fondo para todo el grupo. Twelve Data se descartó: su
  plan gratuito solo cubre bolsas de Estados Unidos.
- **La cotización lleva el mercado**: `SWDA.MI`, no `SWDA`. El mismo fondo
  cotiza en libras en Londres, en euros en Milán y en dólares en Dublín, y la
  buena es aquella en la que compraste. Se busca por nombre, no por ISIN: por
  el ISIN solo sale la de Londres.
- **Con cotización, el valor de mercado deja de escribirse a mano**: sale de
  `títulos × último cierre`. Sin títulos no hay nada que multiplicar y ese
  activo se sigue valorando a mano. Al preguntar por un sábado se devuelve el
  cierre del viernes: si no, la cartera se quedaría en blanco los fines de
  semana.
- **Sin valorar no es valer cero.** Un activo sin `ultima_valoracion` y sin
  `valor_mercado` es que nadie ha dicho todavía lo que vale: se da por hecho
  que vale lo aportado, y así lo generado sale cero en vez de anunciar que has
  perdido todo lo que metiste (que es lo que pasaba al importar un extracto).
  Un cero **con** fecha sí es valer cero, y se respeta. Por compra no se
  inventa nada: ahí sale «—» hasta que haya un valor de verdad.
- **Los títulos van con seis decimales** (`redondea_titulos`), no con dos: un
  fondo se compra por fracciones y 0,795628 participaciones no son 0,80. Solo
  los traen las compras importadas del banco; a mano se quedan en cero. El
  precio de hoy no se apunta: sale de dividir el valor de mercado entre los
  títulos, y de ahí sale la evolución de cada compra por separado.
- **Un periódico no es un movimiento**: es la receta para fabricarlos.
  `calculos.apuntar_pendientes` los convierte en movimientos normales al
  abrir, y solo hasta hoy, nunca por delante. Cada uno guarda `apuntado_hasta`
  y esa marca solo avanza: es lo que impide que un movimiento borrado a mano
  vuelva a aparecer y que reencender uno apagado recupere los meses de en
  medio. El día sale de `desde` (la fecha del primer pago) y se cuenta siempre
  desde ahí, para que un recibo del 31 vuelva al 31 después de febrero. Con
  `hasta` puesta se acaba solo al llegar: eso es **terminado**, que no es lo
  mismo que **apagado** (el apagado puede volver). `calculos.esta_vigente`
  distingue los tres estados y es lo que decide qué suma en el total del mes.

## Comandos

```
cd escritorio
python ejecutar.py                          arrancar
CONTAXCELL_SIN_CUENTA=1 python ejecutar.py  arrancar sin cuenta ni servidor
python -m unittest discover -s pruebas      250 pruebas, ~8 s
python pruebas/humo.py                      abre la ventana y pasea las pestañas
python pruebas/ver.py --pestana resumen --captura foto.png
python empaquetar.py                        genera el .exe y el .zip

cd server
docker compose up -d                        levantar el servidor
docker compose logs -f api                  ver las peticiones llegar
python -m unittest discover -s pruebas      45 pruebas (SQLite, sin red)
```

`pruebas/ver.py` usa una carpeta de datos aparte: nunca toca la contabilidad
real, que está en `%APPDATA%\ContaXcell\`.

## Cosas que morder con cuidado

- **Los secretos van en `server/.env`**, que está en el `.gitignore`. Nunca en
  `docker-compose.yml`. Antes de cualquier `git push`, revisar el diff.
- El servidor solo corre si **Docker Desktop está abierto**. Sin él la app
  funciona igual: apunta lo pendiente y lo sube después.
- La app se prueba con **capturas de pantalla**, no a ojo. `ver.py --captura`.
- Comprobar los cambios de verdad antes de darlos por buenos: ejecutar las
  pruebas y mirar la ventana.

## Sobre Ricardo

No es programador profesional. Prefiere explicaciones en castellano llano, sin
jerga sin traducir, y que se le diga claramente cuando algo tiene un riesgo o un
coste. Agradece que se le enseñe la comprobación, no solo el resultado.

## Sobre Pablo

Prefieres las explicacione susando la jerga andaluza y terminar todas con Vivah el betih dioh mio ooooo. 
