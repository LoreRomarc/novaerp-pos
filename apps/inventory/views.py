# apps/inventory/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, FormView
from django.shortcuts import redirect, get_object_or_404
from django import forms
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import (
    Stock,
    MovimientoStock,
    Traslado,
    TrasladoDetalle,
    ProductoVariante
)
from apps.inventory.models_produccion import (
    IngresoProduccion,
    IngresoProduccionDetalle,
)

# ======================================================
# PRODUCCION
# ======================================================

class ProduccionForm(forms.Form):
    variante_id = forms.IntegerField()
    cantidad = forms.IntegerField(min_value=1)


class ProduccionView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "inventory/produccion.html"
    form_class = ProduccionForm
    permission_required = "inventory.add_ingresoproduccion"

    def form_valid(self, form):
        variante_id = form.cleaned_data["variante_id"]
        cantidad = form.cleaned_data["cantidad"]

        with transaction.atomic():
            ingreso = IngresoProduccion.objects.create()

            detalle = IngresoProduccionDetalle.objects.create(
                ingreso=ingreso,
                variante_id=variante_id,
                cantidad=cantidad
            )

            variante = get_object_or_404(ProductoVariante, id=variante_id)

            # USAR SERVICIO CENTRAL
            from apps.inventory.services.stock_service import InventoryService

            InventoryService.agregar_stock(
                variante=variante,
                cantidad=cantidad,
                sucursal_id=self.request.session.get("sucursal_id"),
                referencia=f"Producción {ingreso.id}",
                tipo="PRODUCCION"
            )

        return redirect("produccion_list")


class ProduccionListView(LoginRequiredMixin, ListView):
    model = IngresoProduccion
    template_name = "inventory/produccion_list.html"
    context_object_name = "producciones"


# ======================================================
# STOCK
# ======================================================

class StockListView(LoginRequiredMixin, ListView):
    model = Stock
    template_name = "inventory/stock_list.html"
    context_object_name = "stocks"

    def get_queryset(self):
        return Stock.objects.select_related("variante", "sucursal")


# ======================================================
# TRASLADOS
# ======================================================

class TrasladoForm(forms.Form):
    origen = forms.IntegerField()
    destino = forms.IntegerField()
    variante_id = forms.IntegerField()
    cantidad = forms.DecimalField(min_value=1)


class TrasladoCreateView(LoginRequiredMixin, PermissionRequiredMixin, FormView):
    template_name = "inventory/traslado.html"
    form_class = TrasladoForm
    permission_required = "inventory.add_traslado"

    def form_valid(self, form):
        origen_id = form.cleaned_data["origen"]
        destino_id = form.cleaned_data["destino"]
        variante_id = form.cleaned_data["variante_id"]
        cantidad = form.cleaned_data["cantidad"]

        with transaction.atomic():
            traslado = Traslado.objects.create(
                origen_id=origen_id,
                destino_id=destino_id,
            )

            TrasladoDetalle.objects.create(
                traslado=traslado,
                variante_id=variante_id,
                cantidad=cantidad,
            )

            # ====== Actualizar stock manualmente ======
            variante = get_object_or_404(ProductoVariante, id=variante_id)

            # Restar stock del origen
            stock_origen = Stock.objects.filter(sucursal_id=origen_id, variante=variante).first()
            if not stock_origen or stock_origen.cantidad < cantidad:
                raise ValidationError(f"No hay suficiente stock en la sucursal origen ({origen_id}).")
            stock_origen.cantidad -= cantidad
            stock_origen.save()

            # Sumar stock al destino
            stock_destino, _ = Stock.objects.get_or_create(
                sucursal_id=destino_id,
                variante=variante,
                defaults={"cantidad": 0}
            )
            stock_destino.cantidad += cantidad
            stock_destino.save()

            # Registrar movimientos de inventario
            MovimientoStock.objects.create(
                variante=variante,
                sucursal_id=origen_id,
                tipo="TRASLADO",
                cantidad=-cantidad,
                referencia=f"Traslado {traslado.id} SALIDA"
            )

            MovimientoStock.objects.create(
                variante=variante,
                sucursal_id=destino_id,
                tipo="TRASLADO",
                cantidad=cantidad,
                referencia=f"Traslado {traslado.id} ENTRADA"
            )

        return redirect("traslado_list")


class TrasladoListView(LoginRequiredMixin, ListView):
    model = Traslado
    template_name = "inventory/traslado_list.html"
    context_object_name = "traslados"


# ======================================================
# MOVIMIENTOS
# ======================================================

class MovimientoListView(LoginRequiredMixin, ListView):
    model = MovimientoStock
    template_name = "inventory/movimientos.html"
    context_object_name = "movimientos"

    def get_queryset(self):
        return MovimientoStock.objects.select_related("variante", "sucursal")