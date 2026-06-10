# apps/administration/views/dashboard.py
from django.views.generic import TemplateView


class AdminDashboardView(TemplateView):
    template_name = "administration/dashboard.html"