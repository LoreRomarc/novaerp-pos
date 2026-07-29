# apps/sales/services/serializers.py

def serializar_venta(venta):

    return {
        "id": venta.id,
        "uuid": str(venta.uuid),
        "estado": venta.estado,
        "tipo_venta": venta.tipo_venta,

        "cliente": venta.cliente or "",
        "observaciones": venta.observaciones or "",

        "efectivo": str(venta.monto_efectivo or 0),
        "transferencia": str(venta.monto_transferencia or 0),
        "tarjeta": str(venta.monto_tarjeta or 0),

        "subtotal": str(venta.subtotal),
        "iva": str(venta.total_iva),
        "total": str(venta.total),

        "items": [
            {
                "id": item.id,
                "variante_id": item.variante.id,
                "sku": item.sku,
                "nombre": item.nombre_producto,
                "color": item.color,
                "talla": item.talla,
                "cantidad": str(item.cantidad),
                "precio_unitario": str(item.precio_unitario),
                "iva_linea": str(item.iva_linea or 0),
                "subtotal_linea": str(item.subtotal_linea or 0),
            }
            for item in venta.items.select_related(
                "variante",
                "variante__producto_base"
            )
        ]
    }