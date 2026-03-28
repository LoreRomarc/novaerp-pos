# apps/inventory/urls.py
from django.urls import path

from apps.inventory.views_corte import crear_corte
from .views import (
    ProduccionView,
    ProduccionListView,
    StockListView,
    TrasladoCreateView,
    TrasladoListView,
    MovimientoListView,
)

app_name = "inventory"

urlpatterns = [
    path("produccion/", ProduccionView.as_view(), name="produccion"),
    path("produccion/list/", ProduccionListView.as_view(), name="produccion_list"),

    path("stock/", StockListView.as_view(), name="stock_list"),

    path("traslados/", TrasladoListView.as_view(), name="traslado_list"),
    path("traslados/nuevo/", TrasladoCreateView.as_view(), name="traslado_create"),

    path("movimientos/", MovimientoListView.as_view(), name="movimientos"),

    path("corte/", crear_corte, name="crear_corte"),
]
