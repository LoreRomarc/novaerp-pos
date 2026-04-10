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
                "sku": item.variante.sku,

                "nombre": f"{item.variante.producto_base.nombre} - {item.variante.talla}",

                "color": item.variante.color.nombre if item.variante.color else None,
                "talla": item.variante.talla,

                "cantidad": str(item.cantidad),
                "precio_unitario": str(item.precio_unitario),

                "iva_linea": str(getattr(item, "iva_linea", 0)),
                "subtotal_linea": str(getattr(item, "subtotal_linea", 0)),
            }
            for item in venta.items.select_related("variante", "variante__producto_base")
        ]
    }