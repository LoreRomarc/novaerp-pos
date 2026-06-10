# apps/sales/services/serializers.py

def serializar_venta(venta):
    return {
        "id": venta.id,
        "estado": venta.estado,
        "tipo_venta": getattr(venta, "tipo_venta", None),

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
            for item in venta.items.select_related("variante", "variante__producto_base")
        ]
    }