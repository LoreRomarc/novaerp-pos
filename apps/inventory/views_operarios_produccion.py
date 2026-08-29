# apps/inventory/views_operarios_produccion.py
from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.inventory.mixins import InventoryAccessMixin
from apps.inventory.models_produccion import (
    OperarioProduccion,
)
from apps.sales.mixins import SucursalIsolationMixin


class OperarioProduccionForm(forms.ModelForm):
    class Meta:
        model = OperarioProduccion
        fields = [
            "nombre",
            "documento",
            "especialidad",
        ]

        widgets = {
            "nombre": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nombre completo",
                }
            ),
            "documento": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Opcional",
                }
            ),
            "especialidad": forms.Select(
                attrs={"class": "form-select"}
            ),
        }


class OperarioProduccionView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    SucursalIsolationMixin,
    View,
):
    template_name = "inventory/operarios_produccion.html"

    def get_context_data(self, form=None):
        sucursal = self.get_sucursal()

        return {
            "form": form or OperarioProduccionForm(),
            "operarios": (
                OperarioProduccion.objects
                .filter(sucursal=sucursal)
                .order_by("activo", "nombre")
            ),
        }

    def get(self, request):
        return render(
            request,
            self.template_name,
            self.get_context_data(),
        )

    def post(self, request):
        form = OperarioProduccionForm(request.POST)

        if form.is_valid():
            operario = form.save(commit=False)
            operario.sucursal = self.get_sucursal()
            operario.save()

            messages.success(
                request,
                "Empleado de producción creado correctamente.",
            )

            return redirect("inventory:operarios_produccion")

        return render(
            request,
            self.template_name,
            self.get_context_data(form=form),
        )