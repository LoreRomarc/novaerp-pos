# apps/inventory/services/stock_service.py
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import Stock, MovimientoStock, ProductoVariante

class InventoryService:

    @staticmethod
    @transaction.atomic
    def agregar_stock(variante: ProductoVariante, cantidad: float, sucursal_id=None, referencia=None, tipo="PRODUCCION"):
        stock, _ = Stock.objects.get_or_create(
            variante=variante,
            sucursal_id=sucursal_id,
            defaults={"cantidad": 0}
        )
        stock.cantidad += cantidad
        stock.save()

        MovimientoStock.objects.create(
            variante=variante,
            sucursal_id=sucursal_id,
            cantidad=cantidad,
            tipo=tipo,
            referencia=referencia
        )

    @staticmethod
    @transaction.atomic
    def descontar_stock(variante: ProductoVariante, cantidad: float, sucursal_id, referencia=None, tipo="VENTA"):
        stock = Stock.objects.filter(variante=variante, sucursal_id=sucursal_id).first()
        if not stock or stock.cantidad < cantidad:
            raise ValidationError(f"Stock insuficiente en sucursal {sucursal_id} para {variante.producto_base.nombre}")
        stock.cantidad -= cantidad
        stock.save()

        MovimientoStock.objects.create(
            variante=variante,
            sucursal_id=sucursal_id,
            cantidad=cantidad,
            tipo=tipo,
            referencia=referencia
        )

    @staticmethod
    @transaction.atomic
    def trasladar_stock(variante: ProductoVariante, cantidad: float, sucursal_origen: int, sucursal_destino: int, referencia=None):
        InventoryService.descontar_stock(variante, cantidad, sucursal_origen, referencia, tipo="TRASLADO_SALIDA")
        InventoryService.agregar_stock(variante, cantidad, sucursal_destino, referencia, tipo="TRASLADO_ENTRADA")