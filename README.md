# NovaERP POS

NovaERP es un ERP para operación comercial por sucursales: catálogo, inventario, producción, listas de precios, punto de venta, caja, cambios y devoluciones. Este documento sirve como guía de instalación y de inducción para el equipo administrador y operativo.

## 1. Requisitos e instalación

Necesitas Python 3.12, PostgreSQL (recomendado para producción) y Git. En Windows se recomienda trabajar desde PowerShell.

```powershell
git clone <URL-DEL-REPOSITORIO> novaerp-pos
Set-Location novaerp-pos
py -3.12 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Crea un archivo `.env` con las variables requeridas por `settings.py`: clave secreta, `DEBUG`, hosts permitidos, credenciales de la base de datos y cualquier integración de correo o almacenamiento que el proyecto tenga configurada. No subas ese archivo al repositorio.

Después prepara la base de datos y el administrador inicial:

```powershell
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
python manage.py runserver 0.0.0.0:8001
```

Abre `http://127.0.0.1:8001/` e inicia sesión. En producción ejecuta `collectstatic`, configura `DEBUG=False`, HTTPS, copias de seguridad y un servidor WSGI/ASGI detrás de un proxy web. Nunca uses `runserver` como servidor de producción.

## 2. Orden recomendado de configuración inicial

La puesta en marcha se realiza una sola vez y debe hacerla un superadministrador.

1. En **Setup inicial**, registra los datos de la empresa. Cuando ya exista una empresa, el setup no debe usarse como formulario para crear una nueva; usa **Administración > Empresa** para actualizar los datos.
2. En **Administración > Sucursales**, crea cada sede activa. Cada sucursal debe tener su caja operativa configurada antes de vender.
3. En **Administración > Usuarios**, crea los usuarios, asígnales rol y sucursal. Los empleados de producción no necesitan usuario: se administran desde el módulo de producción.
4. En **Administración > Catálogos**, registra telas, colores y tallas.
5. En **Productos**, crea el producto base y después sus variantes (SKU, tela, color y talla).
6. En **Administración > Listas de precios**, crea **Mayorista** y **Detal** y marca, en una sola operación, las sucursales que las usan.
7. En **Administración > Precios por producto**, busca una variante, escoge las sucursales y captura los precios mayorista y/o detal. Un guardado crea o actualiza ambos precios sin repetir el producto por sede.

Antes de que un cajero pueda vender, el administrador debe crear las cajas de cada sucursal y el cajero debe abrir su turno.

## 3. Roles y sucursales

Los permisos se aplican junto con la sucursal activa.

| Rol | Operación habitual |
| --- | --- |
| Superadministrador | Configuración completa, cambio de sucursal, auditoría y administración comercial. |
| Administrador de sucursal | Gestión operativa de su sede, según permisos configurados. |
| Cajero | Apertura/cierre de turno, POS, ventas, cambios y devoluciones de su sucursal. |
| Supervisor | Operaciones autorizadas como ajustes o precios manuales, según configuración. |

Un superadministrador debe seleccionar una sucursal activa antes de operar. Los usuarios normales siempre trabajan con la sucursal asociada a su perfil. Nunca intentes registrar una venta para una sede distinta desde otra sesión: el aislamiento de sucursal protege inventario, precios y caja.

## 4. Listas y precios

### Crear o editar una lista

Ve a **Administración > Listas de precios** y pulsa **Crear listas**. Define el nombre, tipo de venta y las sucursales. El sistema conserva una referencia técnica por sede, pero la administración se hace en grupo.

Para modificarla, pulsa el lápiz. Se cargan nombre, tipo, estado y sucursales actuales. Al quitar una sucursal, su lista se desactiva: no se borran precios ni historial, pero el POS ya no puede usarla hasta reactivarla.

### Asignar o editar precios

En **Precios por producto**, pulsa **Asignar precio**, busca por SKU, nombre, color o tela, selecciona las sedes y escribe Mayorista, Detal o ambos. Si un precio ya existe, se actualiza en vez de duplicarse.

Desde el lápiz de cada producto se abre la edición con los valores y sucursales previos cargados. Si una variante tiene diferentes precios entre sucursales, revisa el dato antes de guardar: una edición masiva está diseñada para estandarizar el valor elegido en las sedes marcadas.

## 5. Inventario y kardex

El stock es independiente por variante y sucursal. Nunca se debe editar la tabla de stock directamente en la base de datos.

- **Ajuste de entrada:** agrega unidades físicas encontradas, compras recibidas u otras incorporaciones autorizadas.
- **Ajuste de salida:** resta unidades por merma, pérdida, vencimiento o corrección autorizada.
- **Traslado:** mueve unidades entre sucursales usando el flujo de traslado, no con dos ajustes manuales.
- **Kardex:** es el historial auditable. Cada entrada, salida, venta, devolución, producción o ajuste debe generar un movimiento con saldo posterior.

Un ajuste no requiere caja porque no representa un pago de cliente. Las ventas, cambios con cobro y reembolsos sí requieren un turno abierto para que el dinero quede conciliado.

## 6. Producción

Primero registra los rollos de tela: código, tipo, color, cantidad inicial y costo. En **Corte/Producción** registra el corte, rollos consumidos, variantes y cantidades. El sistema descuenta el material y deja trazabilidad del corte.

Después asigna las operaciones (por ejemplo corte o confección) y los empleados que las realizaron. Los empleados de producción son registros operativos: no requieren correo, contraseña ni usuario del sistema. Solo la persona que captura la información inicia sesión.

