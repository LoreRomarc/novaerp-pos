# NovaERP · despliegue oficial recomendado

Para operación multisucursal se recomienda **Render de pago** con PostgreSQL administrado: la aplicación y la base permanecen en la nube, se realizan copias de seguridad y ninguna sucursal depende del computador de otra. Un hosting compartido de Hostinger no es adecuado para este ERP; si se usa Hostinger debe ser un VPS administrado, que exige mantenimiento de servidor.

## 1. Antes de publicar

1. Termine las pruebas con la guía `DESPLIEGUE_GRATUITO_PASO_A_PASO.md`.
2. Haga una copia de la base actual desde el proveedor de pruebas.
3. Cree un repositorio privado oficial de GitHub y configure el remoto:

```bash
cd /c/Users/User/novaerp-pos
git remote add produccion https://github.com/USUARIO/novaerp-produccion.git
git push produccion HEAD:main
```

Reemplace `USUARIO` por la cuenta/organización propietaria. Nunca suba `.env`, contraseñas ni archivos de respaldo al repositorio.

## 2. Crear producción en Render

1. En Render pulse **New → PostgreSQL**. Elija un plan persistente, una región próxima a los usuarios y anote sólo el nombre, no la contraseña.
2. Pulse **New → Web Service**, conecte el repositorio oficial y elija `main`.
3. Configure los mismos comandos de prueba:

```text
Build Command: bash build.sh
Start Command: gunicorn config.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

4. En **Environment**, enlace `DATABASE_URL` a la nueva PostgreSQL interna y cree/configure estas variables:

```text
DJANGO_SECRET_KEY=<Generate en Render>
DJANGO_DEBUG=False
DJANGO_USE_WHITENOISE=True
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_HSTS_SECONDS=31536000
DJANGO_HSTS_PRELOAD=True
POSTGRES_CONN_MAX_AGE=60
PYTHON_VERSION=3.12.7
```

5. Cree el primer superusuario desde **Shell**:

```bash
python manage.py createsuperuser
```

6. Si importa datos de prueba, realice esa migración mediante un respaldo PostgreSQL y nunca copiando `db.sqlite3`.

## 3. Dominio y seguridad

1. Compre o use el dominio oficial.
2. En Render → Web Service → **Custom Domains**, agregue el dominio.
3. En el proveedor DNS cree exactamente el registro que Render solicita.
4. Espere que Render emita el certificado HTTPS y compruebe el candado del navegador antes de ingresar usuarios.
5. Si usa un dominio personalizado, cree una versión nueva del conector de impresión que autorice ese dominio. El conector no se debe abrir a cualquier página web, porque su función es enviar documentos a una impresora local.

## 4. Impresión para cada sucursal

Cada equipo de caja requiere instalar una vez el ejecutable `NovaERP_Print_Connector.exe`, configurar su controlador Windows con papel de 58 mm y elegir la impresora desde NovaERP. Después del primer inicio Windows lo ejecuta automáticamente; el cajero sólo usa el POS.

## 5. Operación y mantenimiento

- Todo cambio de código se publica con `git push produccion HEAD:main`; Render crea el despliegue y ejecuta las migraciones del proyecto.
- Antes de actualizar, haga respaldo de PostgreSQL desde Render.
- Revise los logs del Web Service después de cada despliegue.
- Mantenga una cuenta superadministradora de contingencia y no la use como cajero diario.
- Haga pruebas controladas de venta, anulación, cambio, crédito, traslado y cierre de caja antes de cambios grandes.
