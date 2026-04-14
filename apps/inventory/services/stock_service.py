from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import Stock, MovimientoStock, ProductoVariante


class InventoryService:

    @staticmethod
    def _get_user_sucursal(user, sucursal_id=None):
        if hasattr(user, "profile") and user.profile.sucursal:
            return user.profile.sucursal.id

        if sucursal_id:
            return sucursal_id

        raise ValidationError("Usuario sin sucursal.")

    @staticmethod
    def _crear_movimiento(variante, sucursal_id, cantidad, tipo, referencia, user, stock_final):

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
    # AGREGAR
    # ===============================
    @staticmethod
    @transaction.atomic
    def agregar_stock(variante, cantidad, user=None, sucursal_id=None, referencia=None, tipo="PRODUCCION"):

        cantidad = Decimal(cantidad)
        sucursal_id = InventoryService._get_user_sucursal(user, sucursal_id)

        stock, _ = Stock.objects.select_for_update().get_or_create(
            variante=variante,
            sucursal_id=sucursal_id,
            defaults={"cantidad": 0}
        )

        stock.cantidad += cantidad
        stock.save(update_fields=["cantidad"])

        InventoryService._crear_movimiento(
            variante, sucursal_id, cantidad, tipo, referencia, user, stock.cantidad
        )

    # ===============================
    # DESCONTAR
    # ===============================
    @staticmethod
    @transaction.atomic
    def descontar_stock(variante, cantidad, user=None, sucursal_id=None, referencia=None, tipo="VENTA"):

        cantidad = Decimal(cantidad)
        sucursal_id = InventoryService._get_user_sucursal(user, sucursal_id)

        stock = Stock.objects.select_for_update().filter(
            variante=variante,
            sucursal_id=sucursal_id
        ).first()

        if not stock or stock.cantidad < cantidad:
            raise ValidationError(f"Stock insuficiente {variante}")

        stock.cantidad -= cantidad
        stock.save(update_fields=["cantidad"])

        InventoryService._crear_movimiento(
            variante, sucursal_id, -cantidad, tipo, referencia, user, stock.cantidad
        )