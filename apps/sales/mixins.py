# apps/sales/mixins.py
from django.core.exceptions import PermissionDenied


class SucursalIsolationMixin:

    def get_sucursal(self):
        profile = getattr(self.request.user, "profile", None)
        if not profile or not profile.sucursal:
            raise PermissionDenied("Usuario sin sucursal asignada.")
        return profile.sucursal
    
class CajaActivaRequiredMixin(SucursalIsolationMixin):

    def dispatch(self, request, *args, **kwargs):
        from .services.caja_service import CajaService
        sucursal = self.get_sucursal()
        if not CajaService.obtener_turno_abierto(sucursal):
            raise PermissionDenied("Debe tener una caja abierta para acceder a esta sección.")
        return super().dispatch(request, *args, **kwargs)