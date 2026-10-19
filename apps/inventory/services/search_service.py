# apps/inventory/services/search_service.py
from django.db.models import Q
from apps.inventory.models import ProductoVariante, normalizar_busqueda


class InventorySearchService:

    @staticmethod
    def search_variantes(query, limit=10):

        if not query:
            return ProductoVariante.objects.none()

        # Los SKU y códigos conservan un filtro indexable; los nombres se
        # comparan además en Python para que "sueter" encuentre "SUÉTER"
        # también en instalaciones sin la extensión PostgreSQL unaccent.
        base = ProductoVariante.objects.select_related(
            "producto_base", "color", "tipo_tela", "talla"
        ).filter(activo=True)
        coincidencias_codigo = list(base.filter(
            Q(sku__icontains=query) | Q(codigo_barras__icontains=query)
        )[:limit])
        termino = normalizar_busqueda(query)
        vistos = {variante.pk for variante in coincidencias_codigo}
        resultado = list(coincidencias_codigo)
        for variante in base.order_by("producto_base__nombre", "sku"):
            if variante.pk in vistos:
                continue
            if termino in normalizar_busqueda(variante.nombre_completo):
                resultado.append(variante)
                vistos.add(variante.pk)
                if len(resultado) >= limit:
                    break
        return resultado

    @staticmethod
    def serialize(variantes):

        return [
            {
                "id": v.id,
                "producto_base_id": v.producto_base_id,

                "text": v.nombre_completo,
                "nombre": v.nombre_completo,

                "sku": v.sku,
                "codigo_barras": v.codigo_barras or "",
                "color": v.color.nombre if v.color else "",
                "talla": v.talla.nombre if v.talla else "",
            }
            for v in variantes
        ]
