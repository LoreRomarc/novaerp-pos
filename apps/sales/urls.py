# apps/sales/urls.py
from django.urls import path
from .views import *

app_name = "sales"

urlpatterns = [
    path("pos/", POSView.as_view(), name="pos"),
    path("pos/agregar/", POSAgregarProductoView.as_view(), name="pos_agregar"),
    path("pos/actualizar/", POSActualizarCantidadView.as_view(), name="pos_actualizar"),
    path("pos/eliminar/", POSEliminarItemView.as_view(), name="pos_eliminar"),
    path("pos/cerrar/", POSCerrarVentaView.as_view(), name="pos_cerrar"),
    path("pos/cancelar/", POSCancelarVentaView.as_view(), name="pos_cancelar"),
    path("pos/autocomplete/", ProductoAutocompleteView.as_view(), name="pos_autocomplete"),
    path("pos/cambiar-tipo/", POSCambiarTipoVentaView.as_view(), name="pos_cambiar_tipo"),

    path("caja/abrir/", AbrirCajaView.as_view(), name="abrir_caja"),
    path("caja/cerrar/", CerrarCajaView.as_view(), name="cerrar_caja"),
]