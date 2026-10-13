# apps/core/context_processors.py
from apps.accounts.models import UserProfile
from apps.core.models import Sucursal
from django.contrib.messages import get_messages


def sucursal_activa(request):
    # Las notificaciones de éxito genéricas no forman parte de la interfaz del
    # ERP. Consumirlas aquí evita que una operación anterior aparezca días
    # después al abrir una pantalla no relacionada. Los errores de formularios
    # se muestran en la misma respuesta y no usan este mecanismo.
    list(get_messages(request))
    usuario = getattr(request, "user", None)

    contexto_vacio = {
        "sucursal_activa": None,
        "puede_cambiar_sucursal": False,
        "puede_gestionar_cajas": False,
        "traslados_pendientes_recepcion": 0,
        "confecciones_pendientes": 0,
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

        pendientes = 0
        confecciones = 0
        if sucursal:
            from apps.inventory.models import Traslado
            from apps.inventory.models_produccion import ProduccionLote
            pendientes = Traslado.objects.filter(
                destino=sucursal, estado="ENVIADO",
                tipo__in=["COMPLETO", "SALIDA", "ENTRADA"],
            ).exclude(enviado_por=usuario).count()
            confecciones = ProduccionLote.objects.filter(
                sucursal=sucursal,
                estado__in=[
                    ProduccionLote.Estado.PENDIENTE_CONFECCION,
                    ProduccionLote.Estado.EN_CONFECCION,
                ],
            ).count()
        return {
            "sucursal_activa": sucursal,
            "puede_cambiar_sucursal": True,
            "puede_gestionar_cajas": True,
            "traslados_pendientes_recepcion": pendientes,
            "confecciones_pendientes": confecciones,
        }

    pendientes = 0
    confecciones = 0
    if perfil.sucursal:
        from apps.inventory.models import Traslado
        from apps.inventory.models_produccion import ProduccionLote
        pendientes = Traslado.objects.filter(
            destino=perfil.sucursal, estado="ENVIADO",
            tipo__in=["COMPLETO", "SALIDA", "ENTRADA"],
        ).exclude(enviado_por=usuario).count()
        confecciones = ProduccionLote.objects.filter(
            sucursal=perfil.sucursal,
            estado__in=[
                ProduccionLote.Estado.PENDIENTE_CONFECCION,
                ProduccionLote.Estado.EN_CONFECCION,
            ],
        ).count()
    return {
        "sucursal_activa": perfil.sucursal,
        "puede_cambiar_sucursal": False,
        "puede_gestionar_cajas": (
            perfil.role == UserProfile.Role.SUPER_ADMIN
        ),
        "traslados_pendientes_recepcion": pendientes,
        "confecciones_pendientes": confecciones,
    }
