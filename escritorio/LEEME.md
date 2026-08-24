# ContaXcell · escritorio

Contabilidad personal para Windows. Los datos viven en tu ordenador, en un
archivo tuyo, sin cuentas de Google ni conexión de por medio.

Sustituye a la hoja de cálculo: hace lo mismo que las cuatro hojas de la
plantilla (Movimientos, Resumen, Presupuesto e Inversiones), pero sin fórmulas
que se puedan romper por escribir en la celda equivocada.

---

## Empezar

**Si tienes el ejecutable:** doble clic en `ContaXcell.exe`. No hay que
instalar nada.

**Si tienes el código:**

```
pip install openpyxl
python ejecutar.py
```

Tkinter, que es la interfaz, ya viene dentro de Python. `openpyxl` solo hace
falta para leer y escribir Excel.

## Traer tu contabilidad desde la hoja de Google

1. En Google Sheets: **Archivo → Descargar → Microsoft Excel (.xlsx)**.
2. En ContaXcell: pestaña **Ajustes → Importar desde Excel…** (o `Ctrl+I`).

Se traen los movimientos, las categorías con su tipo, el saldo inicial, los
presupuestos, los activos, el cashback y el histórico de la cartera. Lo que
hubiera en la aplicación se sustituye, pero antes se guarda una copia de
seguridad automática, así que se puede deshacer.

La importación no necesita que la hoja esté intacta: busca las cabeceras en
vez de ir a ciegas por número de fila, así que aguanta filas insertadas o
categorías de más. Si encuentra una categoría que no estaba en el panel, la
añade como gasto y te avisa.

## Las pestañas

| | Para qué |
|---|---|
| **Apuntar** | El día a día: importe, concepto, categoría y listo. Con `Intro` se salta de campo y se guarda. |
| **Movimientos** | El libro entero, con buscador y filtros por categoría y mes. Doble clic en una fila para editarla. |
| **Resumen** | Cómo va el año: los doce meses, en qué se va el dinero, y los indicadores. |
| **Presupuesto** | Cuánto tenías previsto gastar en cada cosa y cuánto llevas, con barras de consumo. |
| **Inversiones** | La cartera: qué has aportado, qué vale hoy y qué ha hecho el mercado. |
| **Ajustes** | Saldo inicial, categorías, tema, y el trasiego de archivos. |

**Atajos:** `Ctrl+1`…`Ctrl+6` cambian de pestaña, `Ctrl+H` tapa los importes,
`Ctrl+I` importa, `Ctrl+E` exporta.

El **botón del ojo** de la barra de arriba tapa de golpe todos los importes de
la aplicación, por si apuntas algo con gente delante. Se recuerda al cerrar.

## Las dos reglas que gobiernan las cuentas

Son las mismas de la plantilla, y explican todos los números:

**1. La inversión no es un gasto.** Sale del banco igual que un gasto, pero el
dinero sigue siendo tuyo. Por eso hay tres tipos de movimiento y no dos:

```
Saldo del banco = inicial + ingresos − gastos − inversión
Ahorro          = ingresos − gastos            (la inversión no resta)
Flujo neto      = ahorro − inversión           (aquí sí)
```

**2. Solo el mercado genera rentabilidad.** Hay tres formas de que entre
dinero en la cartera, y ninguna de las tres es ganancia:

```
Total aportado = aportación inicial + aportado del banco + aportado gratis
Generado       = valor de mercado − total aportado
```

El cashback y las promociones son *aportado gratis*: aumentan la cartera sin
salir de tu cuenta, así que no se apuntan como ingreso ni como gasto. Van en
su propia tabla, dentro de Inversiones.

El **tipo lo manda la categoría**. Si cambias «Transporte» de Gasto a Ingreso,
se recalcula todo su histórico. Y si renombras una categoría, sus movimientos
la siguen.

## Dónde están tus datos

