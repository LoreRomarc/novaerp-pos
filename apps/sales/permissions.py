# apps/sales/permissions.py
from django.core.exceptions import PermissionDenied


class RolePermissionMixin:

    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        role = getattr(request.user.profile, "role", None)
        if self.allowed_roles and role not in self.allowed_roles:
            raise PermissionDenied("No tienes permisos para esta acción.")
        return super().dispatch(request, *args, **kwargs)