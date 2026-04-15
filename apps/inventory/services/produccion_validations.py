# apps/inventory/services/produccion_validations.py

from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError

from apps.inventory.services.base_validators import BaseInventoryValidator


class ProduccionValidator(BaseInventoryValidator):

    @staticmethod
    def validar_items(items):

        if not items:
            raise ValidationError("Debe ingresar al menos un item.")

        for i, item in enumerate(items, start=1):

            # ==========================
            # CANTIDAD
            # ==========================
            cantidad = item.get("cantidad")

            if cantidad is None:
                raise ValidationError(f"Item {i}: cantidad obligatoria.")

            try:
                cantidad = Decimal(cantidad)
            except (InvalidOperation, TypeError):
                raise ValidationError(f"Item {i}: cantidad inválida.")

            if cantidad <= 0:
                raise ValidationError(f"Item {i}: cantidad debe ser mayor a 0.")

            # ==========================
            # TALLA
            # ==========================
            if not item.get("talla"):
                raise ValidationError(f"Item {i}: talla obligatoria.")

            # ==========================
            # PRODUCTO BASE
            # ==========================
            if not item.get("producto_base_id"):
                raise ValidationError(f"Item {i}: producto_base_id obligatorio.")