# apps/inventory/views_variantes.py
from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum
from django.urls import reverse_lazy
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
)

from apps.inventory.mixins import InventoryAccessMixin

from apps.inventory.models import (
    ProductoVariante,
)

from apps.sales.models import (
    ListaPrecio,
    PrecioVariante,
)

# ======================================================
# FORM
# ======================================================

class VarianteForm(forms.ModelForm):

    precios_lista = {}


    class Meta:

        model = ProductoVariante

        fields = [
            "producto_base",
            "tipo_tela",
            "color",
            "talla",
            "sku",
            "codigo_barras",
            "precio_venta",
            "costo_unitario",
            "stock_minimo",
            "activo",
        ]

        widgets = {

            "producto_base": forms.Select(attrs={
                "class": "form-control"
            }),

            "tipo_tela": forms.Select(attrs={
                "class": "form-control"
            }),

            "color": forms.Select(attrs={
                "class": "form-control"
            }),

            #  CORREGIDO
            "talla": forms.Select(attrs={
                "class": "form-control"
            }),

            "sku": forms.TextInput(attrs={
                "class": "form-control"
            }),

            "codigo_barras": forms.TextInput(attrs={
                "class": "form-control"
            }),

            "precio_venta": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01"
            }),

            "costo_unitario": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01"
            }),

            "stock_minimo": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01"
            }),

            "activo": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }

    def __init__(self, *args, **kwargs):

        super().__init__(*args, **kwargs)

        self.fields["tipo_tela"].queryset = (
            self.fields["tipo_tela"]
            .queryset
            .filter(activo=True)
            .order_by("nombre")
        )

        self.fields["talla"].queryset = (
            self.fields["talla"]
            .queryset
            .filter(activo=True)
            .order_by("orden", "nombre")
        )

        self.fields["color"].queryset = (
            self.fields["color"]
            .queryset
            .order_by("nombre")
        )

        self.fields["producto_base"].queryset = (
            self.fields["producto_base"]
            .queryset
            .filter(activo=True)
            .order_by("nombre")
        )

        self.fields["producto_base"].empty_label = "Seleccione producto"
        self.fields["tipo_tela"].empty_label = "Seleccione tela"
        self.fields["color"].empty_label = "Seleccione color"
        self.fields["talla"].empty_label = "Seleccione talla"

        # ============================================
        # CAMPOS DINAMICOS DE LISTAS DE PRECIOS
        # ============================================

        self.precios_lista = {}

        for lista in ListaPrecio.objects.filter(
            activa=True
        ):

            campo = f"precio_lista_{lista.id}"

            self.fields[campo] = forms.DecimalField(
                required=False,
                label=lista.nombre,
                min_value=0,
                widget=forms.NumberInput(
                    attrs={
                        "class": "form-control",
                        "step": "0.01"
                    }
                )
            )

            self.precios_lista[campo] = lista

        # cargar precios si estamos editando

        if self.instance.pk:

            for precio in self.instance.precios.all():

                campo = (
                    f"precio_lista_{precio.lista_id}"
                )

                if campo in self.fields:

                    self.initial[campo] = precio.precio

    def save(self, commit=True):

        instancia = super().save(commit)

        for campo, lista in self.precios_lista.items():

            valor = self.cleaned_data.get(campo)

            if valor:

                PrecioVariante.objects.update_or_create(
                    variante=instancia,
                    lista=lista,
                    defaults={
                        "precio": valor
                    }
                )

        return instancia

# ======================================================
# LISTADO
# ======================================================

class VarianteListView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    ListView
):

    model = ProductoVariante

    template_name = "inventory/variante_list.html"

    context_object_name = "variantes"

    paginate_by = 50

    def get_queryset(self):

        qs = (
            ProductoVariante.objects
            .select_related(
                "producto_base",
                "tipo_tela",
                "color"
            )
            .prefetch_related("stocks")
        )

        q = self.request.GET.get("q")

        if q:

            qs = qs.filter(
                sku__icontains=q
            ) | qs.filter(
                producto_base__nombre__icontains=q
            )

        return qs

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["total_variantes"] = self.get_queryset().count()

        context["stock_total"] = (
            self.get_queryset()
            .aggregate(total=Sum("stocks__cantidad"))["total"] or 0
        )

        return context


# ======================================================
# CREAR
# ======================================================

class VarianteCreateView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    CreateView
):

    model = ProductoVariante

    form_class = VarianteForm

    template_name = "inventory/variante_form.html"

    success_url = reverse_lazy("inventory:variante_list")

    def form_valid(self, form):

        messages.success(
            self.request,
            "Variante creada correctamente"
        )

        return super().form_valid(form)


# ======================================================
# EDITAR
# ======================================================

class VarianteUpdateView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    UpdateView
):

    model = ProductoVariante

    form_class = VarianteForm

    template_name = "inventory/variante_form.html"

    success_url = reverse_lazy("inventory:variante_list")

    def form_valid(self, form):

        messages.success(
            self.request,
            "Variante actualizada correctamente"
        )

        return super().form_valid(form)