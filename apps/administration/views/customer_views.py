# apps/administration/views/customer_views.py
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy

from apps.customers.models import Cliente
from apps.administration.forms import ClienteForm
from apps.administration.mixins import SuperAdminRequiredMixin


class ClienteListView(SuperAdminRequiredMixin, ListView):
    model = Cliente
    template_name = "administration/customers/list.html"
    context_object_name = "clientes"


class ClienteCreateView(SuperAdminRequiredMixin, CreateView):
    model = Cliente
    form_class = ClienteForm
    template_name = "administration/customers/form.html"
    success_url = reverse_lazy("administration:cliente_list")
