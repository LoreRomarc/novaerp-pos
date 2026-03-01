# apps/sales/admin.py
from django.contrib import admin

from apps.sales.models_caja_enterprise import ArqueoDenominacion, ArqueoTurno, Boveda, CajaMovimiento, TurnoCaja
from .models import Caja, ListaPrecio, PrecioProducto, Venta, VentaItem

admin.site.register(Caja)
admin.site.register(Venta)
admin.site.register(VentaItem)
admin.site.register(ListaPrecio)
admin.site.register(PrecioProducto)
admin.site.register(Boveda)
admin.site.register(TurnoCaja)
admin.site.register(CajaMovimiento)
admin.site.register(ArqueoTurno)
admin.site.register(ArqueoDenominacion)
