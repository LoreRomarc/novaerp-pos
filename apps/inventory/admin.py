# apps/inventory/admin.py
from django.contrib import admin
from .models import MovimientoStock, Producto, Stock

admin.site.register(Producto)
admin.site.register(MovimientoStock)
admin.site.register(Stock)
