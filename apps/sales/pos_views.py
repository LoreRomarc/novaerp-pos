# apps/sales/pos_views.py
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import JsonResponse
from django.views import View

from apps.sales.mixins import SucursalIsolationMixin
from apps.sales.permissions import RolePermissionMixin
from apps.sales.services.pos_service import POSService
from apps.sales.services.serializers import serializar_carrito


logger = logging.getLogger(__name__)


class POSNuevaVentaView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO",
    ]

    def post(self, request):
        try:
            carrito = POSService.crear_carrito(
                usuario=request.user,
                sucursal=self.get_sucursal(),
            )

            return JsonResponse(
                {
                    "success": True,
                    "data": serializar_carrito(carrito),
                },
                status=201,
            )

        except ValidationError as error:
            return JsonResponse(
                {
                    "success": False,
                    "error": error.messages[0],
                },
                status=400,
            )

        except Exception:
            logger.exception("Error al crear un nuevo carrito POS.")

            return JsonResponse(
                {
                    "success": False,
                    "error": (
                        "No fue posible crear la nueva venta. "
                        "Intente nuevamente."
                    ),
                },
                status=500,
            )