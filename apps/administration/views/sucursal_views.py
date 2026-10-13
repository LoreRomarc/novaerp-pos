# apps/administration/views/sucursal_views.py
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy

from apps.core.models import Sucursal
from apps.administration.forms import SucursalForm
from apps.administration.mixins import SuperAdminRequiredMixin


class SucursalListView(SuperAdminRequiredMixin, ListView):
    model = Sucursal
    template_name = "administration/sucursales/list.html"
    context_object_name = "sucursales"

    def get_queryset(self):
        return Sucursal.objects.select_related(
            "empresa",
            "lista_precio_default",
        ).order_by("nombre")


class SucursalCreateView(SuperAdminRequiredMixin, CreateView):
    model = Sucursal
    form_class = SucursalForm
    template_name = "administration/sucursales/form.html"
    success_url = reverse_lazy("administration:sucursal_list")


class SucursalUpdateView(SuperAdminRequiredMixin, UpdateView):
    """Permite corregir datos operativos sin recrear la sucursal."""

    model = Sucursal
    form_class = SucursalForm
    template_name = "administration/sucursales/form.html"
    success_url = reverse_lazy("administration:sucursal_list")
