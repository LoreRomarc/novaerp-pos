# apps/inventory/admin.py
from django.contrib import admin
from django.db import transaction, models
from django.core.exceptions import ValidationError

from apps.core.models import Sucursal
from apps.inventory.models import (
    Color,
    TipoTela,
    ProductoBase,
    ProductoVariante,
    Stock,
    MovimientoStock,
    Traslado,
    TrasladoDetalle
)

from apps.inventory.models_produccion import (
    RolloTela,
    ProduccionLote,
    ProduccionDetalle,
    IngresoProduccion,
    IngresoProduccionDetalle,
)

from apps.inventory.services.traslado_service import TrasladoService


# ======================================================
# MODELOS BASE
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
    list_filter = ("tipo_tela", "color", "talla")
    search_fields = ("sku", "producto_base__nombre", "talla")
    autocomplete_fields = ("producto_base", "tipo_tela", "color")


# ======================================================
# STOCK
# ======================================================

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ("variante", "sucursal", "cantidad")
    list_filter = ("sucursal", "variante__tipo_tela", "variante__color")
    search_fields = ("variante__sku", "variante__producto_base__nombre")
    readonly_fields = ("variante", "sucursal", "cantidad")


@admin.register(MovimientoStock)
class MovimientoStockAdmin(admin.ModelAdmin):
    list_display = ("variante", "sucursal", "tipo", "cantidad", "referencia", "creado")
    list_filter = ("tipo", "sucursal", "variante__tipo_tela", "variante__color")
    search_fields = ("variante__sku", "variante__producto_base__nombre", "referencia")
    readonly_fields = ("variante", "sucursal", "tipo", "cantidad", "referencia", "creado")


# ======================================================
# ROLLOS
# ======================================================

@admin.register(RolloTela)
class RolloTelaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "tipo_tela", "color", "cantidad_disponible", "estado")
    list_filter = ("tipo_tela", "color", "estado")
    search_fields = ("codigo",)
    autocomplete_fields = ("tipo_tela", "color")

    def save_model(self, request, obj, form, change):
        if obj.cantidad_disponible < 0:
            raise ValidationError("Cantidad no puede ser negativa.")
        super().save_model(request, obj, form, change)


# ======================================================
# PRODUCCION DETALLE INLINE
# ======================================================

class ProduccionDetalleInline(admin.TabularInline):
    model = ProduccionDetalle
    extra = 1
    autocomplete_fields = ("producto_base", "tipo_tela", "color", "variante")


# ======================================================
# INGRESO PRODUCCION
# ======================================================

class IngresoProduccionDetalleInline(admin.TabularInline):
    model = IngresoProduccionDetalle
    extra = 0


@admin.register(IngresoProduccion)
class IngresoProduccionAdmin(admin.ModelAdmin):
    list_display = ("id", "orden")
    inlines = [IngresoProduccionDetalleInline]


@admin.register(IngresoProduccionDetalle)
class IngresoProduccionDetalleAdmin(admin.ModelAdmin):
    list_display = ("ingreso", "variante", "cantidad")
    search_fields = ("variante__sku",)


# ======================================================
# PRODUCCION LOTE
# ======================================================

