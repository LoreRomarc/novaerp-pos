# apps/setup/service/setup_repair_service.py
from django.db import transaction

from django.contrib.auth.models import User

from apps.accounts.models import UserProfile

from apps.sales.models import Caja

from apps.sales.models_caja_enterprise import TurnoCaja



class SetupRepairService:

    @staticmethod
    @transaction.atomic
    def reparar_cajas():


        usuario = (
            User.objects
            .filter(
                is_superuser=True
            )
            .first()
        )


        if not usuario:

            return False



        cajas = Caja.objects.all()



        for caja in cajas:


            existe_turno = TurnoCaja.objects.filter(

                caja=caja,

                estado="ABIERTO"

            ).exists()



            if not existe_turno:


                TurnoCaja.objects.create(

                    caja=caja,

                    usuario_apertura=usuario,

                    sucursal=caja.sucursal,

                    monto_inicial=0,

                    estado="ABIERTO"

                )


        # ======================================
        # REPARAR PERFILES DE USUARIO
        # ======================================

        for usuario in User.objects.all():

            UserProfile.objects.get_or_create(

                user=usuario,

                defaults={

                    "role": "SUPER_ADMIN"
                    if usuario.is_superuser
                    else "CAJERO"

                }

            )


        return True
