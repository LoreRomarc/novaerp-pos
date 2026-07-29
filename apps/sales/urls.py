# apps/sales/urls.py
from django.urls import path

from apps.sales.pos_views import POSNuevaVentaView
from .views import (
    POSCargarVentaView,
    POSGuardarEstadoView,
    POSView,
    POSAgregarProductoView,
    POSActualizarCantidadView,
    POSEliminarItemView,
    POSCerrarVentaView,
    POSCancelarVentaView,
    ProductoAutocompleteView,
    POSCambiarTipoVentaView,
    AbrirCajaView,
    CerrarCajaView,
)
from .report_views import ReporteVentasView, VentaDetalleView


app_name = "sales"

urlpatterns = [
    # ==========================
    # POS
    # ==========================
    path("pos/", POSView.as_view(), name="pos"),
    path("pos/agregar/", POSAgregarProductoView.as_view(), name="pos_agregar"),
    path("pos/actualizar/", POSActualizarCantidadView.as_view(), name="pos_actualizar"),
    path("pos/eliminar/", POSEliminarItemView.as_view(), name="pos_eliminar"),
    path("pos/cerrar/", POSCerrarVentaView.as_view(), name="pos_cerrar"),
    path("pos/cancelar/", POSCancelarVentaView.as_view(), name="pos_cancelar"),
    path("pos/autocomplete/", ProductoAutocompleteView.as_view(), name="pos_autocomplete"),
    path("pos/cambiar-tipo/", POSCambiarTipoVentaView.as_view(), name="pos_cambiar_tipo"),

    # ==========================
    # CAJA
    # ==========================
    path("caja/abrir/", AbrirCajaView.as_view(), name="abrir_caja"),
    path("caja/cerrar/", CerrarCajaView.as_view(), name="cerrar_caja"),

    # ==========================
    # REPORTES
    # ==========================
    path("reportes/", ReporteVentasView.as_view(),name="reportes"),
    path("venta/<int:pk>/", VentaDetalleView.as_view(),name="venta_detalle"),

    path("pos/nueva/",POSNuevaVentaView.as_view(),name="pos_nueva"),

    path("pos/cargar/",POSCargarVentaView.as_view(), name="pos_cargar"),

    path(
    "pos/nueva/",
    POSNuevaVentaView.as_view(),
    name="pos_nueva_venta",
),

path(
    "pos/guardar/",
    POSGuardarEstadoView.as_view(),
    name="pos_guardar",
),

]