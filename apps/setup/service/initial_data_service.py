# apps/setup/service/initial_data_service.py
from django.db import transaction
from django.core.management import call_command

from apps.customers.models import Cliente

from apps.inventory.models import (
    Color,
    TipoTela,
    Talla,
)

class InitialDataService:

    @staticmethod
    def _obtener_o_crear_por_nombre(modelo, nombre, defaults):
        """Evita duplicados que solo difieren por mayúsculas/minúsculas."""
        objeto = modelo.objects.filter(nombre__iexact=nombre).first()
        if objeto:
            return objeto, False
        return modelo.objects.get_or_create(nombre=nombre, defaults=defaults)

    @staticmethod
    @transaction.atomic
    def crear_datos_base():

        # ==========================================
        # CLIENTE GENERICO
        # ==========================================
        cliente = Cliente.objects.filter(nombre__iexact="Consumidor final").first()
        if not cliente:
            Cliente.objects.create(
                nombre="Consumidor final",
                identificacion="222222222222",
                tipo_cliente="DETAL",
                activo=True,
            )

        # ==========================================
        # COLORES BASE
        # ==========================================
        colores = [
            ("Sin Definir", "#6B7280"),
            ("Negro", "#000000"),
            ("Blanco", "#FFFFFF"),
            ("Azul Rey", "#0000FF"),
            ("Rojo", "#FF0000"),
            ("Verde", "#008000"),
            ("Gris", "#808080"),
        ]

        for nombre, codigo in colores:

            InitialDataService._obtener_o_crear_por_nombre(
                Color, nombre, {"codigo_hex": codigo, "activo": True}
            )

        # ==========================================
        # TIPOS DE TELA
        # ==========================================

        telas = [
            ("Lycra Algodón", "Tejido elástico de punto."),
            ("Algodón Puro", "Fibra natural rígida o jersey estándar."),
            ("Tela Fría", "Tejido sintético fluido y fresco."),
            ("Algodón Pesado 250gr", "Tela gruesa para prendas premium."),
            ("Algodón Perchado", "Tela con reverso abrigado."),
            ("Tela Burda", "Tejido de punto con rulos internos."),
            ("Suplex Poliamida", "Tela deportiva de alta compresión."),
            ("Tela Piqué", "Tejido texturizado para camisetas polo."),
        ]

        for tela, descripcion in telas:
            InitialDataService._obtener_o_crear_por_nombre(
                TipoTela,
                tela,
                {"descripcion": descripcion, "activo": True},
            )

        # ==========================================
        # TALLAS
        # ==========================================

        # Catálogo inicial flexible para la operación actual. Las tallas
        # existentes nunca se eliminan ni se renombran: cada variante conserva
        # su relación y se puede migrar el catálogo gradualmente.
        tallas = [
            ("Adulto", 1),
            ("Niño", 2),
            ("16", 3),
            ("S", 4),
            ("M", 5),
            ("L", 6),
            ("XL", 7),
            ("2XL", 8),
            ("3XL", 9),
            ("4XL", 10),
            ("Única", 11),
            ("Plus", 12),
        ]


        for nombre, orden in tallas:

            InitialDataService._obtener_o_crear_por_nombre(
                Talla,
                nombre,
                {"orden": orden, "activo": True},
            )

        # Si el archivo editable de catálogo ya contiene productos, la primera
        # instalación los crea aquí. El comando es idempotente: en instalaciones
        # existentes sólo agrega lo que falte y nunca reescribe el historial.
        # Así la misma fuente sirve tanto para iniciar desde cero como para
        # ampliar el catálogo más adelante de forma manual.
        call_command("cargar_catalogo_productos", verbosity=0)

        return True
