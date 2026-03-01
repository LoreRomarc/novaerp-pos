# apps/reports/urls.py
from django.urls import path
from .views import reporte_ventas

urlpatterns = [
    path('ventas/', reporte_ventas, name='reporte_ventas'),
]
