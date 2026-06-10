# apps/inventory/services/corte_service.py
from decimal import Decimal
import uuid
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models_produccion import (
    RolloTela,
    ProduccionLote,
    ProduccionDetalle,
    MovimientoRollo,
    CorteRollo
)

from apps.inventory.models import ProductoVariante
from apps.inventory.services.stock_service import InventoryService


class CorteService:

    @staticmethod
    @transaction.atomic
    def ejecutar_corte(
        rollos,
        items,
        sucursal,
        usuario
    ):

        if not rollos:
            raise ValidationError("Debe seleccionar al menos un rollo.")

        if not items:
            raise ValidationError("Debe haber producción.")

        total_prendas = sum(int(i["cantidad"]) for i in items)

        if total_prendas <= 0:
            raise ValidationError("Sin producción.")

        consumo_total = Decimal("0")
        rollos_objs = []

        # ==========================
        # VALIDAR Y BLOQUEAR ROLLOS
        # ==========================
        for r in rollos:

            rollo = RolloTela.objects.select_for_update().get(id=r["rollo_id"])
            metros = Decimal(r["metros"])

            if metros <= 0:
                raise ValidationError("Metros inválidos.")

            if metros > rollo.cantidad_disponible:
                raise ValidationError(f"Excede rollo {rollo.codigo}")

            consumo_total += metros

            rollos_objs.append((rollo, metros))

        consumo_unitario = consumo_total / Decimal(total_prendas)

        referencia = f"CORTE-{uuid.uuid4().hex[:8]}"

        # ==========================
        # LOTE
        # ==========================
        lote = ProduccionLote.objects.create(
            sucursal=sucursal,
            consumo_total=consumo_total,
            consumo_unitario=consumo_unitario,
            total_prendas=total_prendas,
            operario=usuario,
            referencia=referencia
        )

        # ==========================
        # CONSUMO DE ROLLOS
        # ==========================
        for rollo, metros in rollos_objs:

            costo = metros * rollo.costo_por_metro

            CorteRollo.objects.create(
                lote=lote,
                rollo=rollo,
                metros_consumidos=metros,
                costo_total=costo
            )

            rollo.cantidad_disponible -= metros

            MovimientoRollo.objects.create(
                rollo=rollo,
                tipo="CONSUMO",
                cantidad=metros,
                saldo_post=rollo.cantidad_disponible,
                referencia=referencia,
                usuario=usuario
            )

            if rollo.cantidad_disponible <= 0:
                rollo.estado = "CONSUMIDO"

            rollo.save()

        # ==========================
        # DETALLES PRODUCCIÓN
        # ==========================
        variantes = ProductoVariante.objects.all()

        variantes_map = {
            (v.producto_base_id, v.talla.nombre.upper()): v
            for v in variantes
        }

        detalles = []

        for item in items:

            key = (item["producto_base_id"], item["talla"].upper())
            variante = variantes_map.get(key)

            if not variante:
                raise ValidationError(f"Variante no existe {key}")

            cantidad = int(item["cantidad"])

            detalles.append(
                ProduccionDetalle(
                    lote=lote,
                    variante=variante,
                    cantidad=cantidad,
                    consumo_unitario=consumo_unitario,
                    consumo_total=consumo_unitario * cantidad,
                    costo_unitario=0,
                    costo_total=0
                )
            )

            InventoryService.agregar_stock(
                variante=variante,
                cantidad=cantidad,
                sucursal_id=sucursal.id,
                user=usuario,
                referencia=referencia,
                tipo="PRODUCCION",
                costo_unitario=0
            )

        ProduccionDetalle.objects.bulk_create(detalles)

        lote.ejecutado = True
        lote.save(update_fields=["ejecutado"])

        return lote