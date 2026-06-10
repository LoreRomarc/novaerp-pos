# apps/administration/views/sucursal_views.py
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy

from apps.core.models import Sucursal
from apps.administration.forms import SucursalForm


class SucursalListView(ListView):
    model = Sucursal
    template_name = "administration/sucursales/list.html"
    context_object_name = "sucursales"


class SucursalCreateView(CreateView):
    model = Sucursal
    form_class = SucursalForm
    template_name = "administration/sucursales/form.html"
    success_url = reverse_lazy("administration:sucursal_list")