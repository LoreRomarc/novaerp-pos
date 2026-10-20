# Impresión automática en Windows, sin QZ Tray ni certificados

NovaERP imprime mediante un conector local gratuito. No depende de QZ Tray,
no pide aceptar sitios y no requiere comprar certificados. El conector se
instala una vez en cada computador que tenga impresora y se inicia solo al
iniciar sesión en Windows.

## Instalación sin terminal ni carpeta del proyecto

El archivo distribuible es:

`releases\NovaERP_Print_Connector.exe`

Después de subir los cambios al repositorio, copie **solo ese archivo** al
escritorio de cada computador que tenga impresora, por USB, OneDrive, correo o
la carpeta compartida que usen. No necesita copiar NovaERP, Python, el entorno
virtual ni abrir una terminal.

La primera vez haga doble clic en el archivo. NovaERP registra el conector en
el inicio automático del usuario y muestra un único mensaje de confirmación.
Luego puede cerrar la ventana: el conector queda funcionando en segundo plano
en cada inicio de Windows. Si Windows SmartScreen pregunta por el archivo, use
**Más información > Ejecutar de todas formas** solamente si el archivo fue
recibido desde el repositorio oficial de NovaERP.

## 1. Preparar el material de la SAT TT448-2 (prueba)

1. Abra **Configuración > Bluetooth y dispositivos > Impresoras y escáneres**.
2. Seleccione **SAT TT448-2 USE (ZPL)** y abra **Preferencias de impresión**.
3. En **Preparar página**, junto a *Material*, pulse **Nuevo**.
4. Configure:
   - Nombre: `NOVAERP-33`.
   - Tipo: **Continuo (longitud variable)**.
   - Ancho: **33,00 mm**.
   - Longitud: **150,00 mm** como valor inicial. El ticket ZPL calcula su
     longitud real; este número solo evita que el driver conserve el perfil
     anterior de 70 × 50 mm.
   - Márgenes izquierdo y derecho: **0,00 mm**.
5. Guarde y selecciónelo como material activo.
6. En **Material**, seleccione **Continuo**, modo **Rasgar**, pausa **Sin
   pausa** y deje ambos ajustes en **0,00 mm**.
7. Pulse **Aplicar** y después **Aceptar**.

> Importante: en las capturas el perfil activo es de **70 × 50 mm**. Ese es
> el motivo de que una impresión de 33 mm pareciera ocupar menos de la mitad
> de la cinta. Debe quedar seleccionado `NOVAERP-33`.

## 2. Instalación para desarrollo (opcional)

Este procedimiento queda solo como alternativa para desarrollo desde la
carpeta del proyecto, por ejemplo
`C:\Users\User\novaerp-pos`:

1. Cierre QZ Tray si lo tiene abierto; ya no se usa.
2. Abra PowerShell como el usuario que usará el POS (no hace falta abrirlo
   como administrador).
3. Ejecute exactamente:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
cd C:\Users\User\novaerp-pos
.\tools\instalar_conector_impresion.ps1
```

4. Debe aparecer: `Listo. El conector inicia automáticamente al iniciar sesión en Windows.`
5. Reinicie Windows una vez, o cierre y vuelva a iniciar sesión. Desde ese
   momento no debe abrir ningún `.bat`, PowerShell ni QZ Tray para vender.

Para comprobarlo: en el ERP abra **Configuración de tickets**, pulse el botón
de actualizar junto a la impresora, elija **SAT TT448-2 USE (ZPL)**, escriba
**33** como ancho, guarde y pulse **Probar impresión**.

## 3. Uso normal y alternativa PDF

- Con **Impresión automática** activa, NovaERP envía la venta, devolución y
  reimpresión a la impresora seleccionada sin cuadro del navegador.
- Con la opción desactivada, NovaERP abre el comprobante y el navegador permite
  imprimirlo o guardarlo en PDF.
- Cada computador tiene sus propias impresoras. Repita solamente el paso 2 en
  cada caja que deba imprimir.

## 4. Diseño y contenido del ticket

El contenido de las ventas se arma en:

`apps/sales/services/impresion_termica_service.py`

- Método `_ticket_venta`: datos y orden de la factura de venta.
- Método `_ticket_devolucion`: datos del comprobante de devolución.
- Método `_ticket_zpl`: diseño ZPL específico para la SAT/Zebra de prueba;
  `ancho_dots = ancho_mm × 8` es la medida que controla el ancho físico.

Las vistas HTML que se muestran cuando se imprime desde el navegador están en:

- `apps/sales/templates/sales/ticket_venta.html`
- `apps/sales/templates/sales/ticket_devolucion.html`
- `apps/sales/templates/sales/ticket_prueba.html`

Para la impresora POS definitiva no se necesita cambiar el código: seleccione
su nombre desde **Configuración de tickets**, configure allí y en Windows el
mismo ancho (normalmente 58 u 80 mm), y deje activada la impresión automática.
El conector utilizará el controlador de Windows para una impresora POS común.
