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
            .select_related("producto_base", "color", "tipo_tela")
            .filter(
                Q(sku__icontains=query) |
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

                # 🔥 TEXTO PARA DROPDOWN
                "text": f"{v.producto_base.nombre} - {v.color.nombre} - {v.talla}",

                # 🔥 PARA POS
                "nombre": f"{v.producto_base.nombre} - {v.color.nombre} - {v.talla}",

                "sku": v.sku,
                "color": v.color.nombre if v.color else "",
                "talla": v.talla,
            }
            for v in variantes
        ]