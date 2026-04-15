# apps/sales/mixins.py
from django.core.exceptions import PermissionDenied


class SucursalIsolationMixin:

    def get_sucursal(self):
        user = self.request.user

        if not user.is_authenticated:
            raise PermissionDenied("Usuario no autenticado.")

        profile = getattr(user, "profile", None)

        if not profile:
            raise PermissionDenied("Usuario sin perfil.")

        if not profile.sucursal:
            raise PermissionDenied("Usuario sin sucursal asignada.")

        return profile.sucursal


class CajaActivaRequiredMixin(SucursalIsolationMixin):

    def dispatch(self, request, *args, **kwargs):
        from apps.sales.services.caja_service import CajaService

        sucursal = self.get_sucursal()

        if not CajaService.obtener_turno_abierto(sucursal):
            raise PermissionDenied("Debe tener una caja abierta para acceder a esta sección.")

        return super().dispatch(request, *args, **kwargs)