# apps/setup/service/setup_repair_service.py
from django.db import transaction
from django.contrib.auth.models import User

from apps.accounts.models import UserProfile

from apps.setup.service.initial_data_service import InitialDataService


class SetupRepairService:

    @staticmethod
    @transaction.atomic
    def reparar_sistema():

        # ==================================================
        # REPARAR PERFILES DE USUARIO
        # ==================================================

        for usuario in User.objects.all():

            UserProfile.objects.get_or_create(
                user=usuario,
                defaults={
                    "role": (
                        "SUPER_ADMIN"
                        if usuario.is_superuser
                        else "CAJERO"
                    )
                }
            )

        # ==================================================
        # REPARAR DATOS MAESTROS
        # ==================================================

        InitialDataService.crear_datos_base()

        return True