# apps/inventory/services/stock_service.py

from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import Stock, MovimientoStock
from apps.inventory.services.base_validators import BaseInventoryValidator


class InventoryService:

    @staticmethod
    def _get_user_sucursal(user, sucursal_id=None):

        if user:
            return BaseInventoryValidator.validar_usuario_y_sucursal(user).id

        if sucursal_id:
            return sucursal_id

        raise ValidationError("Debe especificar sucursal o usuario con sucursal.")

    @staticmethod
    def _crear_movimiento(
        variante,
        sucursal_id,
        cantidad,
        tipo,
        referencia,
        user,
        stock_final
    ):

        if not user:
            raise ValidationError("Movimiento de inventario requiere usuario.")

        MovimientoStock.objects.create(
            variante=variante,
            sucursal_id=sucursal_id,
            cantidad=cantidad,
            tipo=tipo,
            referencia=referencia,
            usuario=user,
            saldo_post_movimiento=stock_final
        )

    # ===============================
    # AGREGAR STOCK
    # ===============================
    @staticmethod
    @transaction.atomic
    def agregar_stock(
        variante,
        cantidad,
        user=None,
        sucursal_id=None,
        referencia=None,
        tipo="PRODUCCION"
    ):

        cantidad = BaseInventoryValidator.validar_cantidad(cantidad, "agregar_stock")

        sucursal_id = InventoryService._get_user_sucursal(user, sucursal_id)

        stock, _ = Stock.objects.select_for_update().get_or_create(
            variante=variante,
            sucursal_id=sucursal_id,
            defaults={"cantidad": Decimal("0")}
        )

        stock.cantidad += Decimal(cantidad)
        stock.save(update_fields=["cantidad"])

        InventoryService._crear_movimiento(
            variante=variante,
            sucursal_id=sucursal_id,
            cantidad=cantidad,
            tipo=tipo,
            referencia=referencia,
            user=user,
            stock_final=stock.cantidad
        )

    # ===============================
    # DESCONTAR STOCK
    # ===============================
    @staticmethod
    @transaction.atomic
    def descontar_stock(
        variante,
        cantidad,
        user=None,
        sucursal_id=None,
        referencia=None,
        tipo="VENTA"
    ):

        cantidad = BaseInventoryValidator.validar_cantidad(cantidad, "descontar_stock")

        sucursal_id = InventoryService._get_user_sucursal(user, sucursal_id)

        stock = Stock.objects.select_for_update().filter(
            variante=variante,
            sucursal_id=sucursal_id
        ).first()

        BaseInventoryValidator.validar_stock_disponible(
            stock,
            cantidad,
            "descontar_stock"
        )

        stock.cantidad -= Decimal(cantidad)
        stock.save(update_fields=["cantidad"])

        InventoryService._crear_movimiento(
            variante=variante,
            sucursal_id=sucursal_id,
            cantidad=-Decimal(cantidad),
            tipo=tipo,
            referencia=referencia,
            user=user,
            stock_final=stock.cantidad
        )