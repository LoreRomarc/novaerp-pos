# NovaERP: despliegue oficial de pago en Hostinger VPS

Esta guía es para operar el ERP real con varias sucursales y una base de datos
central. El computador de la empresa continúa siendo **Windows**: no debe
instalar Ubuntu allí. Ubuntu estará solamente en la VPS remota de Hostinger y
los comandos se copian en la consola web del navegador.

> Primero complete las pruebas de `DESPLIEGUE_GRATUITO_PASO_A_PASO.md`.
> Antes de tocar el servidor real, realice y compruebe un respaldo.

## 1. Qué comprar

1. Compre una **VPS** de Hostinger, no hosting compartido. Para varias cajas,
   empiece con al menos 2 GB de RAM; puede subir de plan después.
2. Compre un dominio, por ejemplo `miempresa.com`, en Hostinger o en cualquier
   proveedor.
3. En Hostinger abra **hPanel → VPS**, pulse **Setup**, elija **Ubuntu 24.04
   LTS** y una ubicación cercana a Colombia si está disponible.

Hostinger explica estas pantallas en su [guía de compra de VPS](https://www.hostinger.com/support/1583582-how-and-why-to-purchase-vps-hosting-at-hostinger/).

## 2. Separar el repositorio de despliegue del compartido

No tiene que “salirse” del proyecto compartido. Una rama es una línea local de
trabajo y un remoto es el lugar de GitHub al que se publica el código. En este
equipo:

- `origin` es el repositorio compartido;
- `pruebas` es su repositorio propio `jnstudiotech/novaerp-pruebas`;
- `dev` es la rama compartida;
- `despliegue-pruebas` es su rama privada de despliegue.

En PowerShell ejecute:

```powershell
cd C:\Users\User\novaerp-pos
git branch --show-current
git remote -v
git switch despliegue-pruebas
```

Si el último comando indica que la rama no existe, créela sólo una vez:

```powershell
git switch -c despliegue-pruebas
```

Para publicar código hacia su repositorio sin modificar el de otra persona:

```powershell
git add -A
git status
git commit -m "Preparar NovaERP para producción"
git push -u pruebas HEAD:main
```

No ejecute `git push origin ...`: ese comando enviaría cambios al repositorio
compartido. Para volver al trabajo compartido después use `git switch dev`.
Cambiar de rama no borra ni publica archivos. Antes de `git add -A`, confirme
con `git status` que no aparezcan `.env`, `venv`, `staticfiles` ni respaldos.

## 3. Abrir la consola del servidor

1. Entre a [hPanel](https://hpanel.hostinger.com/).
2. Abra **VPS** y pulse **Manage** sobre su servidor.
3. En **Overview**, copie la IP pública y guárdela.
4. Pulse **Web Console**. Si pide usuario escriba `root`; cuando escriba la
   contraseña no se mostrarán caracteres, lo cual es normal.

La [guía oficial de la consola web](https://www.hostinger.com/support/how-to-use-the-web-console-in-hostinger/) muestra estas pantallas.

En esa consola ejecute, una línea o bloque a la vez:

```bash
apt update
apt upgrade -y
apt install -y git nginx postgresql postgresql-contrib python3 python3-venv python3-pip python3-dev build-essential libpq-dev certbot python3-certbot-nginx ufw
adduser --disabled-password --gecos "" novaerp
usermod -aG www-data novaerp
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
```

Espere siempre a que vuelva a aparecer el cursor terminado en `#` antes de
pegar el bloque siguiente.

## 4. Permitir que la VPS lea el repositorio privado

En la consola de la VPS ejecute:

```bash
sudo -u novaerp mkdir -p /home/novaerp/.ssh
sudo -u novaerp ssh-keygen -t ed25519 -C "novaerp-vps" -f /home/novaerp/.ssh/id_ed25519 -N ""
sudo -u novaerp cat /home/novaerp/.ssh/id_ed25519.pub
```

Copie todo el resultado de la última línea, que empieza por `ssh-ed25519`.
Luego, en GitHub:

1. Abra `https://github.com/jnstudiotech/novaerp-pruebas`.
2. Pulse **Settings → Deploy keys → Add deploy key**.
3. Como título escriba `VPS NovaERP producción`.
4. Pegue la clave copiada, deje desmarcado **Allow write access** y pulse
   **Add key**.

Vuelva a la consola y descargue el proyecto:

```bash
sudo -u novaerp ssh-keyscan github.com >> /home/novaerp/.ssh/known_hosts
sudo -u novaerp git clone git@github.com:jnstudiotech/novaerp-pruebas.git /opt/novaerp-pos
chown -R novaerp:www-data /opt/novaerp-pos
```

Si su repositorio cambia de nombre, sustituya solamente
`jnstudiotech/novaerp-pruebas.git` por la URL de **GitHub → Code → SSH**.

## 5. Base de datos y archivo privado de configuración

Cree la base de datos. El primer comando pedirá una contraseña: use una larga
y única, y guárdela en un gestor de contraseñas.

```bash
sudo -u postgres createuser --pwprompt novaerp_app
sudo -u postgres createdb --owner=novaerp_app novaerp
```

Ahora cree el archivo privado:

```bash
mkdir -p /etc/novaerp
nano /etc/novaerp/novaerp.env
```

Pegue el siguiente contenido. Reemplace cada valor entre corchetes. Use el
subdominio real, por ejemplo `erp.miempresa.com`:

```text
DJANGO_SECRET_KEY=[clave_larga_aleatoria]
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=[erp.tudominio.com]
DJANGO_CSRF_TRUSTED_ORIGINS=https://[erp.tudominio.com]
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_HSTS_SECONDS=31536000
POSTGRES_DB=novaerp
POSTGRES_USER=novaerp_app
POSTGRES_PASSWORD=[contrasena_de_la_base]
POSTGRES_HOST=127.0.0.1
POSTGRES_PORT=5432
POSTGRES_CONN_MAX_AGE=60
```

Para generar el valor de `DJANGO_SECRET_KEY`, abra una segunda consola y ejecute:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(64))"
```

En `nano`, guarde con `Ctrl+O`, luego `Enter`, y salga con `Ctrl+X`. Proteja el
archivo:

```bash
chown root:novaerp /etc/novaerp/novaerp.env
chmod 640 /etc/novaerp/novaerp.env
```

Nunca suba este archivo a GitHub, WhatsApp o correo.

## 6. Instalar NovaERP

Ejecute estos comandos:

```bash
sudo -u novaerp bash -c 'cd /opt/novaerp-pos && python3 -m venv venv && venv/bin/python -m pip install --upgrade pip && venv/bin/pip install -r requirements.txt'
sudo -u novaerp env $(cat /etc/novaerp/novaerp.env | xargs) /opt/novaerp-pos/venv/bin/python manage.py migrate --noinput
sudo -u novaerp env $(cat /etc/novaerp/novaerp.env | xargs) /opt/novaerp-pos/venv/bin/python manage.py collectstatic --noinput
sudo -u novaerp env $(cat /etc/novaerp/novaerp.env | xargs) /opt/novaerp-pos/venv/bin/python manage.py check --deploy
```

El último comando debe finalizar sin problemas críticos. Una advertencia por
dominio antes de crear el DNS se resolverá en el siguiente paso.

## 7. Dominio, servicio web y HTTPS

### 7.1 DNS

En el proveedor donde compró el dominio cree un registro:

| Campo | Valor |
|---|---|
| Tipo | `A` |
| Nombre / Host | `erp` |
| Apunta a | La IP pública de la VPS |
| TTL | Automático o 300 |

Espere la propagación antes de activar HTTPS.

### 7.2 Servicio de NovaERP

El proyecto trae el servicio preparado. Ejecute:

```bash
cp /opt/novaerp-pos/deploy/novaerp.service /etc/systemd/system/novaerp.service
systemctl daemon-reload
systemctl enable --now novaerp
systemctl status novaerp --no-pager
```

Debe verse `active (running)`. Si no, copie el resultado de:

```bash
journalctl -u novaerp -n 80 --no-pager
```

### 7.3 Nginx

```bash
cp /opt/novaerp-pos/deploy/nginx-novaerp.conf /etc/nginx/sites-available/novaerp
nano /etc/nginx/sites-available/novaerp
```

Reemplace las dos apariciones de `erp.tudominio.com` por el dominio real.
Guarde con `Ctrl+O`, `Enter`, `Ctrl+X`; luego ejecute:

```bash
ln -s /etc/nginx/sites-available/novaerp /etc/nginx/sites-enabled/novaerp
rm -f /etc/nginx/sites-enabled/default
nginx -t
systemctl reload nginx
```

### 7.4 Certificado HTTPS

Cuando el DNS ya apunte a la VPS, ejecute cambiando dominio y correo:

```bash
certbot --nginx -d erp.tudominio.com -m tu-correo@empresa.com --agree-tos --no-eff-email
```

Si pregunta por redirigir HTTP a HTTPS, elija sí. Abra después
`https://erp.tudominio.com`: en la primera visita complete `/setup/` una sola
vez con empresa, sucursal inicial, caja y usuario administrador.

## 8. Lector, impresora y uso por sucursales

### Lector USB con cable

El lector se conecta al computador de cada caja, no a la VPS. Abra Bloc de
notas, escanee una etiqueta y confirme que el lector añade Enter al final. En
el POS haga clic en “Buscar o escanear” y escanee. No requiere programa extra:
funciona como un teclado. También puede usarse en los campos “Buscar o
escanear” de inventario, traslados, devoluciones y precios.

### Impresora

Una VPS remota no puede imprimir directamente en una impresora USB conectada
a la caja. Para el uso remoto utilice la impresión del navegador; para una
impresión silenciosa se requiere un agente de impresión local en cada caja o
un servicio de impresión ejecutado en un Windows local con la impresora.

### Varias sucursales

Todos los equipos entran a la misma URL HTTPS y usan una sola base de datos.
No instale una base por sucursal. Desde el ERP cree las sucursales, cajas y
usuarios; los permisos de cada usuario limitan su operación a su sede.

## 9. Respaldos y actualizaciones

Instale el respaldo diario incluido y pruébelo:

```bash
install -m 700 -o root -g root /opt/novaerp-pos/deploy/backup_postgres.sh /usr/local/sbin/novaerp-backup
echo '30 2 * * * root /usr/local/sbin/novaerp-backup' > /etc/cron.d/novaerp-backup
/usr/local/sbin/novaerp-backup
ls -lh /var/backups/novaerp
```

Descargue además una copia cifrada fuera de la VPS al menos cada semana. Antes
de cada actualización ejecute el respaldo. Para actualizar código ya probado:

```bash
/usr/local/sbin/novaerp-backup
cd /opt/novaerp-pos
sudo -u novaerp git pull --ff-only origin main
sudo -u novaerp /opt/novaerp-pos/venv/bin/pip install -r requirements.txt
sudo -u novaerp env $(cat /etc/novaerp/novaerp.env | xargs) /opt/novaerp-pos/venv/bin/python manage.py migrate --noinput
sudo -u novaerp env $(cat /etc/novaerp/novaerp.env | xargs) /opt/novaerp-pos/venv/bin/python manage.py collectstatic --noinput
systemctl restart novaerp
systemctl status novaerp --no-pager
```

No edite ni borre migraciones ya aplicadas.

## 10. Prueba final de producción

1. Entre por `https://erp.tudominio.com`, no por la IP.
2. Cree usuarios de prueba de sucursales distintas.
3. Pruebe lector, venta, crédito, abono, devolución, traslado, recepción y
   cierre de caja.
4. Revise que exista un archivo nuevo en `/var/backups/novaerp`.
5. Compruebe el acceso desde un teléfono usando datos móviles.

La [documentación de VPS de Hostinger](https://www.hostinger.com/support/vps/) sirve como referencia para credenciales, consola, firewall y copias de seguridad.
