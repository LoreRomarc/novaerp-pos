# apps/inventory/mixins.py
from django.core.exceptions import PermissionDenied

from apps.accounts.models import UserProfile
from apps.core.models import Sucursal


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
        """Obtiene la sucursal de trabajo sin permitir mezclar inventario."""
        perfil = getattr(self.request.user, "profile", None)

        if not perfil:
            raise PermissionDenied("El usuario no tiene un perfil configurado.")

        if perfil.role == UserProfile.Role.SUPER_ADMIN:
            sucursal = Sucursal.objects.filter(
                pk=self.request.session.get("sucursal_id"),
                activa=True,
            ).first()
            if not sucursal:
                raise PermissionDenied(
                    "Debe seleccionar una sucursal activa para operar."
                )
            return sucursal

        if not perfil.sucursal_id or not perfil.sucursal.activa:
            raise PermissionDenied(
                "Su usuario no tiene una sucursal activa asignada."
            )

        return perfil.sucursal

    def filter_by_sucursal(self, qs, field="sucursal"):
        sucursal = self.get_sucursal()

        if not sucursal:
            return qs.none()

        return qs.filter(**{field: sucursal})
