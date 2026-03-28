# apps/inventory/admin.py
# apps/inventory/admin.py
from django.contrib import admin
from apps.inventory.models import (
    Color, TipoTela, ProductoBase, ProductoVariante
)
from apps.inventory.models_produccion import RolloTela, ProduccionLote, ProduccionDetalle
from apps.inventory.services.corte_service import CorteService

# ======================================================
# MODELOS BASE PARA CREAR COLORES, TELAS Y PRODUCTOS
# ======================================================

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo_hex")
    search_fields = ("nombre", "codigo_hex")


@admin.register(TipoTela)
class TipoTelaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descripcion", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(ProductoBase)
class ProductoBaseAdmin(admin.ModelAdmin):
    list_display = ("nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)


@admin.register(ProductoVariante)
class ProductoVarianteAdmin(admin.ModelAdmin):
    list_display = ("sku", "producto_base", "tipo_tela", "color", "talla")
    list_filter = ("tipo_tela", "color")
    search_fields = ("sku", "producto_base__nombre", "talla")
    autocomplete_fields = ("producto_base", "tipo_tela", "color")

# ======================================================
# ROLLOS
# ======================================================

@admin.register(RolloTela)
class RolloTelaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "tipo_tela", "color", "cantidad_disponible", "estado")
    list_filter = ("tipo_tela", "color", "estado")
    search_fields = ("codigo",)
    autocomplete_fields = ("tipo_tela", "color")

# ======================================================
# PRODUCCION CORTE
# ======================================================

class ProduccionDetalleInline(admin.TabularInline):
    model = ProduccionDetalle
    extra = 1
    autocomplete_fields = ("producto_base", "tipo_tela", "color", "variante")


@admin.register(ProduccionLote)
class ProduccionLoteAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "rollo",
        "consumo_total",
        "total_prendas",
        "ejecutado",
        "creado"
    )

    inlines = [ProduccionDetalleInline]

    actions = ["ejecutar_corte"]

    autocomplete_fields = ("rollo",)

    def ejecutar_corte(self, request, queryset):

        for lote in queryset:

            if lote.ejecutado:
                self.message_user(request, f"Lote {lote.id} ya ejecutado", level="warning")
                continue

            try:
                items = []

                for d in lote.detalles.all():
                    items.append({
                        "producto_base_id": d.producto_base_id,
                        "talla": d.talla,
                        "cantidad": d.cantidad,
                    })

                CorteService.ejecutar_corte(
                    rollo_id=lote.rollo_id,
                    es_completo=True,
                    metros_usados=None,
                    items=items
                )

            except Exception as e:
                self.message_user(request, str(e), level="error")

    ejecutar_corte.short_description = "Ejecutar corte seleccionado"