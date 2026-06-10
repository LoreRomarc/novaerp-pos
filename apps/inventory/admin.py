# apps/inventory/admin.py
from django.contrib import admin

from apps.inventory.models import (
    Color,
    TipoTela,
    Talla,
    ProductoBase,
    ProductoVariante,
    Stock,
    MovimientoStock,
    Traslado,
    TrasladoDetalle,
)

from apps.inventory.models_produccion import (
    RolloTela,
    MovimientoRollo,
    CorteRollo,
    ProduccionLote,
    ProduccionDetalle,
)

# ======================================================
# MAESTROS
# ======================================================

@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "codigo_hex")
    search_fields = ("nombre",)
    ordering = ("nombre",)


@admin.register(TipoTela)
class TipoTelaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)
    ordering = ("nombre",)


@admin.register(Talla)
class TallaAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "orden", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)
    ordering = ("orden", "nombre")


@admin.register(ProductoBase)
class ProductoBaseAdmin(admin.ModelAdmin):
    list_display = ("id", "nombre", "activo")
    list_filter = ("activo",)
    search_fields = ("nombre",)
    ordering = ("nombre",)


# ======================================================
# PRODUCTO VARIANTE
# ======================================================

@admin.register(ProductoVariante)
class ProductoVarianteAdmin(admin.ModelAdmin):

    list_display = (
        "sku",
        "producto_base",
        "tipo_tela",
        "color",
        "talla",
        "precio_venta",
        "stock_total",
        "activo",
    )

    list_filter = (
        "tipo_tela",
        "color",
        "talla",
        "activo",
    )

    search_fields = (
        "sku",
        "codigo_barras",
        "producto_base__nombre",
        "tipo_tela__nombre",
        "color__nombre",
        "talla__nombre",
    )

    autocomplete_fields = (
        "producto_base",
        "tipo_tela",
        "color",
        "talla",
    )

    list_select_related = (
        "producto_base",
        "tipo_tela",
        "color",
        "talla",
    )

    ordering = ("-id",)


# ======================================================
# STOCK
# ======================================================

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):

    list_display = (
        "variante",
        "sucursal",
        "cantidad",
        "costo_promedio",
    )

    list_filter = ("sucursal",)

    search_fields = (
        "variante__sku",
        "variante__producto_base__nombre",
        "sucursal__nombre",
    )

    autocomplete_fields = ("variante", "sucursal")

    list_select_related = ("variante", "sucursal")


# ======================================================
# MOVIMIENTOS STOCK
# ======================================================

@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "variante",
        "sucursal",
        "tipo",
        "cantidad",
        "saldo_post_movimiento",
        "usuario",
        "creado",
    )

    list_filter = ("tipo", "sucursal", "creado")

    search_fields = (
        "variante__sku",
        "variante__producto_base__nombre",
        "referencia",
    )

    autocomplete_fields = ("variante", "sucursal", "usuario")

    list_select_related = ("variante", "sucursal", "usuario")

    date_hierarchy = "creado"

    ordering = ("-id",)


# ======================================================
# TRASLADOS
# ======================================================

class TrasladoDetalleInline(admin.TabularInline):
    model = TrasladoDetalle
    extra = 1
    autocomplete_fields = ("variante",)


@admin.register(Traslado)
class TrasladoAdmin(admin.ModelAdmin):

    list_display = (
        "numero",
        "tipo",
        "estado",
        "origen",
        "destino",
        "total_items",
        "total_unidades",
        "creado",
    )

    list_filter = ("tipo", "estado", "creado")

    search_fields = ("numero", "motivo", "observaciones")

    autocomplete_fields = ("origen", "destino", "enviado_por", "recibido_por")

    inlines = [TrasladoDetalleInline]

    readonly_fields = ("numero", "creado", "actualizado")

    ordering = ("-id",)


@admin.register(TrasladoDetalle)
class TrasladoDetalleAdmin(admin.ModelAdmin):

    list_display = ("traslado", "variante", "cantidad")

    search_fields = (
        "traslado__numero",
        "variante__sku",
        "variante__producto_base__nombre",
    )

    autocomplete_fields = ("traslado", "variante")


# ======================================================
# ROLLOS
# ======================================================

@admin.register(RolloTela)
class RolloTelaAdmin(admin.ModelAdmin):

    list_display = (
        "codigo",
        "tipo_tela",
        "color",
        "cantidad_inicial",
        "cantidad_disponible",
        "estado",
    )

    list_filter = ("tipo_tela", "color", "estado")

    search_fields = (
        "codigo",
        "tipo_tela__nombre",
        "color__nombre",
    )

    autocomplete_fields = ("tipo_tela", "color")

    list_select_related = ("tipo_tela", "color")


@admin.register(MovimientoRollo)
class MovimientoRolloAdmin(admin.ModelAdmin):

    list_display = (
        "rollo",
        "tipo",
        "cantidad",
        "saldo_post",
        "usuario",
        "creado",
    )

    list_filter = ("tipo", "creado")

    search_fields = (
        "rollo__codigo",
        "referencia",
    )

    autocomplete_fields = ("rollo", "usuario")


# ======================================================
# PRODUCCIÓN
# ======================================================

class ProduccionDetalleInline(admin.TabularInline):
    model = ProduccionDetalle
    extra = 1
    autocomplete_fields = ("variante",)

class CorteRolloInline(admin.TabularInline):
    model = CorteRollo
    extra = 0
    autocomplete_fields = ("rollo",)

@admin.register(ProduccionLote)
class ProduccionLoteAdmin(admin.ModelAdmin):

    list_display = (
        "referencia",
        "sucursal",
        "consumo_total",
        "total_prendas",
        "costo_total",
        "operario",
        "ejecutado",
        "creado",
    )

    list_filter = (
        "sucursal",
        "ejecutado",
        "creado",
    )

    search_fields = (
        "referencia",
        "operario__username",
    )

    autocomplete_fields = (
        "sucursal",
        "operario",
    )

    inlines = [ProduccionDetalleInline]
    inlines = [
        CorteRolloInline,
        ProduccionDetalleInline,
    ]

    readonly_fields = (
        "creado",
    )

    ordering = ("-id",)


@admin.register(ProduccionDetalle)
class ProduccionDetalleAdmin(admin.ModelAdmin):

    list_display = (
        "lote",
        "variante",
        "cantidad",
        "consumo_total",
        "costo_total",
    )

    list_filter = ("lote",)

    search_fields = (
        "lote__referencia",
        "variante__sku",
        "variante__producto_base__nombre",
    )

    autocomplete_fields = ("lote", "variante")