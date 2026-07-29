# apps/sales/pos_views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.views import View

from apps.sales.mixins import SucursalIsolationMixin
from apps.sales.permissions import RolePermissionMixin
from apps.sales.services.pos_service import POSService

class POSNuevaVentaView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View
):

    allowed_roles=[
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO"
    ]


    def post(self,request):

        venta = POSService.crear_nueva_venta(
            usuario=request.user,
            sucursal=self.get_sucursal()
        )

        return JsonResponse({
            "success": True,
            "venta": {
                "uuid": str(venta.uuid),
                "id": venta.id,
                "tipo_venta": venta.tipo_venta,
                "cliente": venta.cliente or "",
                "total": 0
            }
        })

