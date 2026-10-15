# apps/administration/views/catalog_views.py

from django.contrib import messages
from django.db.models import Q
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView, CreateView, UpdateView
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
from apps.administration.mixins import SuperAdminRequiredMixin

class CatalogoListMixin:
    paginate_by = 30
    search_fields = ("nombre",)

    def get_queryset(self):
        queryset = super().get_queryset()
        query = self.request.GET.get("q", "").strip()
        estado = self.request.GET.get("estado", "")
        if query:
            filtro = Q()
            for field in self.search_fields:
                filtro |= Q(**{f"{field}__icontains": query})
            queryset = queryset.filter(filtro)
        if estado in {"activo", "inactivo"} and hasattr(self.model, "activo"):
            queryset = queryset.filter(activo=estado == "activo")
        return queryset


class ColorCreateView(SuperAdminRequiredMixin, CreateView):
    model = Color
    form_class = ColorForm
    template_name = "administration/catalogos/color_form.html"
    success_url = reverse_lazy("administration:color_list")


class ColorUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = Color
    form_class = ColorForm
    template_name = "administration/catalogos/color_form.html"
    success_url = reverse_lazy("administration:color_list")


class TipoTelaCreateView(SuperAdminRequiredMixin, CreateView):
    model = TipoTela
    form_class = TipoTelaForm
    template_name = "administration/catalogos/tipo_tela_form.html"
    success_url = reverse_lazy("administration:tipo_tela_list")


class TipoTelaUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = TipoTela
    form_class = TipoTelaForm
    template_name = "administration/catalogos/tipo_tela_form.html"
    success_url = reverse_lazy("administration:tipo_tela_list")

class TallaCreateView(SuperAdminRequiredMixin, CreateView):
    model = Talla
    form_class = TallaForm
    template_name = "administration/catalogos/talla_form.html"
    success_url = reverse_lazy("administration:talla_list")


class TallaUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = Talla
    form_class = TallaForm
    template_name = "administration/catalogos/talla_form.html"
    success_url = reverse_lazy("administration:talla_list")


class CatalogoDeleteMixin(SuperAdminRequiredMixin, View):
    model = None
    success_url = None

    def post(self, request, pk):
        objeto = get_object_or_404(self.model, pk=pk)
        try:
            objeto.delete()
            messages.success(request, "Registro eliminado porque no tenía historial asociado.")
        except ProtectedError:
            messages.error(
                request,
                "No se puede eliminar porque ya tiene productos, rollos o movimientos relacionados. Desactívelo para conservar la trazabilidad.",
            )
        return redirect(self.success_url)


class ColorDeleteView(CatalogoDeleteMixin):
    model = Color
    success_url = reverse_lazy("administration:color_list")


class TipoTelaDeleteView(CatalogoDeleteMixin):
    model = TipoTela
    success_url = reverse_lazy("administration:tipo_tela_list")


class TallaDeleteView(CatalogoDeleteMixin):
    model = Talla
    success_url = reverse_lazy("administration:talla_list")

class ColorListView(SuperAdminRequiredMixin, CatalogoListMixin, ListView):
    model = Color
    template_name = "administration/catalogos/colores.html"
    context_object_name = "colores"


class TipoTelaListView(SuperAdminRequiredMixin, CatalogoListMixin, ListView):
    model = TipoTela
    template_name = "administration/catalogos/telas.html"
    context_object_name = "telas"


class TallaListView(SuperAdminRequiredMixin, CatalogoListMixin, ListView):
    model = Talla
    template_name = "administration/catalogos/tallas.html"
    context_object_name = "tallas"

