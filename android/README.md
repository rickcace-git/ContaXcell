# ContaXcell para Android

Aplicación nativa en Kotlin y Jetpack Compose que conserva las reglas y el
formato de datos de ContaXcell de escritorio. Funciona primero contra el
almacenamiento privado del teléfono y sincroniza en segundo plano con el mismo
servidor de `server/` cuando hay una cuenta y conexión.

## Incluye

- Apunte rápido de ingresos, gastos e inversión, con fecha y activo opcionales.
- Conversión opcional del apunte en pago periódico, sin repetir el formulario.
- Libro de movimientos con búsqueda, filtros, edición y borrado.
- Resumen por mes, año o varios años, presupuesto mensual y métricas de ahorro.
- Cartera por activo, aportaciones, cashback, histórico de valoraciones y
  cotizaciones automáticas del mismo servidor.
- Pagos periódicos, categorías, temas claro/oscuro y ocultación de importes.
- Libreta de deudas: lo que te deben, lo que debes, pagos parciales, notas y
  saldo compensado por persona, sin alterar el saldo bancario por sí sola.
- Registro, inicio de sesión, cambio de contraseña y sincronización sin conexión.
- Importación y exportación de libros Excel mediante el selector de documentos
  de Android, sin pedir acceso general a los archivos del teléfono.
- Importación de extractos PDF de Trade Republic.

Los importes se guardan positivos y el tipo lo decide la categoría. La
inversión sale del banco pero no resta del ahorro; la rentabilidad es solo
`valor de mercado - total aportado`, igual que en escritorio.

## Abrir y compilar

1. Abre la carpeta `android/` en Android Studio.
2. Espera a que termine la sincronización de Gradle.
3. Para generar un APK de desarrollo, usa **Build → Build APK(s)** o:

   ```bash
   ./gradlew assembleDebug
   ```

El APK queda en `app/build/outputs/apk/debug/app-debug.apk`. La aplicación
admite Android 8.0 (API 26) o posterior. Esta primera fase se verifica con la
compilación y las pruebas unitarias; no requiere arrancar un emulador.

## Servidor

En la pantalla de acceso se indica la URL completa del servidor, por ejemplo
`https://cuentas.ejemplo.es`. En un dispositivo real, `localhost` apunta al
propio teléfono, no al ordenador. Para un servidor de desarrollo en la misma
red se usa la IP local del ordenador, y en producción siempre se recomienda
HTTPS.

Los datos del libro se guardan en el espacio privado de la aplicación con
escritura atómica y copias fechadas. Cerrar sesión no borra el libro local.
