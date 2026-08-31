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
  contaserver/       aplicacion.py (8 rutas), seguridad.py, almacen.py,
                     limites.py (frena los intentos a lo bruto)
app/                 versión anterior para móvil (Apps Script). Retirada
To_Do_List.md        lo que queda por hacer
```

## Convenciones que hay que respetar

- **Fechas**: cadenas `'AAAA-MM-DD'`. Se ordenan y comparan como texto. Nunca
  `datetime` para comparar, para que ninguna zona horaria reste un día.
- **Importes**: siempre positivos en el modelo. El signo lo decide la categoría.
  En la ventana no se pueden teclear letras ni signos raros: las casillas de
  número pasan por `widgets.solo_numeros`, igual que las de fecha. Solo el
  saldo inicial admite el menos, que se puede empezar en números rojos.
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
  La casilla «se repite» de Apuntar crea la regla a partir del apunte con
  `calculos.periodico_de`: ese movimiento **es** el primer pago, así que la
  marca nace ya en su fecha y no se rellena lo anterior. Sin eso, el gasto que
  acabas de escribir saldría dos veces.
- **El resumen se mira por tramos.** `calculos.resumen_periodo` parte el
  periodo en días (un mes suelto), meses (un año) o años (varios), y de ahí
  salen el gráfico y la tabla. Las medias van **siempre por mes** sean los
  tramos lo que sean: repartir tres años de gastos entre tres tramos daría un
  «gasto medio al mes» de diez mil euros, y entre treinta y un días, treinta
  euros. Por eso `meses_con_datos` se cuenta aparte, de una pasada por los
  movimientos, y no sumando tramos.
- **Una deuda no es dinero.** Que Fulanito te deba veinte euros no es tenerlos,
  así que las deudas no tocan el saldo ni el ahorro: son una libreta aparte.
  Lo que mueve el banco son los movimientos, y por eso cobrar o pagar una
  deuda **ofrece** apuntar uno en vez de fabricarlo solo: si pagaste tú la
  cena entera, ese gasto ya salió de tu cuenta y lo que te devuelven solo lo
  compensa; apuntarlo también lo contaría dos veces. Se devuelve a trozos
  (`devuelto`), y `calculos.pendiente_de` nunca baja de cero, que un pendiente
  negativo se leería como que ahora te deben a ti.

## Comandos

```
cd escritorio
python ejecutar.py                          arrancar
CONTAXCELL_SIN_CUENTA=1 python ejecutar.py  arrancar sin cuenta ni servidor
python -m unittest discover -s pruebas      348 pruebas, ~9 s (test_dialogos abre
                                            ventanas: en Mac/Linux, mejor correr
                                            los demás módulos sueltos)
python pruebas/humo.py                      abre la ventana y pasea las pestañas
python pruebas/ver.py --pestana resumen --captura foto.png
python empaquetar.py                        genera el .exe y el .zip

cd server
docker compose up -d                        levantar el servidor (solo en local)
docker compose --profile https up -d        producción: Caddy con certificado delante
docker compose logs -f api                  ver las peticiones llegar
python -m unittest discover -s pruebas      75 pruebas (SQLite, sin red)
```

`pruebas/ver.py` usa una carpeta de datos aparte: nunca toca la contabilidad
real, que está en `%APPDATA%\ContaXcell\`.

## Cosas que morder con cuidado

- **Los secretos van en `server/.env`**, que está en el `.gitignore`. Nunca en
  `docker-compose.yml`. Antes de cualquier `git push`, revisar el diff.
- **Cambiar la contraseña tira las sesiones de los demás ordenadores** (el
  token lleva una generación que sube con cada cambio; es lo que permite
  revocarlas). El servidor también corta a los pesados con un 429, y en
  producción el puerto 8000 solo escucha en la propia máquina: fuera se sale
  por Caddy con https. Los detalles, en `server/LEEME.md`.
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
