from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.inventory.models import Stock


class StockService:

    @staticmethod
    @transaction.atomic
    def _get_stock(variante, sucursal):

        stock = (
            Stock.objects
            .select_for_update()
            .filter(variante=variante, sucursal=sucursal)
            .first()
        )

        if not stock:
            raise ValidationError("Stock no configurado para esta variante.")

        return stock

    @staticmethod
    @transaction.atomic
    def validar_stock_disponible(variante, sucursal, cantidad: Decimal):

        stock = StockService._get_stock(variante, sucursal)

        if stock.cantidad < cantidad:
            raise ValidationError(
                f"Stock insuficiente. Disponible: {stock.cantidad}"
            )

        return stock

    @staticmethod
    @transaction.atomic
    def descontar_stock(variante, sucursal, cantidad: Decimal):

        if cantidad <= 0:
            raise ValidationError("Cantidad inválida.")

        stock = StockService._get_stock(variante, sucursal)

        if stock.cantidad < cantidad:
            raise ValidationError("Stock insuficiente (concurrencia detectada).")

        stock.cantidad -= cantidad
        stock.save(update_fields=["cantidad"])

        return stock

    @staticmethod
    @transaction.atomic
    def devolver_stock(variante, sucursal, cantidad: Decimal):

        if cantidad <= 0:
            return

        stock = StockService._get_stock(variante, sucursal)
        stock.cantidad += cantidad
        stock.save(update_fields=["cantidad"])