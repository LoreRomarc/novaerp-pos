# apps/administration/views/dashboard.py
from django.views.generic import TemplateView

from apps.administration.mixins import SuperAdminRequiredMixin


class AdminDashboardView(SuperAdminRequiredMixin, TemplateView):
    template_name = "administration/dashboard.html"
