# apps
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import Stock, MovimientoStock


class InventoryService:

    @staticmethod
    def _to_decimal(value):
        return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _get_user_sucursal(user, sucursal_id=None):

        if sucursal_id:
            return sucursal_id

        if user and hasattr(user, "profile") and user.profile.sucursal:
            return user.profile.sucursal.id

        raise ValidationError("Usuario sin sucursal.")

    # ======================================================
    # MOVIMIENTO (KARDEX)
    # ======================================================
    @staticmethod
    def _crear_movimiento(
        variante,
        sucursal_id,
        cantidad,
        tipo,
        referencia,
        user,
        stock_final,
        costo_unitario=None
    ):

        MovimientoStock.objects.create(
            variante=variante,
            sucursal_id=sucursal_id,
            cantidad=cantidad,
            tipo=tipo,
            referencia=referencia,
            usuario=user,  # 👈 IMPORTANTE: dejar user directo
            saldo_post_movimiento=stock_final,
            costo_unitario=costo_unitario
        )

    # ======================================================
    # ENTRADA
    # ======================================================
    @staticmethod
    @transaction.atomic
    def agregar_stock(
        variante,
        cantidad,
        user=None,
        sucursal_id=None,
        referencia=None,
        tipo="PRODUCCION",
        costo_unitario=None
    ):

        cantidad = Decimal(cantidad)

        if cantidad <= 0:
            raise ValidationError("Cantidad debe ser mayor a 0.")

        sucursal_id = InventoryService._get_user_sucursal(user, sucursal_id)

        stock, _ = Stock.objects.select_for_update().get_or_create(
            variante=variante,
            sucursal_id=sucursal_id,
            defaults={"cantidad": Decimal("0")}
        )

        if costo_unitario is not None:
            total = stock.cantidad + cantidad
            stock.costo_promedio = (
                (stock.costo_promedio * stock.cantidad) +
                (Decimal(costo_unitario) * cantidad)
            ) / total if total > 0 else 0

        stock.cantidad += cantidad
        stock.save()

        InventoryService._crear_movimiento(
            variante=variante,
            sucursal_id=sucursal_id,
            cantidad=cantidad,
            tipo=tipo,
            referencia=referencia,
            user=user,
            stock_final=stock.cantidad,
            costo_unitario=costo_unitario
        )

    # ======================================================
    # SALIDA
    # ======================================================
    @staticmethod
    @transaction.atomic
    def descontar_stock(
        variante,
        cantidad,
        user=None,
        sucursal_id=None,
        referencia=None,
        tipo="VENTA",
        costo_unitario=None
    ):

        cantidad = Decimal(cantidad)

        if cantidad <= 0:
            raise ValidationError("Cantidad debe ser mayor a 0.")

        sucursal_id = InventoryService._get_user_sucursal(user, sucursal_id)

        stock = Stock.objects.select_for_update().filter(
            variante=variante,
            sucursal_id=sucursal_id
        ).first()

        if not stock:
            raise ValidationError("No existe stock.")

        if stock.cantidad < cantidad:
            raise ValidationError("Stock insuficiente.")

        stock.cantidad -= cantidad
        stock.save()

        InventoryService._crear_movimiento(
            variante=variante,
            sucursal_id=sucursal_id,
            cantidad=-cantidad,
            tipo=tipo,
            referencia=referencia,
            user=user,
            stock_final=stock.cantidad,
            costo_unitario=costo_unitario
        )