# apps/core/context_processors.py
from apps.accounts.models import UserProfile
from apps.core.models import Sucursal


def sucursal_activa(request):
    usuario = getattr(request, "user", None)

    contexto_vacio = {
        "sucursal_activa": None,
        "puede_cambiar_sucursal": False,
        "puede_gestionar_cajas": False,
    }

    if not usuario or not usuario.is_authenticated:
        return contexto_vacio

    perfil = getattr(usuario, "profile", None)

    if not perfil:
        return contexto_vacio

    if perfil.role == UserProfile.Role.SUPER_ADMIN:
        sucursal = (
            Sucursal.objects
            .filter(
                pk=request.session.get("sucursal_id"),
                activa=True,
            )
            .first()
        )

        return {
            "sucursal_activa": sucursal,
            "puede_cambiar_sucursal": True,
            "puede_gestionar_cajas": True,
        }

    return {
        "sucursal_activa": perfil.sucursal,
        "puede_cambiar_sucursal": False,
        "puede_gestionar_cajas": (
            perfil.role == UserProfile.Role.SUPER_ADMIN
        ),
    }