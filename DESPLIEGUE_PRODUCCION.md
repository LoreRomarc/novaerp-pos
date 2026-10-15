# NovaERP: despliegue profesional recomendado, paso a paso

Esta es la ruta recomendada para operar NovaERP de forma real entre varias
sucursales: **Render de pago para la aplicación + Render PostgreSQL de pago para
la base de datos**, ambos en la misma región. El equipo de cada caja sigue
siendo Windows; sólo abre el ERP con el navegador. No se instala Ubuntu ni
PostgreSQL en los computadores de las sucursales.

> Esta guía reemplaza la ruta de prueba gratuita. La prueba gratuita sirve para
> validar el sistema, pero no para ventas reales: sus servicios se suspenden y
> PostgreSQL gratuito vence. No suba datos reales hasta completar esta guía.

## 1. La respuesta corta: dónde queda la base de datos

Al publicar correctamente NovaERP, la base de datos PostgreSQL queda en un
servidor administrado de Render, en la nube. **No queda encendida en su PC, ni
en el PC de una sucursal.** Todos los computadores entran por Internet a una
sola aplicación y esta se conecta a una sola base central.

```text
PC de caja 1 ─┐
PC de caja 2 ─┼── HTTPS ──> NovaERP en Render ── red privada ──> PostgreSQL en Render
PC de fábrica ┘
```

Esto permite que una venta, traslado, caja o inventario se vea de inmediato en
la sede que corresponda. Si se apaga un computador de caja, los datos ya
guardados siguen en la nube. Lo que sí se necesita en cada sede es Internet.

### Qué se actualiza automáticamente y qué no

| Lo que cambia | ¿Llega solo a Render? | Qué debe hacer |
|---|---|---|
| Código (`.py`, HTML, CSS, JavaScript) | Sí, al hacer `git push` a la rama conectada | Esperar a que termine el deploy. |
| Estructura de la BD (campos, tablas) | Sí, si la migración fue creada y subida | Crear migración local, probarla, incluirla en el `git push`. |
| Datos creados en el ERP desplegado | Sí | Ya se guardan directamente en la BD de Render. |
| Datos creados sólo en su BD local | No | Debe capturarlos de nuevo en la nube o hacer una importación planificada. |
| Archivo de migración que no subió a Git | No | Nunca llegará al servidor. |

El archivo [build.sh](build.sh) ya ejecuta estas acciones en cada despliegue:

```bash
python manage.py collectstatic --noinput
python manage.py migrate --noinput
python manage.py cargar_catalogo_productos
python manage.py check --deploy
```

Por tanto, **no ejecute `makemigrations` en Render**. Hágalo en su proyecto de
Windows, pruébelo y suba tanto el código como los archivos de migración. Render
aplicará `migrate` sobre la base central sin borrar los datos existentes.

El cargador de catálogo también se ejecuta automáticamente. Sólo agrega los
productos y variantes faltantes definidos en
`apps/inventory/data/catalogo_productos.py`; nunca borra, cambia precios ni
reescribe SKU, códigos de barras o historial.

## 2. Por qué esta es la ruta recomendada

