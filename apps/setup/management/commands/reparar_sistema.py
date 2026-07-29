# apps/setup/management/commands/reparar_sistema.py
from django.core.management.base import BaseCommand

from apps.setup.service.setup_repair_service import (
    SetupRepairService
)

from apps.setup.service.setup_checker import (
    SetupChecker
)



class Command(BaseCommand):

    help = "Repara componentes faltantes de la configuración inicial."



    def handle(self, *args, **options):


        self.stdout.write(
            "Revisando configuración del sistema..."
        )


        reparado = SetupRepairService.reparar_cajas()



        if reparado:

            self.stdout.write(

                self.style.SUCCESS(
                    "Revisión de cajas completada."
                )

            )

        else:

            self.stdout.write(

                self.style.ERROR(
                    "No fue posible reparar cajas."
                )

            )



        estado = SetupChecker.sistema_configurado()



        if estado:

            self.stdout.write(

                self.style.SUCCESS(
                    "Sistema operativo correctamente."
                )

            )

        else:

            self.stdout.write(

                self.style.WARNING(
                    "El sistema aún requiere configuración."
                )

            )
