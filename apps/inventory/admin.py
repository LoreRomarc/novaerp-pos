from decimal import Decimal
from django.contrib import admin
import nested_admin

from apps.inventory.models import (
    Color, TipoTela, ProductoBase, ProductoVariante,
    Producto, Stock, MovimientoStock,
)
from apps.inventory.models_produccion import IngresoProduccion, IngresoProduccionDetalle, OrdenCorte, OrdenCorteDetalle, RolloTela
from apps.sales.models import ListaPrecio, PrecioVariante

# =========================================================
# COLORES
# =========================================================
@admin.register(Color)
class ColorAdmin(admin.ModelAdmin):
    list_display = ["nombre", "codigo_hex"]
    search_fields = ["nombre", "codigo_hex"]  # <-- agregado

# =========================================================
# TELAS
# =========================================================
@admin.register(TipoTela)
class TipoTelaAdmin(admin.ModelAdmin):
    list_display = ["nombre", "activo"]
    search_fields = ["nombre"]  # <-- agregado

# =========================================================
# STOCK INLINE
# =========================================================
class StockInline(nested_admin.NestedTabularInline):
    model = Stock
    extra = 1
    autocomplete_fields = ["sucursal"]

# =========================================================
# PRECIO VARIANTE INLINE
# =========================================================
class PrecioVarianteInline(nested_admin.NestedTabularInline):
    model = PrecioVariante
    extra = 1
    autocomplete_fields = ["lista"]

# =========================================================
# VARIANTE INLINE (incluye Stock y Precio)
# =========================================================
class ProductoVarianteInline(nested_admin.NestedTabularInline):
    model = ProductoVariante
    extra = 1
    autocomplete_fields = ["tipo_tela", "color"]
    inlines = [StockInline, PrecioVarianteInline]

# =========================================================
# PRODUCTO BASE ADMIN (todo desde aquí)
# =========================================================
@admin.register(ProductoBase)
class ProductoBaseAdmin(nested_admin.NestedModelAdmin):
    list_display = ["nombre", "activo"]
    search_fields = ["nombre"]
    inlines = [ProductoVarianteInline]

# =========================================================
# PRODUCTO VARIANTE ADMIN (para consultas rápidas)
# =========================================================
@admin.register(ProductoVariante)
class ProductoVarianteAdmin(admin.ModelAdmin):
    list_display = ["producto_base", "tipo_tela", "color", "talla", "sku"]

# =========================================================
# PRODUCTO POS
# =========================================================
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ["nombre", "variante", "codigo_barras", "tipo_iva", "activo"]

# =========================================================
# STOCK
# =========================================================
@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ["producto_display", "sucursal", "cantidad"]

    @admin.display(description="Producto")
    def producto_display(self, obj):
        return obj.variante

# =========================================================
# MOVIMIENTO STOCK
# =========================================================
@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ["producto_display", "sucursal", "tipo", "cantidad", "referencia", "creado"]

    @admin.display(description="Producto")
    def producto_display(self, obj):
        return obj.variante

# =========================================================
# PRODUCCION
# =========================================================
@admin.register(RolloTela)
class RolloTelaAdmin(admin.ModelAdmin):
    list_display = ["codigo", "tipo_tela", "color", "estado"]

@admin.register(OrdenCorte)
class OrdenCorteAdmin(admin.ModelAdmin):
    list_display = ["id", "sucursal", "estado", "detalles_count"]

    @admin.display(description="Cantidad de Detalles")
    def detalles_count(self, obj):
        return obj.detalles.count()

@admin.register(OrdenCorteDetalle)
class OrdenCorteDetalleAdmin(admin.ModelAdmin):
    list_display = ["orden", "variante", "cantidad"]

@admin.register(IngresoProduccion)
class IngresoProduccionAdmin(admin.ModelAdmin):
    list_display = ["id", "orden"]

@admin.register(IngresoProduccionDetalle)
class IngresoProduccionDetalleAdmin(admin.ModelAdmin):
    list_display = ["ingreso", "variante", "cantidad"]