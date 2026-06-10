# apps/inventory/services/traslado_service.py
from decimal import Decimal

from django.db import transaction
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.inventory.models import Traslado
from apps.inventory.services.stock_service import InventoryService


class TrasladoService:

    TIPOS_SALIDA = [
        "COMPLETO",
        "SALIDA",
        "AJUSTE_SALIDA",
        "DANADO",
        "MERMA",
        "CONSUMO_INTERNO",
        "DEVOLUCION_PROVEEDOR",
    ]

    TIPOS_ENTRADA = [
        "ENTRADA",
        "AJUSTE_ENTRADA",
        "DEVOLUCION_CLIENTE",
        "INICIAL",
    ]

    # =====================================================
    # PROCESAR MOVIMIENTO
    # =====================================================

    @staticmethod
    @transaction.atomic
    def enviar_traslado(traslado_id, usuario):

        traslado = (
            Traslado.objects
            .select_for_update()
            .prefetch_related("detalles__variante")
            .get(id=traslado_id)
        )

        if traslado.estado != "BORRADOR":
            raise ValidationError(
                "Solo movimientos en borrador pueden procesarse."
            )

        if not traslado.detalles.exists():
            raise ValidationError(
                "El movimiento no tiene items."
            )

        # =================================================
        # VALIDACIONES
        # =================================================

        if traslado.tipo in ["COMPLETO", "SALIDA"]:

            if not traslado.origen:
                raise ValidationError(
                    "Sucursal origen requerida."
                )

        if traslado.tipo in ["COMPLETO", "ENTRADA"]:

            if not traslado.destino:
                raise ValidationError(
                    "Sucursal destino requerida."
                )

        if (
            traslado.tipo == "COMPLETO" and
            traslado.origen_id == traslado.destino_id
        ):
            raise ValidationError(
                "Origen y destino no pueden ser iguales."
            )

        # =================================================
        # MOVIMIENTOS SALIDA
        # =================================================

        if traslado.tipo in TrasladoService.TIPOS_SALIDA:

            for detalle in traslado.detalles.all():

                cantidad = Decimal(detalle.cantidad)

                if cantidad <= 0:
                    raise ValidationError(
                        "Cantidad inválida."
                    )

                InventoryService.descontar_stock(
                    variante=detalle.variante,
                    cantidad=cantidad,
                    sucursal_id=traslado.origen_id,
                    referencia=traslado.numero,
                    tipo=traslado.tipo,
                    user=usuario
                )

        # =================================================
        # MOVIMIENTOS ENTRADA
        # =================================================

        if traslado.tipo in TrasladoService.TIPOS_ENTRADA:

            for detalle in traslado.detalles.all():

                InventoryService.agregar_stock(
                    variante=detalle.variante,
                    cantidad=detalle.cantidad,
                    sucursal_id=traslado.destino_id,
                    referencia=traslado.numero,
                    tipo=traslado.tipo,
                    user=usuario
                )

        # =================================================
        # TRASLADO COMPLETO
        # =================================================

        if traslado.tipo == "COMPLETO":

            for detalle in traslado.detalles.all():

                InventoryService.agregar_stock(
                    variante=detalle.variante,
                    cantidad=detalle.cantidad,
                    sucursal_id=traslado.destino_id,
                    referencia=traslado.numero,
                    tipo=traslado.tipo,
                    user=usuario
                )

            traslado.estado = "RECIBIDO"

            traslado.fecha_recepcion = timezone.now()

            traslado.recibido_por = usuario

        else:

            traslado.estado = "ENVIADO"

        traslado.enviado_por = usuario

        traslado.fecha_envio = timezone.now()

        traslado.save()

        return traslado

    # =====================================================
    # RECIBIR SOLO ENTRADAS PENDIENTES
    # =====================================================

    @staticmethod
    @transaction.atomic
    def recibir_traslado(traslado_id, usuario):

        traslado = (
            Traslado.objects
            .select_for_update()
            .prefetch_related("detalles__variante")
            .get(id=traslado_id)
        )

        if traslado.estado != "ENVIADO":
            raise ValidationError(
                "Solo movimientos enviados."
            )

        if traslado.tipo not in ["SALIDA", "ENTRADA"]:
            raise ValidationError(
                "Este movimiento no requiere recepción."
            )

        for detalle in traslado.detalles.all():

            InventoryService.agregar_stock(
                variante=detalle.variante,
                cantidad=detalle.cantidad,
                sucursal_id=traslado.destino_id,
                referencia=traslado.numero,
                tipo=traslado.tipo,
                user=usuario
            )

        traslado.estado = "RECIBIDO"

        traslado.recibido_por = usuario

        traslado.fecha_recepcion = timezone.now()

        traslado.save()

        return traslado

    # =====================================================
    # CANCELAR
    # =====================================================

    @staticmethod
    @transaction.atomic
    def cancelar_traslado(traslado_id):

        traslado = (
            Traslado.objects
            .select_for_update()
            .get(id=traslado_id)
        )

        if traslado.estado == "RECIBIDO":
            raise ValidationError(
                "No puedes cancelar movimientos recibidos."
            )

        traslado.estado = "CANCELADO"

        traslado.save()

        return traslado