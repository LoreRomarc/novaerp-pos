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
            ("SIN DEFINIR", "#6B7280"),
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

        # Catálogo inicial flexible para la operación actual. Las tallas
        # existentes nunca se eliminan ni se renombran: cada variante conserva
        # su relación y se puede migrar el catálogo gradualmente.
        tallas = [
            ("ADULTO", 1),
            ("NIÑO", 2),
            ("16", 3),
            ("S", 4),
            ("M", 5),
            ("L", 6),
            ("XL", 7),
            ("2XL", 8),
            ("3XL", 9),
            ("4XL", 10),
            ("UNICA", 11),
            ("PLUS", 12),
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
