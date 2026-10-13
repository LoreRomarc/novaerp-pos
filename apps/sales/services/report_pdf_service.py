"""Generación de reportes PDF con el estilo institucional del ERP."""

from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


class ReportePDFService:
    COLOR_MARCA = colors.HexColor("#182b49")
    COLOR_ACENTO = colors.HexColor("#2c7a63")
    COLOR_FONDO = colors.HexColor("#eef4f7")
    COLOR_BORDE = colors.HexColor("#dce6eb")

    @staticmethod
    def dinero(valor):
        return f"${float(valor or 0):,.0f}".replace(",", ".")

    @classmethod
    def _documento(cls, titulo, sucursal, inicio, fin):
        buffer = BytesIO()
        documento = SimpleDocTemplate(
            buffer,
            pagesize=landscape(A4),
            leftMargin=1.15 * cm,
            rightMargin=1.15 * cm,
            topMargin=1.15 * cm,
            bottomMargin=1.25 * cm,
            title=titulo,
        )
        estilos = getSampleStyleSheet()
        estilos.add(ParagraphStyle(
            name="ERPTitle",
            parent=estilos["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            leading=21,
            textColor=cls.COLOR_MARCA,
            spaceAfter=3,
            alignment=TA_CENTER,
        ))
        estilos.add(ParagraphStyle(
            name="ERPInfo",
            parent=estilos["Normal"],
            fontSize=8.5,
            leading=11,
            textColor=colors.HexColor("#52677a"),
            alignment=TA_CENTER,
        ))
        cabecera = [
            Paragraph(titulo, estilos["ERPTitle"]),
            Paragraph(
                f"<b>Sucursal:</b> {sucursal.nombre} &nbsp;&nbsp; "
                f"<b>Desde:</b> {inicio or 'Sin límite'} &nbsp;&nbsp; "
                f"<b>Hasta:</b> {fin or 'Sin límite'}",
                estilos["ERPInfo"],
            ),
            Spacer(1, .35 * cm),
        ]
        return buffer, documento, estilos, cabecera

    @staticmethod
    def _texto(valor, maximo=70):
        """Normaliza las celdas a una sola línea para evitar desfases verticales."""
        texto = str(valor or "—").replace("\n", " ").strip()
        return texto if len(texto) <= maximo else f"{texto[:maximo - 1]}…"

    @classmethod
    def _pie_pagina(cls, canvas, documento):
        canvas.saveState()
        canvas.setStrokeColor(cls.COLOR_BORDE)
        canvas.line(documento.leftMargin, .8 * cm, landscape(A4)[0] - documento.rightMargin, .8 * cm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawCentredString(
            landscape(A4)[0] / 2,
            .5 * cm,
            f"NovaERP · Reporte generado por el sistema · Página {documento.page}",
        )
        canvas.restoreState()

    @classmethod
    def _tabla(cls, datos, anchos):
        tabla = Table(datos, colWidths=anchos, repeatRows=1, hAlign="LEFT")
        tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), cls.COLOR_MARCA),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 7.4),
            ("LEADING", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), .25, cls.COLOR_BORDE),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, cls.COLOR_FONDO]),
        ]))
        return tabla

    @classmethod
    def ventas(cls, ventas, resumen, sucursal, inicio, fin):
        buffer, documento, estilos, historia = cls._documento(
            "Reporte detallado de ventas", sucursal, inicio, fin
        )
        resumen_tabla = Table([[
            Paragraph(f"<b>Total vendido</b><br/>{cls.dinero(resumen['total_general'])}", estilos["ERPInfo"]),
            Paragraph(f"<b>Efectivo</b><br/>{cls.dinero(resumen['total_efectivo'])}", estilos["ERPInfo"]),
            Paragraph(f"<b>Transferencia</b><br/>{cls.dinero(resumen['total_transferencia'])}", estilos["ERPInfo"]),
            Paragraph(f"<b>Ventas</b><br/>{resumen['cantidad_ventas']}", estilos["ERPInfo"]),
        ]], colWidths=[5.2 * cm] * 4)
        resumen_tabla.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), cls.COLOR_FONDO),
            ("BOX", (0, 0), (-1, -1), .5, cls.COLOR_BORDE),
            ("INNERGRID", (0, 0), (-1, -1), .25, cls.COLOR_BORDE),
            ("PADDING", (0, 0), (-1, -1), 7),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        historia.extend([resumen_tabla, Spacer(1, .4 * cm)])

        datos = [["Venta", "Fecha", "Producto", "Cant.", "Precio", "Efectivo", "Transfer.", "Total", "Cliente", "Vendedor"]]
        for venta in ventas:
            items = list(venta.items.all()) or [None]
            for indice, item in enumerate(items):
                producto = "—" if item is None else f"{item.nombre_producto} · {item.sku}"
                cantidad = "—" if item is None else str(item.cantidad)
                precio = "—" if item is None else cls.dinero(item.precio_unitario)
                datos.append([
                    f"#{venta.id}" if indice == 0 else "",
                    venta.creada.strftime("%d/%m/%Y %H:%M") if indice == 0 else "",
                    cls._texto(producto, 46),
                    cantidad,
                    precio,
                    cls.dinero(venta.efectivo_caja) if indice == 0 else "",
                    cls.dinero(venta.transferencia_caja) if indice == 0 else "",
                    cls.dinero(venta.total) if indice == 0 else "",
                    cls._texto(venta.cliente or "Consumidor final", 25) if indice == 0 else "",
                    cls._texto(venta.vendedor or "Sin asignar", 18) if indice == 0 else "",
                ])
        # El ancho suma exactamente el área útil de A4 horizontal (27,4 cm),
        # evitando el espacio vacío derecho y centrando visualmente la tabla.
        historia.append(cls._tabla(datos, [1.5*cm, 2.4*cm, 6.2*cm, 1.0*cm, 2.0*cm, 2.4*cm, 2.5*cm, 2.4*cm, 3.3*cm, 3.7*cm]))
        documento.build(historia, onFirstPage=cls._pie_pagina, onLaterPages=cls._pie_pagina)
        buffer.seek(0)
        return buffer

    @classmethod
    def financiero(cls, movimientos, resumen, resumen_turnos, saldo_boveda, sucursal, inicio, fin):
        buffer, documento, estilos, historia = cls._documento(
            "Reporte financiero y de caja", sucursal, inicio, fin
        )
        datos_resumen = [[
            Paragraph(f"<b>Entradas efectivo</b><br/>{cls.dinero(resumen['ventas_efectivo'] + resumen['abonos_efectivo'] + resumen['ingresos'])}", estilos["ERPInfo"]),
            Paragraph(f"<b>Salidas efectivo</b><br/>{cls.dinero(resumen['egresos'] + resumen['retiros_boveda'])}", estilos["ERPInfo"]),
            Paragraph(f"<b>Abonos a crédito</b><br/>{cls.dinero(resumen['abonos_total'])}", estilos["ERPInfo"]),
            Paragraph(f"<b>Saldo bóveda</b><br/>{cls.dinero(saldo_boveda)}", estilos["ERPInfo"]),
            Paragraph(f"<b>Turnos / diferencias</b><br/>{resumen_turnos['cantidad_turnos']} / {cls.dinero(resumen_turnos['diferencias'])}", estilos["ERPInfo"]),
        ]]
        resumen_tabla = Table(datos_resumen, colWidths=[4.1 * cm] * 5)
        resumen_tabla.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), cls.COLOR_FONDO), ("BOX", (0, 0), (-1, -1), .5, cls.COLOR_BORDE), ("INNERGRID", (0, 0), (-1, -1), .25, cls.COLOR_BORDE), ("PADDING", (0, 0), (-1, -1), 7), ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]))
        historia.extend([resumen_tabla, Spacer(1, .4 * cm)])
        datos = [["Fecha", "Tipo", "Caja", "Medio", "Usuario", "Referencia / observación", "Monto"]]
        for movimiento in movimientos:
            referencia = (
                movimiento.observacion
                or (
                    f"Venta #{movimiento.referencia_venta_id}"
                    if movimiento.referencia_venta_id
                    else ""
                )
                or (
                    f"Cambio o devolución #{movimiento.referencia_devolucion_id}"
                    if movimiento.referencia_devolucion_id
                    else "—"
                )
            )
            datos.append([
                movimiento.creado_en.strftime("%d/%m/%Y %H:%M"),
                cls._texto(movimiento.get_tipo_display(), 24),
                cls._texto(movimiento.caja.codigo, 14),
                cls._texto(movimiento.get_medio_pago_display() if movimiento.medio_pago else "—", 18),
                cls._texto(movimiento.usuario, 24),
                cls._texto(referencia, 70),
                cls.dinero(movimiento.monto),
            ])
        historia.append(cls._tabla(datos, [2.4*cm, 2.8*cm, 1.7*cm, 2.0*cm, 2.8*cm, 10.0*cm, 2.6*cm]))
        documento.build(historia, onFirstPage=cls._pie_pagina, onLaterPages=cls._pie_pagina)
        buffer.seek(0)
        return buffer