@admin.register(ProduccionLote)
class ProduccionLoteAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "rollo",
        "consumo_total",
        "total_prendas",
        "ejecutado",
        "stock_generado",
        "movimientos_count",
        "creado"
    )

    list_filter = ("ejecutado", "tipo_tela", "color")
    inlines = [ProduccionDetalleInline]
    actions = ["ejecutar_corte"]
    autocomplete_fields = ("rollo",)

    # ==========================
    # BLOQUEO SI YA EJECUTADO
    # ==========================
    def has_change_permission(self, request, obj=None):
        if obj and obj.ejecutado:
            return False
        return super().has_change_permission(request, obj)

    # ==========================
    # MÉTRICAS
    # ==========================
    def stock_generado(self, obj):
        try:
            sucursal_fabrica = Sucursal.objects.get(nombre__iexact="FABRICA")

            variantes = obj.detalles.values_list("variante_id", flat=True)

            total = Stock.objects.filter(
                sucursal=sucursal_fabrica,
                variante_id__in=variantes
            ).aggregate(total=models.Sum("cantidad"))["total"] or 0

            return total

        except Sucursal.DoesNotExist:
            return 0

    def movimientos_count(self, obj):
        try:
            sucursal_fabrica = Sucursal.objects.get(nombre__iexact="FABRICA")
            return MovimientoStock.objects.filter(
                sucursal=sucursal_fabrica,
                referencia__icontains=f"Lote {obj.id} - Corte"
            ).count()
        except Sucursal.DoesNotExist:
            return 0

    movimientos_count.short_description = "Movimientos"

    # ==========================
    # EJECUTAR CORTE
    # ==========================
    def ejecutar_corte(self, request, queryset):

        for lote in queryset:

            if lote.ejecutado:
                self.message_user(
                    request,
                    f"Lote {lote.id} ya ejecutado",
                    level="warning"
                )
                continue

            try:
                detalles = lote.detalles.all()

                if not detalles.exists():
                    raise ValidationError("El lote no tiene detalles.")

                sucursal_fabrica = Sucursal.objects.get(nombre__iexact="FABRICA")

                movimientos = []

                with transaction.atomic():

                    for d in detalles:

                        if not d.variante:
                            raise ValidationError(
                                f"Detalle {d.id} sin variante"
                            )

                        stock_obj, _ = Stock.objects.get_or_create(
                            variante=d.variante,
                            sucursal=sucursal_fabrica,
                            defaults={"cantidad": 0}
                        )

                        stock_obj.cantidad += d.cantidad
                        stock_obj.save(update_fields=["cantidad"])

                        movimientos.append(
                            MovimientoStock(
                                variante=d.variante,
                                sucursal=sucursal_fabrica,
                                tipo="PRODUCCION",
                                cantidad=d.cantidad,
                                referencia=f"Lote {lote.id} - Corte"
                            )
                        )

                    MovimientoStock.objects.bulk_create(movimientos)

                    lote.ejecutado = True
                    lote.save(update_fields=["ejecutado"])

                self.message_user(
                    request,
                    f"Lote {lote.id} ejecutado correctamente",
                    level="success"
                )

            except Exception as e:
                self.message_user(
                    request,
                    f"Error en lote {lote.id}: {str(e)}",
                    level="error"
                )


# ======================================================
# TRASLADOS
# ======================================================

class TrasladoDetalleInline(admin.TabularInline):
    model = TrasladoDetalle
    extra = 1
    autocomplete_fields = ("variante",)


@admin.register(Traslado)
class TrasladoAdmin(admin.ModelAdmin):

    list_display = ("id", "origen", "destino", "ejecutado", "creado")
    list_filter = ("ejecutado", "origen", "destino")

    inlines = [TrasladoDetalleInline]
    actions = ["ejecutar_traslado"]

    def has_change_permission(self, request, obj=None):
        if obj and obj.ejecutado:
            return False
        return super().has_change_permission(request, obj)

    def ejecutar_traslado(self, request, queryset):

        for traslado in queryset:

            try:
                TrasladoService.ejecutar_traslado(traslado.id)

                self.message_user(
                    request,
                    f"Traslado {traslado.id} ejecutado correctamente",
                    level="success"
                )

            except Exception as e:
                self.message_user(
                    request,
                    f"Error en traslado {traslado.id}: {str(e)}",
                    level="error"
                )

    ejecutar_traslado.short_description = "Ejecutar traslado"


# ======================================================
# PRODUCCION DETALLE
# ======================================================

@admin.register(ProduccionDetalle)
class ProduccionDetalleAdmin(admin.ModelAdmin):
    list_display = (
        "lote",
        "producto_base",
        "talla",
        "cantidad",
        "variante",
        "tipo_tela",
        "color",
    )
    list_filter = ("talla", "tipo_tela", "color")
    search_fields = ("producto_base__nombre", "variante__sku")