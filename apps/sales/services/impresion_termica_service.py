"""Impresión térmica silenciosa mediante el controlador de Windows.

Se usa GDI, no el navegador ni RAW/ESC-POS: así es compatible con drivers
térmicos que solo aceptan trabajos gráficos de Windows.
"""

import ctypes
import os
import unicodedata
from ctypes import POINTER, byref, c_int, c_void_p, create_unicode_buffer
from ctypes.wintypes import DWORD, LPCWSTR

from django.core.exceptions import ValidationError


class ImpresionTermicaService:
    """Envía un ticket a la impresora instalada, sin diálogo del navegador."""

    ESC = b"\x1b"
    GS = b"\x1d"

    @staticmethod
    def _dinero(valor):
        return f"${float(valor or 0):,.0f}".replace(",", ".")

    @staticmethod
    def _cantidad(valor):
        texto = f"{valor:.2f}" if hasattr(valor, "quantize") else str(valor)
        return texto.rstrip("0").rstrip(".")

    @classmethod
    def _ancho_caracteres(cls, ancho_mm):
        # La fuente ZPL actual ocupa 11 puntos de ancho; se reserva 4 puntos
        # por cada margen. Así las líneas se adaptan al ancho configurado.
        return max(12, (max(160, round(int(ancho_mm) * 8)) - 8) // 11)

    @staticmethod
    def _lineas(texto, ancho):
        texto = " ".join(str(texto or "").split())
        if not texto:
            return []
        return [texto[indice:indice + ancho] for indice in range(0, len(texto), ancho)]

    @classmethod
    def _centrado(cls, texto, ancho):
        return [linea.center(ancho) for linea in cls._lineas(texto, ancho)]

    @classmethod
    def _derecha(cls, etiqueta, valor, ancho):
        valor = str(valor)
        espacio = ancho - len(etiqueta) - len(valor)
        if espacio >= 1:
            return [f"{etiqueta}{' ' * espacio}{valor}"]
        return cls._lineas(etiqueta, ancho) + [valor.rjust(ancho)]

    @classmethod
    def _ticket_venta(cls, venta, configuracion):
        ancho = cls._ancho_caracteres(configuracion.ancho_papel_mm)
        empresa = venta.sucursal.empresa
        nombre_empresa = empresa.nombre if empresa else venta.sucursal.nombre
        lineas = []
        lineas.extend(cls._centrado(nombre_empresa, ancho))
        if empresa and empresa.razon_social:
            lineas.extend(cls._centrado(empresa.razon_social, ancho))
        if empresa and empresa.nit:
            lineas.extend(cls._centrado(f"NIT: {empresa.nit}", ancho))
        lineas.extend(cls._centrado(venta.sucursal.nombre, ancho))
        if venta.sucursal.direccion:
            lineas.extend(cls._centrado(venta.sucursal.direccion, ancho))
        if empresa and empresa.telefono:
            lineas.extend(cls._centrado(f"Tel: {empresa.telefono}", ancho))
        lineas.append("-" * ancho)
        encabezado = (
            "FACTURA DE VENTA A CREDITO"
            if venta.estado == "CREDITO"
            else "COMPROBANTE DE VENTA"
        )
        lineas.extend(cls._centrado(encabezado, ancho))
        lineas.append(f"No: #{venta.id}")
        lineas.append(f"Fecha: {venta.cerrada:%d/%m/%Y %H:%M}")
        lineas.append(f"Caja: {venta.turno.caja.codigo}")
        lineas.append(f"Atendio: {venta.usuario.get_full_name() or venta.usuario.username}")
        lineas.append(f"Vendedor: {venta.vendedor.nombre if venta.vendedor_id else 'Sin asignar'}")
        if venta.cliente:
            lineas.extend(cls._lineas(f"Cliente: {venta.cliente}", ancho))
        lineas.append("-" * ancho)
        for item in venta.items.all():
            lineas.extend(cls._lineas(item.nombre_producto, ancho))
            atributos = " · ".join(filter(None, [
                item.sku,
                item.tipo_tela,
                item.color,
                item.talla,
            ]))
            if atributos:
                lineas.extend(cls._lineas(atributos, ancho))
            detalle = f"{cls._cantidad(item.cantidad)} x {cls._dinero(item.precio_unitario)}"
            lineas.extend(cls._derecha(detalle, cls._dinero(item.total_linea), ancho))
        lineas.append("-" * ancho)
        lineas.extend(cls._derecha("Subtotal", cls._dinero(venta.subtotal), ancho))
        if venta.total_iva:
            lineas.extend(cls._derecha("IVA", cls._dinero(venta.total_iva), ancho))
        lineas.extend(cls._derecha("TOTAL", cls._dinero(venta.total), ancho))
        lineas.extend(cls._derecha("Efectivo", cls._dinero(venta.monto_efectivo), ancho))
        lineas.extend(cls._derecha("Transferencia", cls._dinero(venta.monto_transferencia), ancho))
        if venta.estado == "CREDITO":
            lineas.extend(cls._derecha("TOTAL ABONADO", cls._dinero(venta.total_pagado), ancho))
            lineas.extend(cls._derecha("SALDO PENDIENTE", cls._dinero(venta.saldo_pendiente), ancho))
        if venta.cambio:
            lineas.extend(cls._derecha("Vuelto", cls._dinero(venta.cambio), ancho))
        lineas.append("-" * ancho)
        lineas.extend(cls._centrado(configuracion.mensaje_pie or "Gracias por su compra.", ancho))
        return "\n".join(lineas)

    @classmethod
    def _ticket_devolucion(cls, devolucion, configuracion):
        """Ticket propio; no se presenta como venta ni permite encadenarla."""
        ancho = cls._ancho_caracteres(configuracion.ancho_papel_mm)
        empresa = devolucion.sucursal.empresa
        nombre_empresa = empresa.nombre if empresa else devolucion.sucursal.nombre
        lineas = cls._centrado(nombre_empresa, ancho)
        if empresa and empresa.nit:
            lineas.extend(cls._centrado(f"NIT: {empresa.nit}", ancho))
        lineas.extend(cls._centrado(devolucion.sucursal.nombre, ancho))
        lineas.append("-" * ancho)
        lineas.extend(cls._centrado("COMPROBANTE DE CAMBIO / DEVOLUCION", ancho))
        lineas.append(f"No: CD-{devolucion.id}")
        lineas.append(f"Fecha: {devolucion.creada:%d/%m/%Y %H:%M}")
        lineas.append(f"Caja: {devolucion.turno.caja.codigo}")
        lineas.append(f"Atendio: {devolucion.usuario.get_full_name() or devolucion.usuario.username}")
        if devolucion.venta_id:
            lineas.append(f"Venta origen: #{devolucion.venta_id}")
        if devolucion.referencia_externa:
            lineas.extend(cls._lineas(f"Ref: {devolucion.referencia_externa}", ancho))
        lineas.append("-" * ancho)
        lineas.extend(cls._centrado("PRENDAS RECIBIDAS", ancho))
        for item in devolucion.items_devueltos.all():
            lineas.extend(cls._lineas(str(item.variante), ancho))
            lineas.extend(cls._derecha(
                f"{cls._cantidad(item.cantidad)} x {cls._dinero(item.precio_unitario)}",
                cls._dinero(item.total), ancho,
            ))
        if devolucion.items_entregados.exists():
            lineas.extend(cls._centrado("PRENDAS ENTREGADAS", ancho))
            for item in devolucion.items_entregados.all():
                lineas.extend(cls._lineas(str(item.variante), ancho))
                lineas.extend(cls._derecha(
                    f"{cls._cantidad(item.cantidad)} x {cls._dinero(item.precio_unitario)}",
                    cls._dinero(item.total), ancho,
                ))
        lineas.append("-" * ancho)
        lineas.extend(cls._derecha("Valor recibido", cls._dinero(devolucion.total_devuelto), ancho))
        lineas.extend(cls._derecha("Valor entregado", cls._dinero(devolucion.total_entregado), ancho))
        if devolucion.monto_recibido_efectivo:
            lineas.extend(cls._derecha("Efectivo recibido", cls._dinero(devolucion.monto_recibido_efectivo), ancho))
        if devolucion.vuelto_efectivo:
            lineas.extend(cls._derecha("Vuelto", cls._dinero(devolucion.vuelto_efectivo), ancho))
        if devolucion.monto_reembolsado:
            lineas.extend(cls._derecha("Reembolsado", cls._dinero(devolucion.monto_reembolsado), ancho))
        lineas.extend(cls._derecha("Cobro neto", cls._dinero(devolucion.monto_cobrado), ancho))
        lineas.append("-" * ancho)
        lineas.extend(cls._lineas(f"Motivo: {devolucion.motivo}", ancho))
        lineas.extend(cls._centrado("DOCUMENTO DE CAMBIO / DEVOLUCION", ancho))
        return "\n".join(lineas)

    @staticmethod
    def _zpl_texto(texto):
        """Convierte el contenido a caracteres seguros para comandos ZPL."""
        texto = unicodedata.normalize("NFKD", str(texto or ""))
        texto = texto.encode("ascii", "ignore").decode("ascii")
        return texto.replace("^", " ").replace("~", " ")

    @classmethod
    def _ticket_zpl(cls, contenido, ancho_mm):
        """Genera ZPL para etiquetas continuas de la SAT TT448-2/Zebra."""
        ancho_dots = max(160, round(int(ancho_mm) * 8))  # 203 dpi aprox.
        # Cada tamaño usa todo su ancho físico: el contenido se parte con el
        # mismo cálculo de `_ancho_caracteres` antes de generar el ZPL.
        alto_fuente = 20
        ancho_fuente = 11
        salto = 25
        margen = 4
        y = 8
        campos = []
        for linea in contenido.splitlines():
            linea = cls._zpl_texto(linea)
            campos.append(
                f"^FO{margen},{y}^A0N,{alto_fuente},{ancho_fuente}^FD{linea}^FS"
            )
            y += salto
        comandos = [
            "^XA",
            f"^PW{ancho_dots}",
            f"^LL{y + 18}",
            "^LH0,0",
            "^CI27",
            *campos,
            "^PQ1",
            "^XZ",
        ]
        return "".join(comandos).encode("ascii", errors="replace")

    # FUTURO — impresora POS convencional ESC/POS (58/80 mm).
    # Para activarla: (1) descomente `_ticket_escpos`; (2) en los métodos
    # `imprimir_venta` e `imprimir_prueba`, reemplace ÚNICAMENTE este bloque:
    #     cls._enviar_raw(impresora, cls._ticket_zpl(contenido, configuracion.ancho_papel_mm), configuracion.cortar_papel,)
    # por:
    #     cls._enviar_raw(impresora, cls._ticket_escpos(contenido, configuracion), True)
    # Después configure 58 u 80 mm tanto en Windows como en esta pantalla.
    # @classmethod
    # def _ticket_escpos(cls, contenido, configuracion):
    #     datos = cls.ESC + b"@" + cls.ESC + b"t\x02"
    #     return datos + contenido.encode("cp850", errors="replace") + b"\n\n\n" + cls.GS + b"V\x42\x00"

    @staticmethod
    def _impresora_predeterminada():
        if os.name != "nt":
            raise ValidationError("La impresión directa está disponible únicamente en Windows.")
        winspool = ctypes.WinDLL("winspool.drv")
        cantidad = DWORD(0)
        winspool.GetDefaultPrinterW(None, byref(cantidad))
        if not cantidad.value:
            raise ValidationError("Windows no tiene una impresora predeterminada.")
        buffer = create_unicode_buffer(cantidad.value)
        if not winspool.GetDefaultPrinterW(buffer, byref(cantidad)):
            raise ValidationError("No fue posible consultar la impresora predeterminada.")
        impresora = buffer.value
        ImpresionTermicaService._validar_impresora(impresora)
        return impresora

    @staticmethod
    def _validar_impresora(impresora):
        # Nunca enviar un ticket RAW a una impresora virtual: abriría el
        # diálogo de guardar PDF/XPS, que no es una impresión de caja.
        virtuales = ("microsoft print to pdf", "xps document writer", "onenote")
        if any(nombre in impresora.casefold() for nombre in virtuales):
            raise ValidationError(
                "La impresora predeterminada de Windows es una impresora virtual "
                f"('{impresora}'). Seleccione la impresora térmica como "
                "predeterminada o escriba su nombre en Impresión de tickets."
            )
        return impresora

    @classmethod
    def _enviar_gdi(cls, impresora, contenido, ancho_mm):
        """Dibuja el ticket usando el driver Windows de la impresora.

        Este método evita el trabajo RAW que algunos drivers aceptan en cola
        pero descartan sin imprimir.
        """
        if os.name != "nt":
            raise ValidationError("La impresión directa está disponible únicamente en Windows.")

        class DOCINFOW(ctypes.Structure):
            _fields_ = [
                ("cbSize", c_int),
                ("lpszDocName", LPCWSTR),
                ("lpszOutput", LPCWSTR),
                ("lpszDatatype", LPCWSTR),
                ("fwType", DWORD),
            ]

        gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
        gdi32.CreateDCW.argtypes = [LPCWSTR, LPCWSTR, LPCWSTR, c_void_p]
        gdi32.CreateDCW.restype = c_void_p
        gdi32.CreateFontW.restype = c_void_p
        gdi32.SelectObject.restype = c_void_p
        gdi32.StartDocW.argtypes = [c_void_p, POINTER(DOCINFOW)]
        gdi32.StartDocW.restype = c_int
        gdi32.StartPage.argtypes = [c_void_p]
        gdi32.StartPage.restype = c_int
        gdi32.EndPage.argtypes = [c_void_p]
        gdi32.EndDoc.argtypes = [c_void_p]
        gdi32.TextOutW.argtypes = [c_void_p, c_int, c_int, LPCWSTR, c_int]
        gdi32.TextOutW.restype = c_int
        gdi32.GetDeviceCaps.argtypes = [c_void_p, c_int]
        gdi32.GetDeviceCaps.restype = c_int
        gdi32.DeleteDC.argtypes = [c_void_p]
        hdc = gdi32.CreateDCW("WINSPOOL", impresora, None, None)
        if not hdc:
            raise ValidationError(
                f"Windows no pudo inicializar el controlador de '{impresora}'."
            )

        fuente = c_void_p()
        try:
            # Courier New conserva el ancho de caracteres que utiliza el ticket.
            alto_fuente = {25: 17, 58: 17, 80: 18}.get(ancho_mm, 17)
            fuente = gdi32.CreateFontW(
                -alto_fuente, 0, 0, 0, 400, False, False, False,
                1, 0, 0, 4, 0, "Courier New",
            )
            if not fuente:
                raise ValidationError("Windows no pudo crear la fuente del ticket.")

            anterior = gdi32.SelectObject(hdc, fuente)
            info = DOCINFOW(
                ctypes.sizeof(DOCINFOW),
                "NovaERP - comprobante de venta",
                None,
                None,
                0,
            )
            if gdi32.StartDocW(hdc, byref(info)) <= 0:
                raise ValidationError("Windows no pudo iniciar el documento de impresión.")
            try:
                if gdi32.StartPage(hdc) <= 0:
                    raise ValidationError("Windows no pudo iniciar la página del ticket.")
                try:
                    ancho_impresion = gdi32.GetDeviceCaps(hdc, 8)  # HORZRES
                    margen = max(4, int(ancho_impresion * 0.03))
                    y = max(6, int(ancho_impresion * 0.04))
                    salto = alto_fuente + 6
                    for linea in contenido.splitlines():
                        if not gdi32.TextOutW(hdc, margen, y, linea, len(linea)):
                            raise ValidationError("Windows no pudo dibujar el contenido del ticket.")
                        y += salto
                finally:
                    gdi32.EndPage(hdc)
            finally:
                gdi32.EndDoc(hdc)
                gdi32.SelectObject(hdc, anterior)
        finally:
            if fuente:
                gdi32.DeleteObject(fuente)
            gdi32.DeleteDC(hdc)

    @classmethod
    def _enviar_raw(cls, impresora, datos, cortar_papel):
        if os.name != "nt":
            raise ValidationError("La impresión directa está disponible únicamente en Windows.")

        class DOC_INFO_1(ctypes.Structure):
            _fields_ = [
                ("pDocName", LPCWSTR),
                ("pOutputFile", LPCWSTR),
                ("pDatatype", LPCWSTR),
            ]

        winspool = ctypes.WinDLL("winspool.drv", use_last_error=True)
        handle = c_void_p()
        if not winspool.OpenPrinterW(impresora, byref(handle), None):
            raise ValidationError(f"No fue posible abrir la impresora '{impresora}'.")

        try:
            documento = DOC_INFO_1("NovaERP - comprobante de venta", None, "RAW")
            trabajo = winspool.StartDocPrinterW(handle, 1, byref(documento))
            if not trabajo:
                raise ValidationError("Windows no pudo iniciar el trabajo de impresión.")
            try:
                if not winspool.StartPagePrinter(handle):
                    raise ValidationError("Windows no pudo iniciar la página de impresión.")
                try:
                    bytes_escritos = DWORD(0)
                    buffer = ctypes.create_string_buffer(datos)
                    if not winspool.WritePrinter(
                        handle,
                        buffer,
                        len(datos),
                        byref(bytes_escritos),
                    ):
                        raise ValidationError("Windows no pudo enviar el ticket a la impresora.")
                finally:
                    winspool.EndPagePrinter(handle)
            finally:
                winspool.EndDocPrinter(handle)
        finally:
            winspool.ClosePrinter(handle)

    @classmethod
    def imprimir_venta(cls, venta, configuracion):
        """Imprime una venta finalizada, incluso si conserva saldo a crédito."""
        if venta.estado not in {"CERRADA", "CREDITO"}:
            raise ValidationError("Solo se pueden imprimir ventas finalizadas.")

        impresora = configuracion.nombre_impresora.strip() or cls._impresora_predeterminada()
        cls._validar_impresora(impresora)
        contenido = cls._ticket_venta(venta, configuracion)
        cls._enviar_raw(
            impresora,
            cls._ticket_zpl(contenido, configuracion.ancho_papel_mm),
            configuracion.cortar_papel,
        )
        return impresora

    @classmethod
    def payload_venta_zpl(cls, venta, configuracion):
        """Datos del ticket para el agente local Windows de NovaERP."""
        contenido = cls._ticket_venta(venta, configuracion)
        return {
            "impresora": configuracion.nombre_impresora.strip(),
            "zpl": cls._ticket_zpl(
                contenido, configuracion.ancho_papel_mm
            ).decode("ascii", errors="replace"),
        }

    @classmethod
    def payload_prueba_zpl(cls, sucursal, configuracion):
        ancho = cls._ancho_caracteres(configuracion.ancho_papel_mm)
        contenido = "\n".join(
            cls._centrado("PRUEBA DE IMPRESION", ancho)
            + cls._centrado(sucursal.nombre, ancho)
            + ["-" * ancho, f"Ancho: {configuracion.ancho_papel_mm} mm", "Texto de prueba", "-" * ancho]
        )
        return {
            "impresora": configuracion.nombre_impresora.strip(),
            "zpl": cls._ticket_zpl(
                contenido, configuracion.ancho_papel_mm
            ).decode("ascii", errors="replace"),
        }

    @classmethod
    def payload_devolucion_zpl(cls, devolucion, configuracion):
        contenido = cls._ticket_devolucion(devolucion, configuracion)
        return {
            "impresora": configuracion.nombre_impresora.strip(),
            "zpl": cls._ticket_zpl(
                contenido, configuracion.ancho_papel_mm
            ).decode("ascii", errors="replace"),
        }

    @classmethod
    def imprimir_devolucion(cls, devolucion, configuracion):
        """Imprime el comprobante independiente de cambio o devolución."""
        impresora = configuracion.nombre_impresora.strip() or cls._impresora_predeterminada()
        cls._validar_impresora(impresora)
        contenido = cls._ticket_devolucion(devolucion, configuracion)
        cls._enviar_raw(impresora, cls._ticket_zpl(contenido, configuracion.ancho_papel_mm), configuracion.cortar_papel)
        return impresora

    @classmethod
    def imprimir_prueba(cls, sucursal, configuracion):
        ancho = cls._ancho_caracteres(configuracion.ancho_papel_mm)
        contenido = "\n".join(
            cls._centrado("PRUEBA DE IMPRESION", ancho)
            + cls._centrado(sucursal.nombre, ancho)
            + ["-" * ancho, f"Ancho: {configuracion.ancho_papel_mm} mm", "Texto de prueba", "-" * ancho]
        )
        impresora = configuracion.nombre_impresora.strip() or cls._impresora_predeterminada()
        cls._validar_impresora(impresora)
        cls._enviar_raw(
            impresora,
            cls._ticket_zpl(contenido, configuracion.ancho_papel_mm),
            configuracion.cortar_papel,
        )
        return impresora
