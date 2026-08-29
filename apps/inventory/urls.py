# apps/inventory/urls.py
from django.urls import path

from apps.inventory.api.search_views import VarianteSearchAPI

from apps.inventory.views_dashboard import InventoryDashboardView
from apps.inventory.views_kardex import KardexDetalleView, KardexListView
from apps.inventory.views_produccion import CorteProduccionView
from apps.inventory.views_rollos import (
    RolloCreateView,
    RolloListView
)

from apps.inventory.views_confeccion import (
    ConfeccionLotesView,
    ConfeccionRegistroView,
)
from apps.inventory.views_operaciones_produccion import (
    OperacionProduccionListView,
)
from apps.inventory.views_operarios_produccion import (
    OperarioProduccionView,
)
from apps.inventory.views_productos import (
    ProductoListView,
    ProductoCreateView,
    ProductoUpdateView,
    ProductoDetailView,
)

from .views import (
    AjusteStockCreateView,
    AjusteStockView,
    StockListView,
    TrasladoCreateView,
    TrasladoListView,
    ProduccionListView,
)

from apps.inventory.views_variantes import (
    VarianteListView,
    VarianteCreateView,
    VarianteUpdateView,
)

app_name = "inventory"

urlpatterns = [

    # ======================================================
    # DASHBOARD
    # ======================================================
    path("",InventoryDashboardView.as_view(),name="dashboard"),

    # ======================================================
    # PRODUCCION
    # ======================================================
    path( "produccion/",ProduccionListView.as_view(),name="produccion_list"),
    path("produccion/corte/",CorteProduccionView.as_view(), name="corte_produccion"),
    path("produccion/operarios/",OperarioProduccionView.as_view(), name="operarios_produccion",),
    path("produccion/confeccion/",  ConfeccionLotesView.as_view(), name="confeccion_lotes", ),
    path( "produccion/confeccion/<int:lote_id>/", ConfeccionRegistroView.as_view(), name="confeccion_registrar",),
    path( "produccion/historial-operaciones/", OperacionProduccionListView.as_view(), name="operaciones_produccion",),

    # ======================================================
    # ROLLOS
    # ======================================================
    path( "rollos/",RolloListView.as_view(), name="rollo_list"),
    path("rollos/nuevo/",RolloCreateView.as_view(),name="rollo_create"),

    # ======================================================
    # PRODUCTOS
    # ======================================================
    path( "productos/",ProductoListView.as_view(),name="producto_list"),
    path("productos/nuevo/", ProductoCreateView.as_view(), name="producto_create"),
    path( "productos/<int:pk>/", ProductoDetailView.as_view(), name="producto_detail"),
    path( "productos/<int:pk>/editar/", ProductoUpdateView.as_view(), name="producto_update"),

    # ======================================================
    # STOCK
    # ======================================================
    path("api/variantes/search/", VarianteSearchAPI.as_view(), name="variant_search_api" ),
    path("ajuste-stock/", AjusteStockView.as_view(), name="ajuste_stock" ),
    path( "stock/", StockListView.as_view(),  name="stock_list" ),
    path("stock/ajuste/",AjusteStockCreateView.as_view(), name="ajuste_stock_form"),

    # ======================================================
    # TRASLADOS
    # ======================================================
    path( "traslados/", TrasladoListView.as_view(),  name="traslado_list" ),
    path( "traslados/nuevo/", TrasladoCreateView.as_view(), name="traslado_create"),

    # ======================================================
    # MOVIMIENTOS
    # ======================================================
    path( "movimientos/kardex/", KardexListView.as_view(), name="kardex" ),
    path("movimientos/kardex/<int:pk>/detalle/", KardexDetalleView.as_view(), name="kardex_detalle"),

    # ======================================================
    # VARIANTES
    # ======================================================
    path( "variantes/", VarianteListView.as_view(),  name="variante_list"),
    path( "variantes/nuevo/", VarianteCreateView.as_view(), name="variante_create"),
    path( "variantes/<int:pk>/editar/", VarianteUpdateView.as_view(),  name="variante_update"),

]
