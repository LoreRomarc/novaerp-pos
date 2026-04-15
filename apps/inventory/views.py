from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, FormView, TemplateView
from django.shortcuts import redirect, get_object_or_404
from django.db import transaction

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

from apps.inventory.services.traslado_service import TrasladoService
from apps.inventory.services.stock_service import InventoryService


# ======================================================
# PRODUCCION
# ======================================================

class ProduccionView(LoginRequiredMixin, TemplateView):
    template_name = "inventory/produccion.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["variantes"] = ProductoVariante.objects.select_related(
            "producto_base", "color", "tipo_tela"
        ).all()

        return context

    def post(self, request):

        variante_id = request.POST.get("variante_id")

        try:
            cantidad = int(request.POST.get("cantidad"))
        except:
            cantidad = 0

        if not variante_id or cantidad <= 0:
            return redirect("inventory:produccion")

        variante = get_object_or_404(ProductoVariante, id=variante_id)

        with transaction.atomic():

            ingreso = IngresoProduccion.objects.create()

            IngresoProduccionDetalle.objects.create(
                ingreso=ingreso,
                variante=variante,
                cantidad=cantidad
            )

            InventoryService.agregar_stock(
                variante=variante,
                cantidad=cantidad,
                user=request.user,
                referencia=f"Producción {ingreso.id}",
                tipo="PRODUCCION"
            )

        return redirect("inventory:produccion")


# ======================================================
# LISTA PRODUCCION
# ======================================================

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

        with transaction.atomic():

            traslado = Traslado.objects.create(
                origen_id=form.cleaned_data["origen"],
                destino_id=form.cleaned_data["destino"],
            )

            TrasladoDetalle.objects.create(
                traslado=traslado,
                variante_id=form.cleaned_data["variante_id"],
                cantidad=form.cleaned_data["cantidad"],
            )

            TrasladoService.ejecutar_traslado(
                traslado.id,
                usuario=self.request.user
            )

        return redirect("inventory:traslado_list")


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