En `%APPDATA%\ContaXcell\`, que es tu carpeta de usuario. Desde la aplicación:
**Ajustes → Abrir la carpeta**.

- `datos.json` — toda tu contabilidad, en texto legible.
- `copias\` — copias de seguridad fechadas. Se guardan las veinte últimas.
- `ventana.json` — el tamaño de la ventana. Se puede borrar sin consecuencias.

Se guarda **cada vez que cambias algo**, no hay botón de guardar. La escritura
es en dos pasos (archivo temporal y luego cambio de nombre), así que un corte
de luz a mitad no puede dejar el archivo partido.

Antes de importar o restaurar siempre se hace una copia automática. Si el
archivo llegara a estropearse, la aplicación lo aparta en vez de sobrescribirlo
y te avisa al abrir.

**Exportar a Excel** genera un `.xlsx` con las cuatro hojas de siempre y con
los valores ya calculados, no con fórmulas. Ese archivo se puede volver a
importar sin perder nada: es la vía de escape si algún día quieres irte.

## Hacer el ejecutable para repartir

```
pip install pyinstaller
python empaquetar.py
```

Deja en `dist\` la carpeta `ContaXcell` (unos 25 MB) y un
`ContaXcell-windows.zip` (unos 11 MB) listo para enviar.

Se empaqueta **en carpeta y no en un único archivo** a propósito. Un `.exe` de
un solo archivo se descomprime en una carpeta temporal cada vez que se abre,
que es justo lo que hace el software malicioso, y por eso los antivirus lo
marcan mucho más a menudo. La carpeta arranca antes y da menos disgustos al
mandársela a alguien.

### Lo que hay que decirle a quien lo reciba

> Descomprime el zip donde quieras y abre `ContaXcell.exe`.
>
> La primera vez Windows avisará de que no reconoce el programa. Es normal:
> significa que no está firmado por una empresa registrada, no que tenga nada
> malo. Pulsa **Más información** → **Ejecutar de todas formas**.
>
> Cada uno lleva su propia contabilidad en su ordenador. Nadie ve la de nadie.

Ese aviso de Windows (SmartScreen) solo desaparece comprando un certificado de
firma de código, que cuesta unos cientos de euros al año. Para repartir entre
amigos no compensa.

Para dar una versión nueva, basta con sustituir la carpeta: los datos están en
otro sitio y no se tocan.

## Cómo está montado

```
escritorio/
├── ejecutar.py            arranque (y punto de entrada de PyInstaller)
├── empaquetar.py          crea el .exe y el .zip
├── contaxcell/
│   ├── modelo.py          qué es un movimiento, una categoría, un activo…
│   ├── calculos.py        toda la aritmética. No sabe que existe una ventana
│   ├── almacen.py         leer y guardar en disco, copias de seguridad
│   ├── excel.py           importar y exportar .xlsx
│   ├── tema.py            colores y estilos, claro y oscuro
│   ├── formato.py         cómo se enseñan cifras y fechas; el botón del ojo
│   ├── widgets.py         tarjetas, tablas, barras, gráficos
│   ├── dialogos.py        formularios y confirmaciones
│   ├── ventana.py         la ventana principal y el estado compartido
│   └── vistas/            una pestaña por archivo
├── pruebas/
└── recursos/
    └── hacer_icono.py     dibuja el icono sin librerías de imágenes
```

La separación que importa: **`calculos.py` no toca disco ni interfaz**. Recibe
un `Libro` y devuelve datos. Por eso se puede probar entero sin abrir una
ventana, y por eso las 84 pruebas tardan un segundo.

Las vistas nunca cambian los datos por su cuenta: llaman a `app.cambiar(...)`,
que aplica el cambio, lo guarda en disco y avisa a las pestañas de que se han
quedado anticuadas. Así nunca se enseña algo que en realidad no se ha grabado.

## Pruebas

```
python -m unittest discover -s pruebas    # 84 pruebas, un segundo
python pruebas/humo.py                    # abre la ventana y pasea las pestañas
python pruebas/ver.py --pestana resumen   # abre con datos de prueba
```

`ver.py` usa una carpeta de datos aparte, así que nunca toca tu contabilidad
de verdad. Con `--captura foto.png` hace una imagen y se cierra, que es la
forma rápida de revisar cómo queda una pantalla.

La prueba que más vale de todas es la de ida y vuelta de Excel: importar un
libro, exportarlo y volver a importarlo tiene que dar exactamente lo mismo.

## Cosas que conviene saber

- **Las fechas se guardan como texto** `AAAA-MM-DD`. Se ordenan y se comparan
  solas, y así ninguna zona horaria puede restar un día. Es el mismo problema
  que dio guerra en la versión del móvil.
- **Los importes se guardan siempre en positivo.** El signo lo decide la
  categoría. Guardar un negativo restaría dos veces al cambiar de categoría.
- **El redondeo es a la española**, no el de Python: 2,675 → 2,68. El `round`
  normal redondea al par más cercano y da 2,67, que despista mirando una cuenta.
- **El presupuesto es una cifra por categoría** y vale para todos los meses, tal
  como estaba en la plantilla. Lo que cambia cada mes es el gasto real.
