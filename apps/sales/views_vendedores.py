from django import forms
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import FormView, ListView

from apps.sales.mixins import SucursalIsolationMixin
from apps.sales.models import Vendedor
from apps.sales.permissions import RolePermissionMixin


class VendedorForm(forms.ModelForm):
    class Meta:
        model = Vendedor
        fields = ("nombre", "documento", "telefono", "activo")
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nombre completo"}),
            "documento": forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional"}),
            "telefono": forms.TextInput(attrs={"class": "form-control", "placeholder": "Opcional"}),
            "activo": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


class VendedorListView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, ListView):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL"]
    model = Vendedor
    template_name = "sales/vendedores.html"
    context_object_name = "vendedores"
    paginate_by = 30

    def get_queryset(self):
        queryset = Vendedor.objects.filter(sucursal=self.get_sucursal())
        q = self.request.GET.get("q", "").strip()
        if q:
            queryset = queryset.filter(
                models.Q(nombre__icontains=q)
                | models.Q(documento__icontains=q)
                | models.Q(telefono__icontains=q)
            )
        return queryset.order_by("nombre", "id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        vendedor_id = self.request.GET.get("editar")
        vendedor = None
        if vendedor_id:
            vendedor = Vendedor.objects.filter(
                pk=vendedor_id, sucursal=self.get_sucursal()
            ).first()
        context["vendedor_edicion"] = vendedor
        context["form"] = VendedorForm(instance=vendedor)
        return context

    def post(self, request, *args, **kwargs):
        vendedor_id = request.POST.get("vendedor_id")
        vendedor = None
        if vendedor_id:
            vendedor = get_object_or_404(
                Vendedor, pk=vendedor_id, sucursal=self.get_sucursal()
            )
        form = VendedorForm(request.POST, instance=vendedor)
        if form.is_valid():
            vendedor = form.save(commit=False)
            vendedor.sucursal = self.get_sucursal()
            vendedor.save()
            messages.success(
                request,
                "Vendedor actualizado." if vendedor_id else "Vendedor registrado.",
            )
            return redirect("sales:vendedor_list")
        else:
            context = self.get_context_data()
            context["form"] = form
            context["vendedor_edicion"] = vendedor
            return render(request, self.template_name, context, status=400)
