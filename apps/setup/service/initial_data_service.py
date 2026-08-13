# apps/setup/service/initial_data_service.py
from django.db import transaction

from apps.customers.models import Cliente

from apps.inventory.models import (
    Color,
    TipoTela,
    Talla,
)

class InitialDataService:

    @staticmethod
    @transaction.atomic
    def crear_datos_base():

        # ==========================================
        # CLIENTE GENERICO
        # ==========================================
        Cliente.objects.get_or_create(

            nombre="CONSUMIDOR FINAL",

            defaults={

                "identificacion": "222222222222",

                "tipo_cliente": "DETAL",

                "activo": True,

            }

        )

        # ==========================================
        # COLORES BASE
        # ==========================================
        colores = [

            ("NEGRO", "#000000"),
            ("BLANCO", "#FFFFFF"),
            ("AZUL REY", "#0000FF"),
            ("ROJO", "#FF0000"),
            ("VERDE", "#008000"),
            ("GRIS", "#808080"),
        ]

        for nombre, codigo in colores:

            Color.objects.get_or_create(
                nombre=nombre,
                defaults={
                    "codigo_hex": codigo
                }
            )

        # ==========================================
        # TIPOS DE TELA
        # ==========================================

        telas = [
            "ALGODON",
            "BURDA",
            "LYCRA",
            "PERCHADO",
            "ALGODON PESADO",
        ]

        for tela in telas:

            TipoTela.objects.get_or_create(
                nombre=tela,

                defaults={
                    "activo": True
                }
            )

        # ==========================================
        # TALLAS
        # ==========================================

        tallas = [
            ("XS",1),
            ("S",2),
            ("M",3),
            ("L",4),
            ("XL",5),
            ("XXL",6),
        ]


        for nombre, orden in tallas:

            Talla.objects.get_or_create(

                nombre=nombre,

                defaults={

                    "orden": orden,

                    "activo": True

                }

            )

        return True
