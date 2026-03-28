# apps/sales/services/serializers.py
from decimal import Decimal


def serializar_venta(venta):

    return {
        "id": venta.id,
        "estado": venta.estado,
        "tipo_venta": getattr(venta, "tipo_venta", None),

        "subtotal": str(venta.subtotal),
        "iva": str(getattr(venta, "total_iva", 0)),
        "total": str(venta.total),

        "items": [
            {
                "id": item.id,

                # VARIANTE (NUEVO MODELO)
                "variante_id": item.variante.id,
                "sku": item.variante.sku,

                "nombre": f"{item.variante.producto_base.nombre} - {item.variante.talla}",

                "color": getattr(item.variante, "color", None).nombre
                if hasattr(item.variante, "color") and item.variante.color else None,

                "talla": item.variante.talla,

                "cantidad": str(item.cantidad),
                "precio_unitario": str(item.precio_unitario),
                "subtotal": str(item.subtotal()),
            }
            for item in venta.items.select_related("variante", "variante__producto_base")
        ]
    }