# apps/sales/urls.py
from django.urls import path

from apps.sales.pos_views import POSNuevaVentaView
from apps.sales.report_views import (
    ReporteCajaView,
    ReporteVentasView,
    VentaDetalleView,
)
from apps.sales.views_devoluciones import (
    CambioDirectoProcesarView,
    CambioDirectoView,
    CambioProductoBusquedaView,
    DevolucionListView,
)
from apps.sales.views_caja import (
    AbrirCajaView,
    CajaAprobarArqueoView,
    CajaArqueoView,
    CajaAsignarCajeroView,
    CajaAsignarSupervisorView,
    CajaDashboardView,
    CajaDesasignarCajeroView,
    CajaEgresoView,
    CajaHistorialCierresView,
    CajaIngresoView,
    CajaRetiroView,
    CajaVerificarIntegridadView,
    CerrarCajaView,
    SeleccionarSucursalView,
)

from .views import (
    POSActualizarCantidadView,
    POSAgregarProductoView,
    POSAnularVentaView,
    POSCambiarTipoVentaView,
    POSCancelarVentaView,
    POSCargarVentaView,
    POSCerrarVentaView,
    POSEliminarItemView,
    POSGuardarEstadoView,
    POSView,
    ProductoAutocompleteView,
)

app_name = "sales"


urlpatterns = [
    path("pos/", POSView.as_view(), name="pos"),
    path("pos/agregar/", POSAgregarProductoView.as_view(), name="pos_agregar"),
    path("pos/actualizar/", POSActualizarCantidadView.as_view(), name="pos_actualizar"),
    path("pos/eliminar/", POSEliminarItemView.as_view(), name="pos_eliminar"),
    path("pos/cerrar/", POSCerrarVentaView.as_view(), name="pos_cerrar"),
    path("pos/cancelar/", POSCancelarVentaView.as_view(), name="pos_cancelar"),
    path("pos/anular-venta/",POSAnularVentaView.as_view(),name="pos_anular_venta",),
    path("pos/autocomplete/", ProductoAutocompleteView.as_view(), name="pos_autocomplete"),
    path("pos/cambiar-tipo/", POSCambiarTipoVentaView.as_view(), name="pos_cambiar_tipo"),
    path("pos/cargar/", POSCargarVentaView.as_view(), name="pos_cargar"),
    path("pos/nueva/", POSNuevaVentaView.as_view(), name="pos_nueva_venta"),
    path("pos/guardar/", POSGuardarEstadoView.as_view(), name="pos_guardar"),

    path("caja/", CajaDashboardView.as_view(), name="caja_dashboard"),
    path("caja/abrir/", AbrirCajaView.as_view(), name="abrir_caja"),
    path("caja/cerrar/", CerrarCajaView.as_view(), name="cerrar_caja"),
    path("caja/ingreso/", CajaIngresoView.as_view(), name="caja_ingreso"),
    path("caja/egreso/", CajaEgresoView.as_view(), name="caja_egreso"),
    path("caja/retiro/", CajaRetiroView.as_view(), name="caja_retiro"),
    path("caja/arqueo/", CajaArqueoView.as_view(), name="caja_arqueo"),
    path("caja/supervisor/", CajaAsignarSupervisorView.as_view(), name="caja_asignar_supervisor",),
    path("caja/cajeros/",CajaAsignarCajeroView.as_view(),name="caja_asignar_cajero",),
    path("caja/cajeros/<int:usuario_id>/desasignar/",CajaDesasignarCajeroView.as_view(),name="caja_desasignar_cajero",),
    path("caja/arqueos/<int:arqueo_id>/aprobar/", CajaAprobarArqueoView.as_view(), name="caja_aprobar_arqueo",),
    path("caja/turnos/<int:turno_id>/integridad/",CajaVerificarIntegridadView.as_view(),name="caja_verificar_integridad",),
    path("caja/resumen/",CajaDashboardView.as_view(),name="caja_resumen",),
    path("caja/reportes/", ReporteCajaView.as_view(), name="caja_reportes"),
    path("caja/cierres/",CajaHistorialCierresView.as_view(), name="caja_historial_cierres",),

    path( "sucursal/seleccionar/",SeleccionarSucursalView.as_view(), name="seleccionar_sucursal",),

    path("reportes/", ReporteVentasView.as_view(), name="reportes"),
    path("venta/<int:pk>/", VentaDetalleView.as_view(), name="venta_detalle"),

    # ======================================================
    # DEVOLUCIONES Y CAMBIOS
    # ======================================================
    path("devoluciones/",DevolucionListView.as_view(), name="devolucion_list",),
    path("devoluciones/nuevo/", CambioDirectoView.as_view(), name="devolucion_create",),
    path("devoluciones/procesar/", CambioDirectoProcesarView.as_view(), name="devolucion_procesar",),
    path("devoluciones/buscar-producto/",CambioProductoBusquedaView.as_view(), name="devolucion_buscar_producto",),
]