# apps/administration/views/empresas_views.py
from django.views import View
from django.shortcuts import render

from apps.core.models import Empresa


class EmpresaListView(View):

    template_name = "administration/empresa/empresa_list.html"


    def get(self, request):

        empresas = Empresa.objects.all()

        return render(
            request,
            self.template_name,
            {
                "empresas": empresas
            }
        )
