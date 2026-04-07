# apps/inventory/services/produccion_validations.py
from django.core.exceptions import ValidationError


class ProduccionValidator:

    @staticmethod
    def validar_items(items):
        if not items:
            raise ValidationError("Debe ingresar al menos un item.")

        for item in items:
            if item["cantidad"] <= 0:
                raise ValidationError("Cantidad inválida en items.")

            if not item["talla"]:
                raise ValidationError("Talla requerida.")