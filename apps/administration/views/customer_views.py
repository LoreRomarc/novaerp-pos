# apps/administration/views/customer_views.py
from django.db.models import Q
from django.views.generic import ListView, CreateView, UpdateView
from django.urls import reverse_lazy

from apps.customers.models import Cliente
from apps.administration.forms import ClienteForm
from apps.administration.mixins import SuperAdminRequiredMixin


class ClienteListView(SuperAdminRequiredMixin, ListView):
    model = Cliente
    template_name = "administration/customers/list.html"
    context_object_name = "clientes"
    paginate_by = 30

    def get_queryset(self):
        queryset = Cliente.objects.all().order_by("nombre", "id")
        query = self.request.GET.get("q", "").strip()
        tipo = self.request.GET.get("tipo", "")
        estado = self.request.GET.get("estado", "")
        if query:
            queryset = queryset.filter(
                Q(nombre__icontains=query)
                | Q(identificacion__icontains=query)
            )
        if tipo in {"DETAL", "MAYORISTA"}:
            queryset = queryset.filter(tipo_cliente=tipo)
        if estado in {"activo", "inactivo"}:
            queryset = queryset.filter(activo=estado == "activo")
        return queryset


class ClienteCreateView(SuperAdminRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "administration/customers/form.html"
    success_url = reverse_lazy("administration:cliente_list")


class ClienteUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "administration/customers/form.html"
    success_url = reverse_lazy("administration:cliente_list")
