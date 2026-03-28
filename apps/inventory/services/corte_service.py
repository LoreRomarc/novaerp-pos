# apps/inventory/services/corte_service.py
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models_produccion import (
    RolloTela,
    ProduccionLote,
    ProduccionDetalle,
    IngresoProduccion,
    IngresoProduccionDetalle,
)
from apps.inventory.models import ProductoVariante


class CorteService:

    @staticmethod
    @transaction.atomic
    def ejecutar_corte(rollo_id, es_completo, metros_usados, items):

        rollo = (
            RolloTela.objects
            .select_for_update()
            .select_related("tipo_tela", "color")
            .get(id=rollo_id)
        )

        if rollo.estado == "CONSUMIDO":
            raise ValidationError("El rollo ya está consumido.")

        if es_completo:
            consumo_total = rollo.cantidad_disponible
        else:
            consumo_total = Decimal(metros_usados or 0)

            if consumo_total <= 0:
                raise ValidationError("Metros inválidos.")

            if consumo_total > rollo.cantidad_disponible:
                raise ValidationError("Excede disponible del rollo.")

        total_prendas = sum(int(i["cantidad"]) for i in items)

        if total_prendas <= 0:
            raise ValidationError("Debe haber prendas.")

        consumo_unitario = consumo_total / Decimal(total_prendas)

        lote = ProduccionLote.objects.create(
            rollo=rollo,
            tipo_tela=rollo.tipo_tela,
            color=rollo.color,
            consumo_total=consumo_total,
            consumo_unitario=consumo_unitario,
            total_prendas=total_prendas,
        )

        ingreso = IngresoProduccion.objects.create()

        for item in items:

            producto_base_id = item["producto_base_id"]
            talla = item["talla"]
            cantidad = int(item["cantidad"])

            variante = ProductoVariante.objects.filter(
                producto_base_id=producto_base_id,
                tipo_tela=rollo.tipo_tela,
                color=rollo.color,
                talla=talla
            ).first()

            if not variante:
                raise ValidationError(
                    f"No existe variante para producto {producto_base_id}, talla {talla}"
                )

            ProduccionDetalle.objects.create(
                lote=lote,
                producto_base_id=producto_base_id,
                talla=talla,
                cantidad=cantidad,
                tipo_tela=rollo.tipo_tela,
                color=rollo.color,
                variante=variante
            )

            IngresoProduccionDetalle.objects.create(
                ingreso=ingreso,
                variante=variante,
                cantidad=cantidad
            )

        # descontar rollo
        rollo.cantidad_disponible -= consumo_total

        if rollo.cantidad_disponible <= 0:
            rollo.cantidad_disponible = 0
            rollo.estado = "CONSUMIDO"

        rollo.save(update_fields=["cantidad_disponible", "estado"])

        lote.ejecutado = True
        lote.save(update_fields=["ejecutado"])

        return lote