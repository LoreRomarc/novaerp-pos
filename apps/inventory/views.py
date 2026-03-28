# apps/inventory/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.views.generic import ListView, CreateView, DetailView, FormView
from django.shortcuts import redirect, get_object_or_404
from django.urls import reverse_lazy
from django import forms
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import (
    Stock,
    MovimientoStock,
    Traslado,
    TrasladoDetalle,
)
from apps.inventory.models_produccion import (
    IngresoProduccion,
    IngresoProduccionDetalle,
)
from apps.inventory.services.stock_domain_service import StockDomainService


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

            IngresoProduccionDetalle.objects.create(
                ingreso=ingreso,
                variante_id=variante_id,
                cantidad=cantidad
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

            StockDomainService.ejecutar_traslado(traslado)

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