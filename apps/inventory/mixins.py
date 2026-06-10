# apps/inventory/mixins.py
from django.core.exceptions import PermissionDenied


class InventoryAccessMixin:

    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "INVENTARIO"]

    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            raise PermissionDenied("No autenticado")

        profile = getattr(request.user, "profile", None)

        if not profile:
            raise PermissionDenied("Sin perfil")

        if profile.role not in self.allowed_roles:
            raise PermissionDenied("Sin permisos de inventario")

        return super().dispatch(request, *args, **kwargs)


class SucursalScopedMixin:

    def get_sucursal(self):
        return getattr(self.request.user.profile, "sucursal", None)

    def filter_by_sucursal(self, qs, field="sucursal"):
        sucursal = self.get_sucursal()

        if not sucursal:
            return qs.none()

        return qs.filter(**{field: sucursal})