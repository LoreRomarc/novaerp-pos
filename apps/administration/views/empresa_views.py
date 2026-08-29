# apps/administration/views/empresas_views.py
from django.shortcuts import render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import UpdateView

from apps.administration.forms import EmpresaForm
from apps.administration.mixins import SuperAdminRequiredMixin
from apps.core.models import Empresa


class EmpresaListView(SuperAdminRequiredMixin, View):
    template_name = "administration/empresa/empresa_list.html"

    def get(self, request):
        empresas = Empresa.objects.all().order_by("nombre")

        return render(
            request,
            self.template_name,
            {
                "empresas": empresas,
            },
        )


class EmpresaUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = Empresa
    form_class = EmpresaForm
    template_name = "administration/empresa/empresa_form.html"
    success_url = reverse_lazy("administration:empresa_list")
