# apps/inventory/services/corte_service.py
from decimal import Decimal
import uuid
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import ProductoBase, TipoTela, Color
from apps.inventory.services.variant_service import VariantService
from apps.inventory.services.stock_service import InventoryService

from apps.inventory.models_produccion import (
    RolloTela,
    ProduccionLote,
    ProduccionDetalle,
    MovimientoRollo,
    CorteRollo
)


class CorteService:

    @staticmethod
    @transaction.atomic
    def ejecutar_corte(
        rollos,
        sucursal,
        usuario
    ):

        if not rollos:
            raise ValidationError("Debe seleccionar al menos un rollo.")

        total_prendas = 0


        for r in rollos:

            for item in r["items"]:

                total_prendas += int(
                    item["cantidad"]
                )

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

        
        detalles = []

        # ==========================
        # CARGAR CATÁLOGOS NECESARIOS
        # ==========================

        producto_ids = set()
        tela_ids = set()
        color_ids = set()

        for rollo in rollos:

            for item in rollo["items"]:

                producto_ids.add(item["producto_base_id"])
                tela_ids.add(item["tipo_tela_id"])
                color_ids.add(item["color_id"])


        productos_map = {
            p.id: p
            for p in ProductoBase.objects.filter(
                id__in=producto_ids
            )
        }

        telas_map = {
            t.id: t
            for t in TipoTela.objects.filter(
                id__in=tela_ids
            )
        }

        colores_map = {
            c.id: c
            for c in Color.objects.filter(
                id__in=color_ids
            )
        }


        for r in rollos:

            rollo_actual = next(
                rollo
                for rollo, _ in rollos_objs
                if rollo.id == int(r["rollo_id"])
            )

            for item in r["items"]:


                producto_base = productos_map[
                    item["producto_base_id"]
                ]

                tipo_tela = telas_map[
                    item["tipo_tela_id"]
                ]

                color = colores_map[
                    item["color_id"]
                ]

                cantidad = int(item["cantidad"])

                variante = VariantService.obtener_o_crear(
                    producto_base=producto_base,
                    tipo_tela=tipo_tela,
                    color=color,
                    talla_nombre=item["talla"],
                )

                detalles.append(
                    ProduccionDetalle(
                        lote=lote,
                        rollo=rollo_actual,
                        variante=variante,
                        cantidad=cantidad,
                        consumo_unitario=consumo_unitario,
                        consumo_total=consumo_unitario * cantidad,
                        costo_unitario=0,
                        costo_total=0,
                    )
                )


                InventoryService.agregar_stock(
                    variante=variante,
                    cantidad=cantidad,
                    sucursal_id=sucursal.id,
                    user=usuario,
                    referencia=referencia,
                    tipo="PRODUCCION",
                    costo_unitario=0,
                )

        for d in detalles:
            print(
                "ROLLO:",
                d.rollo,
                "ROLLO_ID:",
                d.rollo_id,
                "VARIANTE:",
                d.variante_id
            )


        ProduccionDetalle.objects.bulk_create(detalles)

        lote.ejecutado = True
        lote.save(update_fields=["ejecutado"])

        return lote