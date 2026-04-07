# apps/inventory/services/traslado_service.py
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import Stock, MovimientoStock
from apps.inventory.models import Traslado


class TrasladoService:

    @staticmethod
    @transaction.atomic
    def ejecutar_traslado(traslado_id):

        traslado = (
            Traslado.objects
            .select_for_update()
            .prefetch_related("detalles__variante")
            .get(id=traslado_id)
        )

        if traslado.ejecutado:
            raise ValidationError("El traslado ya fue ejecutado.")

        if traslado.origen_id == traslado.destino_id:
            raise ValidationError("Origen y destino no pueden ser iguales.")

        movimientos = []

        for detalle in traslado.detalles.all():

            variante = detalle.variante
            cantidad = Decimal(detalle.cantidad)

            if cantidad <= 0:
                raise ValidationError("Cantidad inválida en traslado.")

            # ==========================
            # STOCK ORIGEN (OBLIGATORIO)
            # ==========================
            stock_origen = Stock.objects.select_for_update().filter(
                variante=variante,
                sucursal=traslado.origen
            ).first()

            if not stock_origen:
                raise ValidationError(
                    f"No existe stock en {traslado.origen} para {variante}"
                )

            if stock_origen.cantidad < cantidad:
                raise ValidationError(
                    f"Stock insuficiente en {traslado.origen} para {variante}"
                )

            # ==========================
            # STOCK DESTINO
            # ==========================
            stock_destino, _ = Stock.objects.get_or_create(
                variante=variante,
                sucursal=traslado.destino,
                defaults={"cantidad": Decimal("0")}
            )

            # ==========================
            # MOVIMIENTO STOCK
            # ==========================
            stock_origen.cantidad -= cantidad
            stock_origen.save(update_fields=["cantidad"])

            stock_destino.cantidad += cantidad
            stock_destino.save(update_fields=["cantidad"])

            movimientos.append(
                MovimientoStock(
                    variante=variante,
                    sucursal=traslado.origen,
                    tipo="TRASLADO",
                    cantidad=-cantidad,
                    referencia=f"Traslado {traslado.id} SALIDA"
                )
            )

            movimientos.append(
                MovimientoStock(
                    variante=variante,
                    sucursal=traslado.destino,
                    tipo="TRASLADO",
                    cantidad=cantidad,
                    referencia=f"Traslado {traslado.id} ENTRADA"
                )
            )

        MovimientoStock.objects.bulk_create(movimientos)

        traslado.ejecutado = True
        traslado.save(update_fields=["ejecutado"])

        return traslado