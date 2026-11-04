# NovaERP · prueba gratuita en Render

Esta guía publica una copia de prueba accesible desde varias sucursales. No suba el archivo `.env`, la base de datos local, ni la carpeta `venv/`.

## 1. Publicar el código de prueba

Abra **Git Bash** dentro de `C:\Users\User\novaerp-pos` y ejecute:

```bash
git status
git add .
git commit -m "Preparar ticket POS de 58 mm"
git push pruebas HEAD:main
```

El último comando publica la rama actual en el repositorio de pruebas `jnstudiotech/novaerp-pruebas`, rama `main`. Render inicia el despliegue automáticamente cuando termina el `push`.

## 2. Crear o revisar los recursos en Render

1. Entre a [Render Dashboard](https://dashboard.render.com/) y abra el proyecto de pruebas.
2. Deben existir, en la **misma región**, estos dos recursos:
   - Base PostgreSQL: `novaerp-pruebas-db`.
   - Web Service: `novaerp-pruebas`.
3. En el Web Service, en **Settings**, confirme:
   - Branch: `main`.
   - Build Command: `bash build.sh`.
   - Start Command: `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120`.
4. En **Environment**, confirme estas variables. `DATABASE_URL` debe enlazar la base `novaerp-pruebas-db`; no copie contraseñas manualmente.

| Variable | Valor |
| --- | --- |
| `DATABASE_URL` | conexión interna de `novaerp-pruebas-db` |
| `DJANGO_SECRET_KEY` | **Generate** en Render |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_USE_WHITENOISE` | `True` |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` |
| `DJANGO_HSTS_SECONDS` | `31536000` |
| `DJANGO_HSTS_PRELOAD` | `True` |
| `POSTGRES_CONN_MAX_AGE` | `60` |
| `PYTHON_VERSION` | `3.12.7` |

5. Pulse **Manual Deploy → Deploy latest commit** sólo si el Auto-Deploy no inició por sí mismo. Espere el estado **Live** y abra la URL mostrada por Render.

El build ejecuta migraciones, recolecta archivos estáticos y carga maestros y catálogo de forma idempotente: los productos que ya existen no se duplican ni se reescribe el historial.

## 3. Primer ingreso

En Render abra **Shell** dentro del Web Service y ejecute una sola vez:

```bash
python manage.py createsuperuser
```

Ingrese usuario, correo (opcional) y contraseña. Entre a la URL pública con ese usuario y complete el asistente de empresa/sucursal/cajas si todavía no se ha hecho. La base PostgreSQL queda alojada en Render: no tiene que dejar un PC encendido para que las sucursales usen la aplicación.

## 4. Instalar la impresión en cada PC que tenga una caja

La aplicación web no puede controlar directamente una impresora física. Cada PC que imprima debe tener una vez el conector local de NovaERP.

1. Instale el controlador oficial de la impresora y confirme que imprime una página de prueba desde **Configuración de Windows → Impresoras y escáneres**.
2. En las preferencias del controlador configure papel continuo de **58 mm** de ancho. Use márgenes mínimos o cero si el controlador los permite.
3. Descargue `releases/NovaERP_Print_Connector.exe` desde el repositorio de pruebas y ejecútelo una sola vez. No requiere Python, terminal, `.bat` ni mantener abierta la carpeta del proyecto. Se registra para iniciar con la sesión de Windows.
4. Entre a NovaERP → **Configuración de tickets** desde ese mismo PC. Pulse actualizar impresoras, seleccione la impresora instalada, escriba `58` en ancho de papel y active **Impresión automática**.
5. Guarde y pulse **Imprimir prueba**. El ticket debe usar el ancho completo; si el driver deja bordes, ajuste los márgenes en Windows, no en NovaERP.

El conector de esta versión acepta `https://novaerp-pruebas.onrender.com`. Para un dominio definitivo se genera un conector de producción con ese dominio antes de entregar la versión oficial.

## 5. Comprobaciones antes de probar ventas reales

1. Cree una sucursal, caja y usuario de prueba.
2. Abra caja, registre una venta pequeña, compruebe stock, kardex y reporte.
3. Imprima el comprobante de prueba y una venta real de prueba.
4. Haga un traslado y acéptelo desde la sucursal destino.
5. Cierre caja y revise que el efectivo esperado coincida.

Render gratuito sirve para validación. Puede pausarse por inactividad y no es la opción final para operación comercial continua.
