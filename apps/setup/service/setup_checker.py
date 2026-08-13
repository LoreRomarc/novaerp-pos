# apps/setup/service/setup_checker.py
from django.contrib.auth.models import User

from apps.core.models import Sucursal
from apps.sales.models import Caja
from apps.sales.models_caja_enterprise import TurnoCaja
from apps.core.models_config import SistemaConfiguracion


class SetupChecker:

    @staticmethod
    def sistema_configurado():

        configuracion = (
            SistemaConfiguracion.objects
            .filter(
                instalado=True
            )
            .exists()
        )


        return configuracion
