# apps/sales/mixins.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.accounts.models import UserProfile


from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied

from apps.accounts.models import UserProfile
from apps.core.models import Sucursal


class SucursalIsolationMixin:
    """
    Determina la sucursal activa para el usuario.

    SUPER_ADMIN:
        Puede operar cualquier sucursal activa.
        La sucursal seleccionada se guarda en sesión.

    Usuarios normales:
        Deben tener una sucursal asignada en su perfil.
    """

    def get_sucursal(self):
        usuario = self.request.user

        if not usuario.is_authenticated:
            raise PermissionDenied(
                "Debe iniciar sesión para acceder al sistema."
            )

        try:
            perfil = (
                UserProfile.objects
                .select_related("sucursal")
                .get(user=usuario)
            )
        except UserProfile.DoesNotExist:
            raise PermissionDenied(
                "Su usuario no tiene un perfil configurado. "
                "Solicite al administrador que configure su usuario."
            )

        # ==================================================
        # SUPER ADMIN
        # ==================================================

        if perfil.role == UserProfile.Role.SUPER_ADMIN:

            sucursal_id = self.request.session.get(
                "sucursal_id"
            )

            if not sucursal_id:
                raise PermissionDenied(
                    "Debe seleccionar una sucursal para operar."
                )

            sucursal = (
                Sucursal.objects
                .filter(
                    pk=sucursal_id,
                    activa=True,
                )
                .first()
            )

            if not sucursal:
                self.request.session.pop(
                    "sucursal_id",
                    None,
                )
                self.request.session.modified = True

                raise PermissionDenied(
                    "La sucursal seleccionada no existe "
                    "o está inactiva."
                )

            return sucursal

        # ==================================================
        # USUARIOS NORMALES
        # ==================================================

        if not perfil.sucursal:
            raise PermissionDenied(
                "Su usuario no tiene una sucursal asignada."
            )

        if not perfil.sucursal.activa:
            raise PermissionDenied(
                "La sucursal asignada a su usuario está inactiva."
            )

        return perfil.sucursal


class CajaActivaRequiredMixin:
    """
    Obliga a tener un turno de caja abierto.

    IMPORTANTE:
    Este mixin NO debe utilizarse en POSView.

    POSView necesita permitir que un cajero sin turno
    sea enviado a la pantalla de apertura de caja.
    """

    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return super().dispatch(request, *args, **kwargs)

        from apps.accounts.models import UserProfile
        from django.shortcuts import redirect

        perfil = (
            UserProfile.objects
            .filter(user=request.user)
            .first()
        )

        if (
            perfil
            and perfil.role == UserProfile.Role.SUPER_ADMIN
            and not request.session.get("sucursal_id")
        ):
            return redirect(
                "sales:seleccionar_sucursal"
            )

        from apps.sales.services.caja_service import CajaService

        sucursal = self.get_sucursal()

        turno = CajaService.obtener_turno_activo_usuario(
            sucursal=sucursal,
            usuario=request.user,
        )

        if not turno:
            request.session.pop("turno_id", None)
            request.session.pop("caja_id", None)
            request.session.modified = True

            return redirect(
                "sales:abrir_caja"
            )

        request.session["turno_id"] = turno.id
        request.session["caja_id"] = turno.caja_id
        request.session.modified = True

        return super().dispatch(
            request,
            *args,
            **kwargs,
        )
