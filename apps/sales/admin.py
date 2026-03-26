from django.contrib import admin
from django.db.models import Q
from .models import Caja, TurnoCajaUsuario, Venta, VentaItem, ListaPrecio, PrecioVariante
from .models_caja_enterprise import TurnoCaja, CajaMovimiento, ArqueoTurno, ArqueoDenominacion, Boveda

# =========================================================
# CAJA
# =========================================================
@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ["codigo", "nombre", "sucursal", "activa"]
    list_filter = ["sucursal", "activa"]
    search_fields = ["codigo", "nombre"]

# =========================================================
# TURNO CAJA
# =========================================================
@admin.register(TurnoCaja)
class TurnoCajaAdmin(admin.ModelAdmin):
    list_display = ["caja", "usuario_apertura", "sucursal", "estado", "abierto_en", "cerrado_en"]
    list_filter = ["estado", "sucursal"]
    search_fields = ["caja__codigo", "usuario_apertura__username"]

# =========================================================
# CAJEROS EN TURNO
# =========================================================
@admin.register(TurnoCajaUsuario)
class TurnoCajaUsuarioAdmin(admin.ModelAdmin):
    list_display = ["turno", "usuario", "activo", "asignado_en", "desasignado_en"]
    list_filter = ["activo"]
    search_fields = ["usuario__username"]

# =========================================================
# MOVIMIENTOS DE CAJA
# =========================================================
@admin.register(CajaMovimiento)
class CajaMovimientoAdmin(admin.ModelAdmin):
    list_display = ["turno", "usuario", "tipo", "medio_pago", "monto", "referencia_venta", "creado_en"]
    list_filter = ["tipo", "medio_pago"]
    search_fields = ["usuario__username"]
    readonly_fields = ["hash_integridad", "creado_en"]

    def has_change_permission(self, request, obj=None):
        return False
    def has_delete_permission(self, request, obj=None):
        return False

# =========================================================
# ARQUEO
# =========================================================
class ArqueoDenominacionInline(admin.TabularInline):
    model = ArqueoDenominacion
    extra = 1

@admin.register(ArqueoTurno)
class ArqueoTurnoAdmin(admin.ModelAdmin):
    list_display = ["turno", "realizado_por", "creado_en", "total_contado", "diferencia"]
    inlines = [ArqueoDenominacionInline]

# =========================================================
# BÓVEDA
# =========================================================
@admin.register(Boveda)
class BovedaAdmin(admin.ModelAdmin):
    list_display = ["sucursal", "saldo_actual", "actualizada_en"]
    readonly_fields = ["actualizada_en"]

# =========================================================
# VENTA ITEMS INLINE
# =========================================================
class VentaItemInline(admin.TabularInline):
    model = VentaItem
    extra = 1
    readonly_fields = ["subtotal_linea", "iva_linea", "total_linea"]

# =========================================================
# VENTA
# =========================================================
@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ["id", "sucursal", "usuario", "estado", "total", "creada"]
    list_filter = ["estado", "sucursal", "tipo_venta"]
    search_fields = ["id", "usuario__username"]
    inlines = [VentaItemInline]

    actions = ["cerrar_ventas"]

    def cerrar_ventas(self, request, queryset):
        for venta in queryset:
            try:
                venta.cerrar_venta()
            except Exception as e:
                self.message_user(request, f"Error en venta {venta.id}: {e}")

    cerrar_ventas.short_description = "Cerrar ventas seleccionadas"

# =========================================================
# VENTA ITEM
# =========================================================
@admin.register(VentaItem)
class VentaItemAdmin(admin.ModelAdmin):
    list_display = ["venta", "variante", "cantidad", "precio_unitario", "subtotal_linea", "iva_linea", "total_linea"]
    search_fields = ["venta__id"]

# =========================================================
# LISTA DE PRECIOS
# =========================================================
@admin.register(ListaPrecio)
class ListaPrecioAdmin(admin.ModelAdmin):
    list_display = ["nombre", "sucursal", "tipo_venta", "activa"]
    list_filter = ["sucursal", "tipo_venta", "activa"]

# =========================================================
# PRECIO VARIANTE
# =========================================================
@admin.register(PrecioVariante)
class PrecioVarianteAdmin(admin.ModelAdmin):
    list_display = ["variante", "lista", "precio"]
    list_filter = ["lista"]