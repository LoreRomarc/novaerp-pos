# apps/administration/views/precio_views.py

from django.views.generic import (
    ListView,
    CreateView
)

from django.urls import reverse_lazy

from apps.sales.models import (
    ListaPrecio,
    PrecioVariante
)

from apps.administration.forms import (
    ListaPrecioForm,
    PrecioVarianteForm
)


class ListaPrecioListView(ListView):
    model = ListaPrecio
    template_name = "administration/precios/listas.html"
    context_object_name = "listas"


class ListaPrecioCreateView(CreateView):
    model = ListaPrecio
    form_class = ListaPrecioForm
    template_name = "administration/precios/lista_form.html"
    success_url = reverse_lazy("administration:lista_precio_list")


class PrecioVarianteListView(ListView):
    model = PrecioVariante
    template_name = "administration/precios/precios.html"
    context_object_name = "precios"


class PrecioVarianteCreateView(CreateView):
    model = PrecioVariante
    form_class = PrecioVarianteForm
    template_name = "administration/precios/precio_form.html"
    success_url = reverse_lazy("administration:precio_variante_list")