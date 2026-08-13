# apps/inventory/services/corte_numero_service.py
from django.utils import timezone
from django.db.models import Max

from apps.inventory.models_produccion import ProduccionLote


class NumeroCorteService:

    @staticmethod
    def siguiente_numero():

        anio = timezone.now().year

        ultimo = (
            ProduccionLote.objects
            .filter(
                anio_corte=anio
            )
            .aggregate(
                maximo=Max("numero_corte")
            )
            ["maximo"]
        )

        if ultimo:
            numero = ultimo + 1
        else:
            numero = 1

        return anio, numero