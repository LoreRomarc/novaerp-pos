# apps/inventory/services/confeccion_service.py

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.core.models import Sucursal

from apps.inventory.models_produccion import (
    OperacionProduccion,
    OperarioProduccion,
    ProduccionDetalle,
    ProduccionLote,
)
from apps.inventory.services.stock_service import InventoryService


class ConfeccionService:
    """
    Registra prendas confeccionadas.

    Una misma línea de corte puede ser confeccionada por varias
    costureras y en diferentes momentos.

    Solo aquí se agrega el producto terminado al inventario.
    """

    @staticmethod
    @transaction.atomic
    def registrar_confeccion(
        *,
        lote_id,
        sucursal,
        usuario,
        items,
    ):
        if not isinstance(items, list) or not items:
            raise ValidationError(
                "Debe registrar al menos una prenda confeccionada."
            )

        lote = (
            ProduccionLote.objects
            .select_for_update()
            .filter(
                pk=lote_id,
                sucursal=sucursal,
            )
            .first()
        )

        if not lote:
            raise ValidationError(
                "El lote no existe o pertenece a otra sucursal."
            )

        if lote.estado == ProduccionLote.Estado.FINALIZADO:
            raise ValidationError(
                "Este lote ya fue confeccionado completamente."
            )

        detalle_ids = set()
        operario_ids = set()
        items_limpios = []

        # ==============================================
        # VALIDAR DATOS RECIBIDOS
        # ==============================================
        for item in items:
            if not isinstance(item, dict):
                raise ValidationError(
                    "Una línea de confección es inválida."
                )

            try:
                detalle_id = int(item.get("detalle_id"))
                operario_id = int(item.get("operario_id"))
                cantidad = int(item.get("cantidad"))
            except (TypeError, ValueError) as error:
                raise ValidationError(
                    "La costurera o cantidad es inválida."
                ) from error

            if cantidad <= 0:
                raise ValidationError(
                    "La cantidad confeccionada debe ser mayor a cero."
                )

            try:
                sucursal_destino_id = int(item.get("sucursal_destino_id"))
            except (TypeError, ValueError) as error:
                raise ValidationError("La sucursal destino es inválida.") from error

            detalle_ids.add(detalle_id)
            operario_ids.add(operario_id)

            items_limpios.append(
                {
                    "detalle_id": detalle_id,
                    "operario_id": operario_id,
                    "cantidad": cantidad,
                    "sucursal_destino_id": sucursal_destino_id,
                }
            )

        # ==============================================
        # BLOQUEAR DETALLES DEL LOTE
        # ==============================================
        detalles = {
            detalle.id: detalle
            for detalle in (
                ProduccionDetalle.objects
                .select_for_update()
                .select_related("variante")
                .filter(
                    id__in=detalle_ids,
                    lote=lote,
                )
            )
        }

        if len(detalles) != len(detalle_ids):
            raise ValidationError(
                "Una de las prendas no pertenece a este lote."
            )

        destinos = {
            destino.id: destino
            for destino in Sucursal.objects.filter(
                id__in={item["sucursal_destino_id"] for item in items_limpios}, activa=True
            )
        }
        if len(destinos) != len({item["sucursal_destino_id"] for item in items_limpios}):
            raise ValidationError("Una sucursal destino no existe o está inactiva.")

        # ==============================================
        # VALIDAR COSTURERAS
        # ==============================================
        costureras = {
            operario.id: operario
            for operario in OperarioProduccion.objects.filter(
                id__in=operario_ids,
                sucursal=sucursal,
                activo=True,
                especialidad__in=[
                    OperarioProduccion.Especialidad.COSTURERA,
                    OperarioProduccion.Especialidad.AMBOS,
                ],
            )
        }

        if len(costureras) != len(operario_ids):
            raise ValidationError(
                "Una de las costureras no existe, está inactiva "
                "o pertenece a otra sucursal."
            )

        # ==============================================
        # REGISTRAR CONFECCIÓN E INGRESAR STOCK
        # ==============================================
        referencia = f"CONFECCION-{lote.referencia}"

        cantidades_nuevas = {}
        for item in items_limpios:
            cantidades_nuevas[item["detalle_id"]] = (
                cantidades_nuevas.get(item["detalle_id"], 0) + item["cantidad"]
            )

        for detalle_id, cantidad_nueva in cantidades_nuevas.items():
            detalle = detalles[detalle_id]
            ya_confeccionada = OperacionProduccion.objects.filter(
                detalle=detalle, tipo=OperacionProduccion.Tipo.CONFECCION,
            ).aggregate(total=Sum("cantidad"))["total"] or 0
            if cantidad_nueva > detalle.cantidad - ya_confeccionada:
                raise ValidationError(
                    f"No puede confeccionar {cantidad_nueva} unidades de {detalle.variante}; "
                    f"solo quedan {detalle.cantidad - ya_confeccionada} pendientes."
                )

        for item in items_limpios:
            detalle = detalles[item["detalle_id"]]

            OperacionProduccion.objects.create(
                detalle=detalle,
                operario=costureras[item["operario_id"]],
                tipo=OperacionProduccion.Tipo.CONFECCION,
                cantidad=item["cantidad"],
                sucursal_destino=destinos[item["sucursal_destino_id"]],
                registrado_por=usuario,
            )

            # Solo la prenda terminada ingresa a inventario.
            InventoryService.agregar_stock(
                variante=detalle.variante,
                cantidad=item["cantidad"],
                sucursal_id=item["sucursal_destino_id"],
                user=usuario,
                referencia=referencia,
                tipo="PRODUCCION",
                costo_unitario=detalle.costo_unitario,
            )

        # ==============================================
        # ACTUALIZAR ESTADO DEL LOTE
        # ==============================================
        detalles_lote = (
            ProduccionDetalle.objects
            .select_for_update()
            .filter(lote=lote)
        )

        quedan_pendientes = False

        for detalle in detalles_lote:
            total_confeccionado = (
                OperacionProduccion.objects
                .filter(
                    detalle=detalle,
                    tipo=OperacionProduccion.Tipo.CONFECCION,
                )
                .aggregate(total=Sum("cantidad"))["total"]
                or 0
            )

            if total_confeccionado < detalle.cantidad:
                quedan_pendientes = True
                break

        lote.estado = (
            ProduccionLote.Estado.EN_CONFECCION
            if quedan_pendientes
            else ProduccionLote.Estado.FINALIZADO
        )

        lote.save(update_fields=["estado"])

        return lote
