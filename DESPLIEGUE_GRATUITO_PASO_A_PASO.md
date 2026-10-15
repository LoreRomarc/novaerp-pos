# NovaERP: prueba gratuita entre sucursales, paso a paso

Esta guía sirve para publicar una **copia de prueba** de NovaERP en Internet y abrirla desde otras sucursales. Está escrita para Windows y no requiere saber programar.

> **No es producción.** Render gratuito suspende la web cuando no recibe visitas durante 15 minutos; tarda aproximadamente un minuto en volver a abrir. Su PostgreSQL gratuito vence a los 30 días y no tiene copias de seguridad administradas. Úsalo únicamente para pruebas, con información de ejemplo. No reemplaza la instalación local ni sus respaldos. Consulte las condiciones vigentes de [Render Free](https://render.com/docs/free).

## Resultado que tendrá al finalizar

- Una dirección parecida a `https://novaerp-pruebas.onrender.com`.
- Una única base de datos de prueba centralizada.
- Las sucursales podrán entrar con navegador e Internet usando la misma dirección.
- Cada sucursal verá sólo lo permitido por su usuario y sucursal asignada.
- El lector de códigos USB con cable funcionará como teclado en cada computador.
- La impresora Windows local **no imprime automáticamente desde Render**; para la prueba puede usar el botón de comprobante y el diálogo de impresión del navegador.

---

## Parte 1: revisar el proyecto en su computador

### 1. Cerrar el servidor si está abierto

Si ve en la terminal mensajes como `Starting development server`, haga clic allí y presione `Ctrl + C` una vez. Espere a volver a ver el cursor.

### 2. Abrir PowerShell en la carpeta correcta

1. Presione la tecla Windows.
2. Escriba **PowerShell** y abra **Windows PowerShell**.
3. Copie y pegue esta línea; luego presione `Enter`:

```powershell
cd C:\Users\User\novaerp-pos
```

4. Verifique que está en el sitio correcto:

```powershell
dir render.yaml, build.sh, .gitignore
```

Debe ver los tres archivos. Si aparece un error, no continúe: revise que la ruta sea exactamente `C:\Users\User\novaerp-pos`.

### 3. Confirmar que las claves privadas no se subirán

No abra ni copie el archivo `.env`. Ese archivo contiene contraseñas y ya está protegido por `.gitignore`.

En la misma PowerShell ejecute:

```powershell
git check-ignore -v .env
git status
```

La primera línea debe mencionar `.gitignore`. En la salida de `git status` **no debe aparecer `.env`**. Si aparece `.env`, deténgase y no ejecute `git add`; solicite ayuda primero.

No necesita editar `.env`, `settings.py`, `render.yaml` ni `build.sh` para esta prueba. Los archivos ya quedaron preparados.

---

## Parte 2: crear su repositorio privado en GitHub

GitHub guardará el código. No guardará la base de datos local, ventas reales ni el archivo `.env`.

### 4. Crear cuenta o iniciar sesión

1. Abra [github.com](https://github.com/).
2. Pulse **Sign in** e inicie sesión. Si no tiene cuenta, pulse **Sign up** y complete el registro.

### 5. Crear el repositorio

1. Arriba a la derecha pulse el símbolo **+**.
2. Pulse **New repository**.
3. En **Repository name** escriba: `novaerp-pruebas`.
4. Seleccione **Private**. Esto es obligatorio para no publicar el código.
5. No marque ninguna de estas opciones:
   - `Add a README file`;
   - `Add .gitignore`;
   - `Choose a license`.
6. Pulse **Create repository**.
7. En la pantalla siguiente copie la dirección HTTPS. Se verá parecida a:

```text
https://github.com/TU-USUARIO/novaerp-pruebas.git
```

No cierre esta pestaña aún.

### 6. Separar esta copia del repositorio compartido, sin borrar nada

No necesita “salirse” de ningún proyecto ni borrar `origin`. Una **rama** es una
línea de trabajo local; un **remoto** es el repositorio al que se envía el
código. En este equipo actualmente:

- `dev` es la rama compartida en la que está trabajando;
- `origin` es el repositorio compartido: `LoreRomarc/novaerp-pos`;
- `pruebas` es su repositorio propio: `jnstudiotech/novaerp-pruebas`.

**Nunca ejecute `git push origin ...` para publicar las pruebas.** Eso sí
enviaría cambios al repositorio compartido. Para comprobar dónde está, ejecute:

```powershell
git branch --show-current
git remote -v
```

Ahora cree una rama exclusiva para los despliegues. Esta acción conserva todos
sus archivos actuales y no modifica el repositorio de la otra persona:

```powershell
git switch -c despliegue-pruebas
```

Si PowerShell dice que esa rama ya existe, use en cambio:

```powershell
git switch despliegue-pruebas
```

Verifique de nuevo con `git branch --show-current`: debe aparecer
`despliegue-pruebas`.

El remoto `pruebas` ya está configurado. Si en otro computador no aparece al
ejecutar `git remote -v`, agréguelo allí una única vez reemplazando sólo la URL:

```powershell
git remote add pruebas https://github.com/jnstudiotech/novaerp-pruebas.git
```

Para volver después al trabajo compartido, ejecute únicamente:

```powershell
git switch dev
```

Cambiar de rama no borra ni publica nada.

### 7. Subir el código de prueba

Ejecute cada línea por separado:

```powershell
git add -A
git status
```

Revise esa salida antes de continuar. **Si aparece `.env`, contraseñas, `venv/`, `db.sqlite3` o un respaldo**, ejecute:

```powershell
git restore --staged .
```

Luego deténgase y pida ayuda. Si no aparecen datos privados, continúe:

```powershell
git commit -m "NovaERP preparado para pruebas gratuitas"
git push -u pruebas HEAD:main
```

Si GitHub pregunta por autenticación, complete la ventana de navegador que abra. Al terminar, regrese a GitHub y actualice la página: debe ver los archivos del proyecto.

---

## Parte 3: crear el servicio gratuito en Render

### 8. Crear cuenta de Render

1. Abra [render.com](https://render.com/).
2. Pulse **Get Started for Free**.
3. Seleccione continuar con **GitHub**.
4. Autorice a Render para acceder sólo al repositorio `novaerp-pruebas` cuando GitHub lo pregunte.

### 9. Crear el despliegue usando Blueprint

1. En el panel de Render pulse **New**.
2. Elija **Blueprint**.
3. Seleccione el repositorio `novaerp-pruebas`.
4. Verifique que la rama sea **main**.
5. Pulse **Connect** y después **Apply**.

Render leerá automáticamente el archivo `render.yaml` de la raíz del repositorio. Ese archivo creará:

- el servicio web gratuito `novaerp-pruebas`;
- una base PostgreSQL gratuita `novaerp-pruebas-db`;
- una clave secreta privada generada por Render;
- `DJANGO_DEBUG=False` y los archivos estáticos necesarios.

No escriba contraseñas manualmente en Render para esta prueba.

### 10. Esperar el primer despliegue

1. Render abrirá una pantalla con mensajes de compilación.
2. Espere hasta que el estado cambie a **Live** y tenga color verde.
3. Si muestra **Build failed**, pulse **Logs**, copie desde la primera línea roja hasta el final y solicite ayuda; no borre el servicio ni la base.
4. Cuando esté verde, pulse la dirección que termina en `.onrender.com`.

### 11. Confirmar los valores de entorno sin editar archivos

1. En Render, abra el servicio web llamado `novaerp-pruebas`.
2. En el menú izquierdo pulse **Environment**.
3. Debe ver estas variables:

| Variable | Valor esperado |
|---|---|
| `DJANGO_DEBUG` | `False` |
| `DJANGO_USE_WHITENOISE` | `True` |
| `DATABASE_URL` | Marcada como secreto o vinculada a la base |
| `DJANGO_SECRET_KEY` | Marcada como secreto |

`DJANGO_DEBUG` no se configura dentro del ERP ni en VS Code durante este paso. Está en **Render → servicio → Environment**. No modifique `DATABASE_URL` ni `DJANGO_SECRET_KEY`.

---

## Parte 4: configurar la copia de prueba del ERP

### 12. Ejecutar el setup inicial una sola vez

1. Abra la dirección `.onrender.com` del paso 10.
2. La primera visita irá a `https://...onrender.com/setup/`.
3. Complete empresa de prueba, sucursal inicial, caja y el usuario administrador.
4. Guarde la contraseña del administrador en un gestor de contraseñas o lugar seguro.
5. Al terminar, cierre sesión e ingrese por:

```text
https://TU-DIRECCION.onrender.com/accounts/login/
```

No vuelva a ejecutar setup para cambiar datos. Después use **Administración → Empresa**, **Sucursales**, **Usuarios y permisos** y **Administrar cajas**.

### 13. Probar varias sucursales

Como superadministrador:

1. Cree una segunda sucursal en **Administración → Sucursales**.
2. Cambie a esa sede desde **Cambiar sucursal** en el sidebar.
3. Cree una caja para esa sede en **Administrar cajas**.
4. Cree un usuario de prueba, asígnele el rol y la sucursal correspondiente.
5. Desde otro computador o teléfono con Internet abra la misma dirección `.onrender.com`.
6. Inicie sesión con el usuario de prueba.
7. Compruebe que no puede cambiar de sucursal ni vender con el stock de otra sede.

Realice como mínimo: venta, venta a crédito, cuota posterior, devolución, traslado, recepción y cierre de caja. Use productos y datos de prueba, no datos reales.

---

## Parte 5: usar el lector de códigos USB con cable

El lector no requiere instalar un programa si funciona como **HID Keyboard**
(teclado USB), que es el modo habitual.

1. Conecte el lector directamente a un puerto USB del computador de caja.
2. Abra **Bloc de notas** de Windows.
3. Escanee una etiqueta. Debe aparecer el número y el cursor debe pasar a la
   línea siguiente. Si sólo aparece el número, use el manual que vino con el
   lector para configurar el sufijo **Enter** o **CR/LF**; normalmente se hace
   escaneando un código de configuración del manual.
4. En NovaERP abra **Punto de venta**, haga un clic en “Buscar o escanear” y
   escanee el producto. Debe agregarse a la venta.
5. Pruebe también Ajuste de stock, Traslados, Cambios/devoluciones y Asignar
   precios: haga clic en su campo “Buscar o escanear” antes de leer la etiqueta.

El lector sólo escribe un código: los permisos, la sucursal activa y la
validación de existencias siguen siendo controlados por NovaERP. Para crear o
probar etiquetas, use el código de barras que muestra cada variante; no
reutilice un mismo código en dos productos.

## Parte 6: publicar cambios posteriores

Antes de empezar un cambio que vaya a la copia de pruebas, abra PowerShell en
`C:\Users\User\novaerp-pos` y entre primero a la rama de despliegue:

```powershell
git switch despliegue-pruebas
```

Cuando termine el cambio y lo haya probado, guárdelo y publíquelo así:

```powershell
git add -A
git status
git commit -m "Describe brevemente el cambio"
git push pruebas HEAD:main
```

Render detectará el envío y hará el despliegue automáticamente. Abra **Render → novaerp-pruebas → Events** para ver el progreso y **Logs** si falla.

Si el cambio incluye modelos de Django, antes de subir ejecute en su computador:

```powershell
.\venv\Scripts\Activate.ps1
python manage.py makemigrations
python manage.py migrate
python manage.py test apps.sales.tests apps.inventory.tests
```

Luego haga el `git add`, `commit` y `push`. **Nunca borre, renombre ni edite migraciones que ya se aplicaron.**

---

## Límites y siguiente paso

Render gratuito permite verificar que todas las sedes pueden trabajar sobre una misma base desde Internet, pero no es apto para operación real por sus pausas, expiración de base, falta de backups y sistema de archivos efímero. [Limitaciones de Render](https://render.com/docs/free)

Cuando las pruebas estén aprobadas, siga [DESPLIEGUE_PRODUCCION.md](DESPLIEGUE_PRODUCCION.md) para pasar a servicios de pago administrados, PostgreSQL central persistente, respaldos, HTTPS y dominio propio.
