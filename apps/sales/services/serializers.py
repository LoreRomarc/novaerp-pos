# apps/sales/services/serializers.py

def serializar_venta(venta):
    return {
        "id": venta.id,
        "subtotal": float(venta.subtotal),
        "iva": float(venta.total_iva),
        "total": float(venta.total),
        "items": [
            {
                "id": item.id,
                "nombre": item.producto.nombre,
                "cantidad": float(item.cantidad),
                "precio": float(item.precio_unitario),
                "iva": float(item.iva_linea),
                "subtotal": float(item.total_linea),
            }
            for item in venta.items.select_related("producto").order_by("id")
        ]
    }