Para una empresa que quiere concentrarse en ventas, producción e inventario,
una base administrada es más segura que alojar PostgreSQL dentro de una VPS que
usted mismo tendría que actualizar, proteger, respaldar y reparar. Render
ofrece PostgreSQL administrado; sus bases de pago tienen recuperación a un
momento anterior (PITR) y exportaciones lógicas desde el panel. El periodo de
recuperación depende del plan del espacio de trabajo: actualmente 3 días en
Hobby y 7 días en Pro o superior. Revise siempre los valores actuales antes de
comprar: [copias y recuperación de Render](https://render.com/docs/postgresql-backups).

Render no tiene región en Colombia. Para sus sucursales, elija **Oregon, USA**
o la región de Estados Unidos que dé mejor resultado en sus pruebas, pero
mantenga *web* y *PostgreSQL* en exactamente la misma región. Render no permite
mover una base o servicio de región después de creado; para hacerlo hay que
migrarlos. Consulte las regiones disponibles antes de crear los servicios:
[regiones de Render](https://render.com/docs/regions).

### Cuándo elegir Hostinger VPS en su lugar

Hostinger VPS es una alternativa si ya cuenta con una persona técnica que se
responsabilice de Linux, actualizaciones de seguridad, firewall, PostgreSQL,
respaldos externos y recuperación ante fallos. Puede tener costo previsible,
pero es administración propia. Para su primera operación profesional
multisucursal, recomiendo Render administrado; reduce ese riesgo operativo.

## 3. Antes de comprar: deje lista su copia de código

Estas instrucciones se realizan una vez desde Windows.

1. Abra **Windows PowerShell**.
2. Copie y pegue exactamente:

   ```powershell
   cd C:\Users\User\novaerp-pos
   git status
   ```

3. Confirme que no aparezcan archivos privados como `.env`, `venv`,
   `staticfiles`, archivos `.sql` de respaldo ni contraseñas.
4. Compruebe que `.env` esté ignorado:

   ```powershell
   git check-ignore .env
   ```

   Si la terminal muestra `.env`, está protegido por `.gitignore`. Si no
   muestra nada, **no publique todavía**: agregue `.env` a `.gitignore` y
   confirme con el mismo comando.
5. Pruebe el proyecto y las migraciones localmente:

   ```powershell
   .\venv\Scripts\Activate.ps1
   python manage.py check
   python manage.py makemigrations --check --dry-run
   ```

   El último comando debe indicar que no hay cambios pendientes. Si usted hizo
   un cambio de modelo que aún no tiene migración, ejecute `python manage.py
   makemigrations`, pruebe `python manage.py migrate` localmente y vuelva a
   ejecutar la comprobación.

6. Publique sólo los cambios que ya probó en su repositorio de despliegue:

   ```powershell
   git add -A
   git status
   git commit -m "Preparar version de produccion"
   git push pruebas HEAD:main
   ```

   En este proyecto `pruebas` es su repositorio propio de Render. No utilice
   `git push origin` si `origin` pertenece al repositorio compartido de otra
   persona.

## 4. Crear la base PostgreSQL profesional

1. Entre a [Render Dashboard](https://dashboard.render.com/) con la misma
   cuenta que usa para la prueba.
2. Pulse **New +** y elija **PostgreSQL**.
3. Escriba como nombre: `novaerp-produccion-db`.
4. Elija una región, por ejemplo **Oregon**. Anótela: la aplicación deberá usar
   esa misma región.
5. Seleccione un plan de pago adecuado para comenzar. No seleccione `Free`.
6. Pulse **Create Database** y espere el estado **Available**.
7. Abra la base y entre a **Info**. No copie ni comparta públicamente sus URL,
   usuario o contraseña: son credenciales de la base.

La base queda creada antes que la aplicación para poder vincularla mediante la
red privada de Render. No necesita abrir puertos ni instalar PostgreSQL en
Windows.

## 5. Crear la aplicación web profesional

1. En Render pulse **New + → Web Service**.
2. Conecte su cuenta de GitHub si Render la solicita.
3. Seleccione el repositorio `jnstudiotech/novaerp-pruebas` (o el repositorio
   privado que usted haya destinado exclusivamente al despliegue).
4. En **Branch** seleccione `main`.
5. Escriba como nombre `novaerp-produccion`.
6. Elija **Python 3** como entorno y la misma región de la base.
7. Use estos comandos:

   | Campo de Render | Valor |
   |---|---|
   | Build Command | `bash build.sh` |
   | Start Command | `gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120` |
8. Seleccione una instancia web de pago. No use la instancia gratuita para una
   operación de caja.

### 5.1 Variables de entorno obligatorias

Dentro de la nueva aplicación abra **Environment** y agregue estas variables.
No las escriba en archivos del repositorio.

| Variable | Valor |
|---|---|
| `DATABASE_URL` | La **Internal Database URL** de `novaerp-produccion-db`. |
| `DJANGO_SECRET_KEY` | Pulse **Generate** si Render ofrece esa opción; de lo contrario use una clave aleatoria larga. |
| `DJANGO_DEBUG` | `False` |
| `DJANGO_USE_WHITENOISE` | `True` |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` |
| `DJANGO_HSTS_SECONDS` | `31536000` |
| `POSTGRES_CONN_MAX_AGE` | `60` |
| `PYTHON_VERSION` | `3.12.7` |

Para agregar `DATABASE_URL`, prefiera la opción de Render de enlazar una
variable desde la base de datos, si aparece. Eso evita copiar manualmente una
contraseña. Si no aparece, copie **Internal Database URL**, nunca la URL
externa, y péguela sólo en el campo secreto de `DATABASE_URL`.

Deje `DJANGO_ALLOWED_HOSTS` y `DJANGO_CSRF_TRUSTED_ORIGINS` sin configurar por
el momento si el proyecto ya obtiene el dominio de Render automáticamente. Los
agregará explícitamente en el siguiente paso cuando tenga su dominio real.

9. Pulse **Create Web Service**.
10. Abra **Events**. El primer despliegue termina bien únicamente cuando el
    último evento diga **Live**. En los logs debe verse que `migrate` terminó
    sin error.

## 6. Dominio empresarial y HTTPS

1. Compre el dominio donde prefiera (Hostinger puede vender el dominio aunque
   no use su VPS).
2. En Render abra `novaerp-produccion` → **Settings** → **Custom Domains**.
3. Escriba `erp.sudominio.com` y pulse para agregarlo.
4. Render mostrará exactamente el registro DNS que necesita. Abra el panel del
   proveedor del dominio, por ejemplo **Hostinger hPanel → Domains → DNS Zone**,
   y cree ese registro. No invente valores: copie los que Render muestra.
5. Vuelva a Render y espere a que el dominio sea verificado y HTTPS quede
   activo.
6. En **Environment** agregue o reemplace estos valores con su dominio real:

   ```text
   DJANGO_ALLOWED_HOSTS=erp.sudominio.com
   DJANGO_CSRF_TRUSTED_ORIGINS=https://erp.sudominio.com
   ```

7. Pulse **Save Changes** y espere el despliegue. Abra
   `https://erp.sudominio.com` y compruebe que aparece el candado HTTPS.

## 7. Primera instalación o paso desde pruebas

### Si es una instalación nueva

1. Abra la URL de producción.
2. Complete `/setup/` una sola vez: empresa, primera sucursal, primera caja y
   usuario superadministrador.
3. Guarde la contraseña en un gestor de contraseñas.
4. Después del setup, no vuelva a usar esa pantalla para modificar datos.
   Use los módulos de Administración del ERP.

### Si ya tiene datos de prueba y quiere conservarlos

No conecte a producción una base de prueba sin respaldarla primero. En la base
de prueba de Render, abra **Recovery** y cree/descargue un export lógico, o
use `pg_dump` desde un equipo seguro. Luego restaure únicamente sobre una base
de destino vacía. La restauración puede duplicar o destruir datos si se hace
sobre una base que ya tiene tablas con información. Para datos reales o si
tiene dudas, haga este traslado una vez con asistencia técnica y conserve una
copia sin modificar antes de empezar.

## 8. Actualizar NovaERP después de estar en producción

Este es el flujo normal para cada mejora. No necesita tocar la base a mano.

1. Haga el cambio en `C:\Users\User\novaerp-pos`.
2. Si cambió un `models.py`, cree la migración local:

   ```powershell
   python manage.py makemigrations
   python manage.py migrate
   ```

3. Pruebe el flujo afectado localmente.
4. Revise los archivos a publicar:

   ```powershell
   git status
   ```

5. Publique:

   ```powershell
   git add -A
   git commit -m "Explicar el cambio"
   git push pruebas HEAD:main
   ```

6. Abra Render → `novaerp-produccion` → **Events** y espere **Live**.
7. Pruebe el cambio en una cuenta de prueba antes de usarlo en caja.

Si el cambio de modelo trae una migración, `build.sh` ejecutará `migrate` en la
base de Render. Las ventas, cajas e inventario que ya existían se conservan;
una migración bien diseñada transforma la estructura, no reinicia la base.

**Nunca** borre o edite una migración que ya se aplicó en Render. Para corregir
una estructura cree una nueva migración. Antes de cambios grandes, exporte la
base desde **Recovery**.

## 9. Copias de seguridad y recuperación

La recuperación administrada no sustituye una copia independiente. Configure
ambas cosas:

1. En Render → `novaerp-produccion-db` → **Recovery**, confirme que la base es
   de pago y que aparece **Point-in-Time Recovery**.
2. Una vez por semana, pulse **Create export** y descargue el archivo a un
   disco seguro o almacenamiento de la empresa con acceso restringido.
3. Antes de una actualización grande, haga otro export manual.
4. Anote quién puede entrar a Render y active autenticación de dos pasos en esa
   cuenta.
5. Una vez antes de operar en serio, ensaye una restauración sobre una base de
   prueba nueva, nunca sobre la base viva.

Las bases de pago de Render tienen PITR y permiten exportaciones lógicas en su
panel; las bases gratuitas no ofrecen la misma recuperación. Consulte el
procedimiento actualizado: [PostgreSQL Recovery and Backups](https://render.com/docs/postgresql-backups).

## 10. Lector, impresora y sucursales

### Lector de código de barras USB

El lector va conectado al PC Windows de cada caja. Debe funcionar en modo
teclado (HID): al escanear escribe el código y normalmente envía Enter. No se
conecta a Render y no necesita una base instalada localmente.

### Impresora de tickets

Una aplicación alojada en la nube no puede controlar por sí sola una impresora
USB conectada a Windows. Para imprimir desde la nube se utiliza el navegador
de la caja, o se instala/integra un agente local de impresión si más adelante
se requiere impresión silenciosa. Mantenga instalado el driver de la impresora
en cada PC que vaya a imprimir.

### Varias sucursales

Todas usan una sola URL y una sola PostgreSQL central. No cree una base por
sucursal. Los permisos, la sucursal activa y las transacciones atómicas de
NovaERP son los que delimitan qué puede operar cada usuario.

## 11. Lista final antes de vender en producción

- [ ] La aplicación y PostgreSQL son planes de pago y están en la misma región.
- [ ] El dominio usa HTTPS y abre `https://erp.sudominio.com`.
- [ ] `DJANGO_DEBUG=False` está en Environment de Render.
- [ ] `DJANGO_SECRET_KEY` y `DATABASE_URL` existen sólo como secretos de Render.
- [ ] Hay un superadministrador con contraseña guardada de forma segura.
- [ ] Cada sucursal tiene caja, usuarios, permisos y prueba de apertura/cierre.
- [ ] Se probó venta, crédito, abono, devolución, traslado y recepción.
- [ ] Se probó lector e impresión en cada PC de caja.
- [ ] Existe al menos una exportación de PostgreSQL descargada fuera de Render.
- [ ] Sólo personas autorizadas tienen acceso a GitHub y Render.

## 12. Soporte: qué información guardar si algo falla

No copie contraseñas ni URLs de base. Guarde únicamente:

1. El nombre del servicio de Render.
2. La hora aproximada del error en Colombia.
3. Una captura del mensaje completo.
4. La sección **Logs** o **Events** del servicio, ocultando secretos si los
   hubiera.
5. El paso que estaba realizando: venta, cierre, traslado, despliegue, etc.

Con esos datos se puede diagnosticar el problema sin exponer la base de datos.
