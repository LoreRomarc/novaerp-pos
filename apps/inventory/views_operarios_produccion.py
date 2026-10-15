# apps/inventory/views_operarios_produccion.py
from django import forms
from django.db import models
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from apps.inventory.mixins import InventoryAccessMixin
from apps.inventory.models_produccion import (
    OperarioProduccion,
)
from apps.sales.mixins import SucursalIsolationMixin
from apps.accounts.models import UserProfile
from apps.core.models import Sucursal


class OperarioProduccionForm(forms.ModelForm):
    class Meta:
        model = OperarioProduccion
        fields = [
            "nombre",
            "documento",
            "especialidad",
            "activo",
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
            "activo": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class OperarioProduccionView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    SucursalIsolationMixin,
    View,
):
    template_name = "inventory/operarios_produccion.html"

    def es_superadmin(self):
        return self.request.user.profile.role == UserProfile.Role.SUPER_ADMIN

    def get_context_data(self, form=None, operario_edicion=None):
        sucursal_activa = self.get_sucursal()
        sucursal_id = self.request.GET.get("sucursal") if self.es_superadmin() else sucursal_activa.id
        sucursal = Sucursal.objects.filter(pk=sucursal_id, activa=True).first() or sucursal_activa
        if operario_edicion and self.es_superadmin():
            sucursal = operario_edicion.sucursal
        queryset = OperarioProduccion.objects.filter(sucursal=sucursal)
        query = self.request.GET.get("q", "").strip()
        especialidad = self.request.GET.get("especialidad", "")
        estado = self.request.GET.get("estado", "")
        if query:
            queryset = queryset.filter(
                models.Q(nombre__icontains=query) | models.Q(documento__icontains=query)
            )
        if especialidad in dict(OperarioProduccion.Especialidad.choices):
            queryset = queryset.filter(especialidad=especialidad)
        if estado in {"activo", "inactivo"}:
            queryset = queryset.filter(activo=estado == "activo")

        return {
            "form": form or OperarioProduccionForm(instance=operario_edicion),
            "operarios": queryset.order_by("-activo", "nombre", "id"),
            "operario_edicion": operario_edicion,
            "sucursal_formulario": sucursal,
            "puede_ver_sucursales": self.es_superadmin(),
            "sucursales": Sucursal.objects.filter(activa=True).order_by("nombre"),
        }

    def get(self, request):
        operario_edicion = None
        if request.GET.get("editar"):
            operario_edicion = get_object_or_404(
                OperarioProduccion,
                pk=request.GET["editar"],
            )
            if not self.es_superadmin() and operario_edicion.sucursal_id != self.get_sucursal().id:
                return redirect("inventory:operarios_produccion")
        return render(
            request,
            self.template_name,
            self.get_context_data(operario_edicion=operario_edicion),
        )

    def post(self, request):
        operario_id = request.POST.get("operario_id")
        operario = None
        if operario_id:
            operario = get_object_or_404(OperarioProduccion, pk=operario_id)
            if not self.es_superadmin() and operario.sucursal_id != self.get_sucursal().id:
                return redirect("inventory:operarios_produccion")
        form = OperarioProduccionForm(request.POST, instance=operario)

        if form.is_valid():
            operario = form.save(commit=False)
            if self.es_superadmin() and request.POST.get("sucursal_id"):
                operario.sucursal = get_object_or_404(
                    Sucursal, pk=request.POST["sucursal_id"], activa=True
                )
            elif not operario.pk:
                operario.sucursal = self.get_sucursal()
            operario.save()

            messages.success(
                request,
                "Operario actualizado correctamente." if operario_id else "Operario de producción creado correctamente.",
            )

            return redirect("inventory:operarios_produccion")

        return render(
            request,
            self.template_name,
            self.get_context_data(form=form, operario_edicion=operario),
        )
