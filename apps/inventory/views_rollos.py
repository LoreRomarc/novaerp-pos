# apps/inventory/views_rollos.py
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.shortcuts import redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django import forms

from apps.inventory.models_produccion import RolloTela
from apps.inventory.mixins import InventoryAccessMixin
from django.db.models import Sum, F, ExpressionWrapper, DecimalField
from django.db.models.functions import Coalesce

# ==========================================
# LISTADO DE ROLLOS
# ==========================================
class RolloListView(LoginRequiredMixin, InventoryAccessMixin, ListView):
    model = RolloTela
    template_name = "inventory/rollo_list.html"
    context_object_name = "rollos"

    def get_queryset(self):
        return (
            RolloTela.objects
            .select_related("tipo_tela", "color")
            .annotate(
                consumido=ExpressionWrapper(
                    Coalesce(F("cantidad_inicial"), 0) - Coalesce(F("cantidad_disponible"), 0),
                    output_field=DecimalField()
                )
            )
            .order_by("-creado")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        qs = self.get_queryset()

        context["total_rollos"] = qs.count()

        context["disponibles"] = qs.filter(
            estado="DISPONIBLE"
        ).count()

        context["consumo_total"] = qs.aggregate(
            total=Sum("consumido")
        )["total"] or 0

        return context


# ==========================================
# CREAR ROLLO
# ==========================================

class RolloForm(forms.ModelForm):

    class Meta:

        model = RolloTela

        fields = [
            "tipo_tela",
            "color",
            "codigo",
            "cantidad_inicial",
            "costo_por_metro"
        ]

        widgets = {

            "tipo_tela": forms.Select(attrs={
                "class": "form-control"
            }),

            "color": forms.Select(attrs={
                "class": "form-control"
            }),

            "codigo": forms.TextInput(attrs={
                "class": "form-control"
            }),

            "cantidad_inicial": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01"
            }),

            "costo_por_metro": forms.NumberInput(attrs={
                "class": "form-control",
                "step": "0.01"
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

        self.fields["color"].queryset = (
            self.fields["color"]
            .queryset
            .order_by("nombre")
        )

        self.fields["tipo_tela"].empty_label = "Seleccione una tela"
        self.fields["color"].empty_label = "Seleccione un color"

class RolloCreateView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    CreateView
):

    model = RolloTela

    form_class = RolloForm

    template_name = "inventory/rollo_create.html"

    success_url = reverse_lazy(
        "inventory:rollo_list"
    )

    def form_valid(self, form):

        obj = form.save(commit=False)

        if obj.cantidad_inicial <= 0:

            messages.error(
                self.request,
                "Cantidad inicial debe ser mayor a 0"
            )

            return self.form_invalid(form)

        obj.cantidad_disponible = obj.cantidad_inicial

        obj.save()

        self.object = obj

        messages.success(
            self.request,
            "Rollo creado correctamente"
        )

        return redirect(self.get_success_url())
        