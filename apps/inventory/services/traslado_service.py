# apps/inventory/services/traslado_service.py

from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import Stock, Traslado
from apps.inventory.services.stock_service import InventoryService


class TrasladoService:

    @staticmethod
    @transaction.atomic
    def ejecutar_traslado(traslado_id, usuario):

        if not usuario:
            raise ValidationError("Usuario requerido para ejecutar traslado.")

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

        for detalle in traslado.detalles.all():

            variante = detalle.variante
            cantidad = Decimal(detalle.cantidad)

            if cantidad <= 0:
                raise ValidationError("Cantidad inválida en traslado.")

            # ==========================
            # VALIDAR STOCK ORIGEN
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
            # SALIDA (ORIGEN)
            # ==========================
            InventoryService.descontar_stock(
                variante=variante,
                cantidad=cantidad,
                sucursal_id=traslado.origen.id,
                referencia=f"Traslado {traslado.id} SALIDA",
                tipo="TRASLADO",
                user=usuario
            )

            # ==========================
            # ENTRADA (DESTINO)
            # ==========================
            InventoryService.agregar_stock(
                variante=variante,
                cantidad=cantidad,
                sucursal_id=traslado.destino.id,
                referencia=f"Traslado {traslado.id} ENTRADA",
                tipo="TRASLADO",
                user=usuario
            )

        traslado.ejecutado = True
        traslado.save(update_fields=["ejecutado"])

        return traslado