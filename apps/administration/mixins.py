from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.accounts.models import UserProfile


class SuperAdminRequiredMixin(LoginRequiredMixin):
    """Protege la configuración estructural del ERP."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        perfil = UserProfile.objects.filter(user=request.user).first()

        if not perfil or perfil.role != UserProfile.Role.SUPER_ADMIN:
            raise PermissionDenied(
                "Solo el Super Administrador puede acceder a Administración."
            )

        return super().dispatch(request, *args, **kwargs)
