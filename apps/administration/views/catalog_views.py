# apps/administration/views/catalog_views.py

from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy

from apps.inventory.models import (
    Color,
    TipoTela,
    Talla
)

from apps.administration.forms import (
    ColorForm,
    TipoTelaForm,
    TallaForm
)

class ColorCreateView(CreateView):
    model = Color
    form_class = ColorForm
    template_name = "administration/catalogos/color_form.html"
    success_url = reverse_lazy("administration:color_list")


class TipoTelaCreateView(CreateView):
    model = TipoTela
    form_class = TipoTelaForm
    template_name = "administration/catalogos/tipo_tela_form.html"
    success_url = reverse_lazy("administration:tipo_tela_list")

class TallaCreateView(CreateView):
    model = Talla
    form_class = TallaForm
    template_name = "administration/catalogos/talla_form.html"
    success_url = reverse_lazy("administration:talla_list")

class ColorListView(ListView):
    model = Color
    template_name = "administration/catalogos/colores.html"
    context_object_name = "colores"


class TipoTelaListView(ListView):
    model = TipoTela
    template_name = "administration/catalogos/telas.html"
    context_object_name = "telas"


class TallaListView(ListView):
    model = Talla
    template_name = "administration/catalogos/tallas.html"
    context_object_name = "tallas"

