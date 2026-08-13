# apps/sales/permissions.py
from django.core.exceptions import PermissionDenied


class RolePermissionMixin:
    allowed_roles = []

    def get_user_role(self):
        if not self.request.user.is_authenticated:
            return None

        profile = getattr(self.request.user, "profile", None)

        if not profile:
            return None

        return profile.role

    def dispatch(self, request, *args, **kwargs):
        role = self.get_user_role()

        if self.allowed_roles and role not in self.allowed_roles:
            raise PermissionDenied("No tienes permisos para esta acción.")

        return super().dispatch(request, *args, **kwargs)