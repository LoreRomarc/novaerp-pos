# apps/core/admin.py
from django.contrib import admin
from apps.core.models import Sucursal

@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ["nombre", "direccion", "activa"]
    search_fields = ["nombre", "direccion"]