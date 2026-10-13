# apps/inventory/services/search_service.py
from django.db.models import Q
from apps.inventory.models import ProductoVariante


class InventorySearchService:

    @staticmethod
    def search_variantes(query, limit=10):

        if not query:
            return ProductoVariante.objects.none()

        return (
            ProductoVariante.objects
            .select_related("producto_base", "color", "tipo_tela", "talla")
            .filter(
                Q(sku__icontains=query) |
                Q(codigo_barras__icontains=query) |
                Q(producto_base__nombre__icontains=query) |
                Q(color__nombre__icontains=query) |
                Q(tipo_tela__nombre__icontains=query)
            )[:limit]
        )

    @staticmethod
    def serialize(variantes):

        return [
            {
                "id": v.id,
                "producto_base_id": v.producto_base_id,

                # 🔥 TEXTO PARA DROPDOWN
                "text": " - ".join(
                    parte for parte in [
                        v.producto_base.nombre,
                        v.color.nombre if v.color else "",
                        v.talla.nombre if v.talla else str(v.talla or ""),
                    ] if parte
                ),

                # 🔥 PARA POS
                "nombre": " - ".join(
                    parte for parte in [
                        v.producto_base.nombre,
                        v.color.nombre if v.color else "",
                        v.talla.nombre if v.talla else str(v.talla or ""),
                    ] if parte
                ),

                "sku": v.sku,
                "codigo_barras": v.codigo_barras or "",
                "color": v.color.nombre if v.color else "",
                "talla": v.talla.nombre if v.talla else "",
            }
            for v in variantes
        ]
