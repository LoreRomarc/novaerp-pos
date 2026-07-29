# apps/core/admin.py
from django.contrib import admin

from apps.core.models import (
    Empresa,
    Sucursal,
)


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):

    list_display = (
        "nombre",
        "nit",
        "telefono",
        "activa",
    )

    search_fields = (
        "nombre",
        "nit",
    )


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):

    list_display = (
        "nombre",
        "empresa",
        "direccion",
        "activa",
    )

    search_fields = (
        "nombre",
        "direccion",
    )

    list_filter = (
        "empresa",
        "activa",
    )
