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
from apps.core.models import Sucursal
from apps.inventory.services.stock_service import InventoryService


class CorteService:

    @staticmethod
    @transaction.atomic
    def ejecutar_corte(
        rollo_id,
        es_completo,
        metros_usados,
        items,
        sucursal,
        usuario
    ):

        # ==========================
        # VALIDACIONES BASE
        # ==========================
        if not sucursal:
            raise ValidationError("Sucursal requerida.")

        if not usuario:
            raise ValidationError("Usuario requerido para ejecutar corte.")

        # ==========================
        # BLOQUEO ROLLO
        # ==========================
        rollo = (
            RolloTela.objects
            .select_for_update()
            .select_related("tipo_tela", "color")
            .get(id=rollo_id)
        )

        if rollo.estado == "CONSUMIDO":
            raise ValidationError("El rollo ya está consumido.")

        ProduccionValidator.validar_items(items)

        # ==========================
        # CONSUMO
        # ==========================
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

        # ==========================
        # 🔥 COSTOS Y EFICIENCIA (NIVEL INDUSTRIAL)
        # ==========================
        costo_por_metro = Decimal("5000")  # 🔥 luego lo vuelves dinámico

        costo_total = consumo_total * costo_por_metro
        costo_unitario_real = costo_total / Decimal(total_prendas)

        # MERMA (lo que NO se convirtió en producto útil)
        merma = Decimal("0")  # puedes mejorar esto luego con lógica real

        eficiencia = Decimal("100")
        if consumo_total > 0:
            eficiencia = (consumo_total / (consumo_total + merma)) * 100

        # ==========================
        # CREAR LOTE
        # ==========================
        lote = ProduccionLote.objects.create(
            sucursal=sucursal,
            rollo=rollo,
            tipo_tela=rollo.tipo_tela,
            color=rollo.color,
            consumo_total=consumo_total,
            consumo_unitario=consumo_unitario,
            total_prendas=total_prendas,

            # 🔥 NUEVO NIVEL
            merma=merma,
            eficiencia=eficiencia,
            costo_total=costo_total,
            costo_unitario_real=costo_unitario_real,
            operario=usuario
        )

        ingreso = IngresoProduccion.objects.create()

        # ==========================
        # SUCURSAL FABRICA
        # ==========================
        sucursal_fabrica = Sucursal.objects.filter(
            nombre__iexact="FABRICA"
        ).first()

        if not sucursal_fabrica:
            raise ValidationError("No existe sucursal FABRICA")

        # ==========================
        # CACHE VARIANTES
        # ==========================
        variantes_cache = {
            (v.producto_base_id, v.talla): v
            for v in ProductoVariante.objects.filter(
                tipo_tela=rollo.tipo_tela,
                color=rollo.color,
                producto_base_id__in=[i["producto_base_id"] for i in items]
            )
        }

        detalles_produccion = []
        detalles_ingreso = []

        # ==========================
        # PROCESAR ITEMS
        # ==========================
        for item in items:

            producto_base_id = int(item["producto_base_id"])
            talla = item["talla"]
            cantidad = Decimal(item["cantidad"])

            variante = variantes_cache.get((producto_base_id, talla))

            if not variante:
                raise ValidationError(
                    f"No existe variante para producto {producto_base_id}, talla {talla}"
                )

            # DETALLE PRODUCCIÓN
            detalles_produccion.append(
                ProduccionDetalle(
                    lote=lote,
                    producto_base_id=producto_base_id,
                    talla=talla,
                    cantidad=int(cantidad),
                    tipo_tela=rollo.tipo_tela,
                    color=rollo.color,
                    variante=variante
                )
            )

            # INGRESO PRODUCCIÓN
            detalles_ingreso.append(
                IngresoProduccionDetalle(
                    ingreso=ingreso,
                    variante=variante,
                    cantidad=int(cantidad)
                )
            )

            # ==========================
            # STOCK
            # ==========================
            InventoryService.agregar_stock(
                variante=variante,
                cantidad=cantidad,
                sucursal_id=sucursal_fabrica.id,
                referencia=f"Lote {lote.id} - Corte",
                tipo="PRODUCCION",
                user=usuario
            )

        # BULK INSERT
        ProduccionDetalle.objects.bulk_create(detalles_produccion)
        IngresoProduccionDetalle.objects.bulk_create(detalles_ingreso)

        # ==========================
        # DESCONTAR ROLLO
        # ==========================
        rollo.cantidad_disponible -= consumo_total

        if rollo.cantidad_disponible <= 0:
            rollo.cantidad_disponible = Decimal("0")
            rollo.estado = "CONSUMIDO"

        rollo.save(update_fields=["cantidad_disponible", "estado"])

        # ==========================
        # FINALIZAR LOTE
        # ==========================
        lote.ejecutado = True
        lote.save(update_fields=["ejecutado"])

        return lote


# ==========================
# VALIDADOR
# ==========================
class ProduccionValidator:

    @staticmethod
    def validar_items(items):

        if not items:
            raise ValidationError("Debe ingresar al menos un item.")

        for item in items:

            if Decimal(item["cantidad"]) <= 0:
                raise ValidationError("Cantidad inválida en items.")

            if not item.get("talla"):
                raise ValidationError("Talla requerida.")