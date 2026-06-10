from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DetailView,
)

from apps.inventory.mixins import InventoryAccessMixin
from apps.inventory.models import (
    ProductoBase,
)


# ======================================================
# FORM
# ======================================================

class ProductoBaseForm(forms.ModelForm):

    class Meta:

        model = ProductoBase

        fields = [
            "nombre",
            "descripcion",
            "activo",
        ]

        widgets = {

            "nombre": forms.TextInput(attrs={
                "class": "form-control"
            }),

            "descripcion": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 4
            }),

            "activo": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }


# ======================================================
# LISTADO
# ======================================================

class ProductoListView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    ListView
):

    model = ProductoBase

    template_name = "inventory/producto_list.html"

    context_object_name = "productos"

    paginate_by = 50

    def get_queryset(self):

        qs = (
            ProductoBase.objects
            .prefetch_related("variantes")
            .order_by("-id")
        )

        q = self.request.GET.get("q")

        if q:

            qs = qs.filter(
                nombre__icontains=q
            )

        return qs


# ======================================================
# DETALLE
# ======================================================

class ProductoDetailView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    DetailView
):

    model = ProductoBase

    template_name = "inventory/producto_detail.html"

    context_object_name = "producto"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["variantes"] = (
            self.object.variantes
            .select_related(
                "tipo_tela",
                "color",
                "talla"
            )
            .prefetch_related("stocks")
        )

        return context


# ======================================================
# CREAR
# ======================================================

class ProductoCreateView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    CreateView
):

    model = ProductoBase

    form_class = ProductoBaseForm

    template_name = "inventory/producto_form.html"

    success_url = reverse_lazy("inventory:producto_list")

    def form_valid(self, form):

        messages.success(
            self.request,
            "Producto creado correctamente"
        )

        return super().form_valid(form)


# ======================================================
# EDITAR
# ======================================================

class ProductoUpdateView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    UpdateView
):

    model = ProductoBase

    form_class = ProductoBaseForm

    template_name = "inventory/producto_form.html"

    success_url = reverse_lazy("inventory:producto_list")

    def form_valid(self, form):

        messages.success(
            self.request,
            "Producto actualizado correctamente"
        )

        return super().form_valid(form)