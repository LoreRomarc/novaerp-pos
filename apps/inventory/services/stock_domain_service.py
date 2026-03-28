# apps/inventory/services/stock_domain_service.py
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.core.models import Sucursal
from apps.inventory.models import Stock, MovimientoStock, ProductoVariante


class StockDomainService:

    BODEGA_NOMBRE = "BODEGA"

    # ======================================================
    # BODEGA
    # ======================================================

    @staticmethod
    def get_bodega():
        bodega, _ = Sucursal.objects.get_or_create(
            nombre=StockDomainService.BODEGA_NOMBRE,
            defaults={
                "direccion": "Bodega principal",
                "activa": True,
            }
        )
        return bodega

    # ======================================================
    # STOCK BASE
    # ======================================================

    @staticmethod
    def _get_or_create_stock(variante, sucursal):
        stock, _ = Stock.objects.select_for_update().get_or_create(
            variante=variante,
            sucursal=sucursal,
            defaults={"cantidad": Decimal("0")}
        )
        return stock

    # ======================================================
    # PRODUCCION → BODEGA
    # ======================================================

    @staticmethod
    @transaction.atomic
    def ingresar_produccion(detalle):

        if detalle.cantidad <= 0:
            raise ValidationError("Cantidad inválida.")

        bodega = StockDomainService.get_bodega()

        stock = StockDomainService._get_or_create_stock(
            detalle.variante,
            bodega
        )

        stock.cantidad += Decimal(detalle.cantidad)
        stock.save(update_fields=["cantidad"])

        MovimientoStock.objects.create(
            variante=detalle.variante,
            sucursal=bodega,
            tipo="PRODUCCION",
            cantidad=detalle.cantidad,
            referencia=detalle.ingreso_id
        )

    # ======================================================
    # TRASLADOS
    # ======================================================

    @staticmethod
    @transaction.atomic
    def ejecutar_traslado(traslado):

        if traslado.ejecutado:
            raise ValidationError("El traslado ya fue ejecutado.")

        for detalle in traslado.detalles.select_related("variante"):

            if detalle.cantidad <= 0:
                raise ValidationError("Cantidad inválida en traslado.")

            stock_origen = StockDomainService._get_or_create_stock(
                detalle.variante,
                traslado.origen
            )

            if stock_origen.cantidad < detalle.cantidad:
                raise ValidationError(
                    f"Stock insuficiente en {traslado.origen} para {detalle.variante}"
                )

            stock_destino = StockDomainService._get_or_create_stock(
                detalle.variante,
                traslado.destino
            )

            # restar origen
            stock_origen.cantidad -= detalle.cantidad
            stock_origen.save(update_fields=["cantidad"])

            # sumar destino
            stock_destino.cantidad += detalle.cantidad
            stock_destino.save(update_fields=["cantidad"])

            # movimientos
            MovimientoStock.objects.create(
                variante=detalle.variante,
                sucursal=traslado.origen,
                tipo="TRASLADO",
                cantidad=-detalle.cantidad,
                referencia=traslado.id
            )

            MovimientoStock.objects.create(
                variante=detalle.variante,
                sucursal=traslado.destino,
                tipo="TRASLADO",
                cantidad=detalle.cantidad,
                referencia=traslado.id
            )

        traslado.ejecutado = True
        traslado.save(update_fields=["ejecutado"])