"""Garantiza los maestros base sin alterar datos comerciales existentes."""

from django.core.management.base import BaseCommand

from apps.setup.service.initial_data_service import InitialDataService


class Command(BaseCommand):
    help = (
        "Crea únicamente los colores, telas, tallas y cliente base faltantes; "
        "no carga productos ni modifica registros existentes."
    )

    def handle(self, *args, **options):
        InitialDataService.crear_datos_base(cargar_catalogo=False)
        self.stdout.write(
            self.style.SUCCESS("Datos maestros base verificados correctamente.")
        )