La prenda terminada entra al inventario de fábrica o de la sucursal definida únicamente cuando el flujo de producción se completa. Consulta el historial de producción para saber qué persona cortó o confeccionó cada lote.

## 7. Caja

### Apertura

El cajero entra a **Abrir caja**, selecciona la caja de su sucursal e indica la base inicial en efectivo. Solo debe haber un turno abierto por caja según las reglas del sistema.

### Durante el turno

Registra retiros, ingresos manuales y sus motivos desde operaciones de caja. Las tarjetas y transferencias se guardan por medio de pago; no deben mezclarse con el efectivo físico.

El resumen del turno separa:

- Base inicial.
- Ventas totales, sin sumar la base.
- Efectivo esperado.
- Ingresos y retiros manuales.
- Cobros adicionales de cambios.
- Reembolsos por cambios o devoluciones.

### Cierre

Al cerrar, cuenta el efectivo físico e informa el valor real. Revisa cualquier diferencia antes de confirmar. No elimines turnos ni movimientos para cuadrar caja: registra el ajuste con motivo y conserva la auditoría.

## 8. Punto de venta (POS)

1. Abre la caja de tu sucursal.
2. Ingresa al POS y crea una venta nueva.
3. Busca la variante por código o nombre y agrégala al carrito. Ajusta cantidades solo dentro del stock disponible.
4. Selecciona Mayorista o Detal si tu operación lo permite. Los precios se actualizan según la lista activa de la sucursal.
5. Registra efectivo, transferencia y/o tarjeta. Los campos aceptan pago combinado y muestran total pagado, faltante o vuelto.
6. Confirma la venta. Esto descuenta inventario, registra kardex, actualiza caja y conserva la factura.

Si se recarga el navegador, el carrito/factura abierta debe recuperarse desde los datos persistidos del sistema. No crees otra venta para continuar una factura existente.

## 9. Anulación de ventas

Una venta anulada no se borra. Conserva su número, detalle, usuario y fecha con estado **Anulada**. La anulación debe revertir el stock y el efecto de caja mediante movimientos de reversión, no eliminando registros. Así el historial financiero y el kardex siguen siendo confiables.

## 10. Cambios y devoluciones

En **Cambios y devoluciones** no es obligatorio conocer el número de venta anterior: puedes buscar y registrar la prenda por SKU o nombre. Si tienes el número, inclúyelo como referencia para mayor auditoría.

### Recibir una prenda

Agrega la prenda que el cliente trae, indica cantidad y estado:

- **Apta:** vuelve a inventario y puede venderse de nuevo.
- **Dañada:** primero se registra la devolución y luego se da de baja; queda trazabilidad en kardex, pero no vuelve a estar disponible para venta.

### Entregar otra prenda y cobrar/reembolsar

Agrega la nueva prenda si existe cambio. El sistema calcula `valor entregado - valor recibido`.

- Resultado positivo: el cliente debe pagar la diferencia. Selecciona Efectivo, Tarjeta, Transferencia o Combinado. Al escoger un medio único se completa el valor automáticamente; en efectivo se puede ingresar un valor mayor y el sistema muestra el vuelto. En caja solo se registra el efectivo neto.
- Resultado cero: es un cambio por igual valor. No se debe registrar pago adicional.
- Resultado negativo: el cliente conserva un saldo a favor. Puedes marcar **Reembolsar diferencia** y elegir el medio; si no lo marcas, se registra como diferencia aceptada por el cliente, sin salida de dinero.

Todos los casos crean el comprobante de devolución/cambio, movimientos de stock y kardex. Los cobros adicionales, reembolsos y devoluciones en efectivo afectan el turno de caja abierto.

## 11. Operación diaria sugerida

1. Verificar sucursal activa.
2. Abrir caja y confirmar base.
3. Realizar ventas desde POS.
4. Registrar traslados, ajustes autorizados, producción y devoluciones con su motivo.
5. Consultar kardex si surge una diferencia de inventario.
6. Registrar retiros/ingresos manuales de caja cuando ocurran, nunca al final “de memoria”.
7. Cerrar caja, contar efectivo y revisar el resumen por medio de pago.

## 12. Controles y buenas prácticas

- No borres ventas, devoluciones, movimientos de stock ni movimientos de caja para corregir errores; usa anulación, ajuste o reversión autorizada.
- Usa referencias claras: factura, proveedor, lote, motivo o responsable.
- Revisa que cada sucursal tenga listas de precio activas antes de empezar a vender.
- Limita el cambio manual de precios a administradores/supervisores y exige motivo.
- Realiza copias de seguridad diarias de la base de datos y prueba periódicamente una restauración.
- Mantén actualizadas dependencias y credenciales; utiliza HTTPS y contraseñas individuales para cada operador.

## 13. Soporte y diagnóstico

Cuando aparezca un error, anota URL, hora, usuario, sucursal y número de venta/cambio. Consulta el kardex y los movimientos de caja antes de hacer correcciones. Si un producto no aparece en POS o cambios, valida que la variante esté activa, tenga stock (cuando aplique) y cuente con precio en la lista activa de la sucursal.

Para revisar la configuración local:

```powershell
python manage.py check
python manage.py makemigrations --check --dry-run
```

Ejecuta pruebas automatizadas antes de desplegar cambios y realiza una prueba manual de venta, cambio con excedente, devolución con reembolso, producción y cierre de caja en un entorno de pruebas.
