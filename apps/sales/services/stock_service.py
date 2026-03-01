# apps/sales/services/stock_service.py
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.inventory.models import Stock


class StockService:

    @staticmethod
    @transaction.atomic
    def validar_stock_disponible(producto, sucursal, cantidad_requerida: Decimal):
        stock = (
            Stock.objects
            .select_for_update()
            .filter(producto=producto, sucursal=sucursal)
            .first()
        )

        if not stock:
            raise ValidationError("Producto sin stock configurado en esta sucursal.")

        if stock.cantidad < cantidad_requerida:
            raise ValidationError("Stock insuficiente.")

        return stock

    @staticmethod
    @transaction.atomic
    def descontar_stock(producto, sucursal, cantidad: Decimal):
        stock = StockService.validar_stock_disponible(producto, sucursal, cantidad)
        stock.cantidad -= cantidad
        stock.save(update_fields=["cantidad"])

    @staticmethod
    @transaction.atomic
    def devolver_stock(producto, sucursal, cantidad: Decimal):
        stock = (
            Stock.objects
            .select_for_update()
            .get(producto=producto, sucursal=sucursal)
        )
        stock.cantidad += cantidad
        stock.save(update_fields=["cantidad"])