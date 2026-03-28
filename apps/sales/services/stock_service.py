# apps/sales/services/stock_service.py
from decimal import Decimal
from django.core.exceptions import ValidationError

from apps.inventory.services.stock_domain_service import StockDomainService
from apps.inventory.models import Stock


class StockService:

    # ======================================================
    # GET STOCK
    # ======================================================

    @staticmethod
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

    # ======================================================
    # VALIDAR
    # ======================================================

    @staticmethod
    def validar_stock_disponible(variante, sucursal, cantidad: Decimal):

        stock = StockService._get_stock(variante, sucursal)

        if stock.cantidad < cantidad:
            raise ValidationError(
                f"Stock insuficiente. Disponible: {stock.cantidad}"
            )

        return stock

    # ======================================================
    # DESCONTAR (POS)
    # ======================================================

    @staticmethod
    def descontar_stock(variante, sucursal, cantidad: Decimal):

        if cantidad <= 0:
            raise ValidationError("Cantidad inválida.")

        stock = StockService._get_stock(variante, sucursal)

        if stock.cantidad < cantidad:
            raise ValidationError("Stock insuficiente.")

        stock.cantidad -= cantidad
        stock.save(update_fields=["cantidad"])

        return stock

    # ======================================================
    # DEVOLVER
    # ======================================================

    @staticmethod
    def devolver_stock(variante, sucursal, cantidad: Decimal):

        if cantidad <= 0:
            return

        stock = StockService._get_stock(variante, sucursal)

        stock.cantidad += cantidad
        stock.save(update_fields=["cantidad"])