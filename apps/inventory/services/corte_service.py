# apps/inventory/services/corte_service.py
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.inventory.models import (
    Color,
    ProductoBase,
    TipoTela,
)
from apps.inventory.models_produccion import (
    CorteRollo,
    MovimientoRollo,
    OperacionProduccion,
    OperarioProduccion,
    ProduccionDetalle,
    ProduccionLote,
    RolloTela,
)
from apps.inventory.services.corte_numero_service import (
    NumeroCorteService,
)
from apps.inventory.services.variant_service import VariantService


class CorteService:

    @staticmethod
    @transaction.atomic
    def ejecutar_corte(
        rollos,
        sucursal,
        usuario,
    ):
        if not rollos:
            raise ValidationError(
                "Debe seleccionar al menos un rollo."
            )

        total_prendas = 0
        rollos_ids = set()
        producto_ids = set()
        tela_ids = set()
        color_ids = set()
        operarios_ids = set()

        # ==================================================
        # VALIDAR ESTRUCTURA RECIBIDA
        # ==================================================
        for datos_rollo in rollos:
            rollo_id = datos_rollo.get("rollo_id")

            if not rollo_id:
                raise ValidationError("Debe seleccionar un rollo.")

            rollo_id = int(rollo_id)

            if rollo_id in rollos_ids:
                raise ValidationError(
                    "No puede usar el mismo rollo dos veces."
                )

            rollos_ids.add(rollo_id)

            items = datos_rollo.get("items") or []

            if not items:
                raise ValidationError(
                    "Cada rollo debe tener al menos una prenda."
                )

            for item in items:
                try:
                    cantidad = int(item.get("cantidad", 0))
                    operario_id = int(item.get("operario_id"))
                except (TypeError, ValueError) as error:
                    raise ValidationError(
                        "La cantidad o el cortador son inválidos."
                    ) from error

                if cantidad <= 0:
                    raise ValidationError(
                        "La cantidad debe ser mayor a cero."
                    )

                total_prendas += cantidad
                producto_ids.add(int(item["producto_base_id"]))
                tela_ids.add(int(item["tipo_tela_id"]))
                color_ids.add(int(item["color_id"]))
                operarios_ids.add(operario_id)

        if total_prendas <= 0:
            raise ValidationError("No hay prendas para cortar.")

        # ==================================================
        # BLOQUEAR Y VALIDAR ROLLOS
        # ==================================================
        rollos_bloqueados = {
            rollo.id: rollo
            for rollo in (
                RolloTela.objects
                .select_for_update()
                .select_related("tipo_tela", "color")
                .filter(id__in=rollos_ids)
            )
        }

        if len(rollos_bloqueados) != len(rollos_ids):
            raise ValidationError("Uno de los rollos no existe.")

        consumo_total = Decimal("0.00")
        costo_material_total = Decimal("0.00")
        consumo_por_rollo = {}

        for datos_rollo in rollos:
            rollo_id = int(datos_rollo["rollo_id"])
            rollo = rollos_bloqueados[rollo_id]

            try:
                metros = Decimal(str(datos_rollo.get("metros")))
            except Exception as error:
                raise ValidationError(
                    f"Los metros del rollo {rollo.codigo} son inválidos."
                ) from error

            if metros <= 0:
                raise ValidationError(
                    f"Los metros del rollo {rollo.codigo} "
                    "deben ser mayores a cero."
                )

            if metros > rollo.cantidad_disponible:
                raise ValidationError(
                    f"El consumo excede el disponible del rollo "
                    f"{rollo.codigo}."
                )

            consumo_por_rollo[rollo_id] = metros
            consumo_total += metros
            costo_material_total += (
                metros * rollo.costo_por_metro
            )

        # ==================================================
        # VALIDAR CATÁLOGOS Y CORTADORES
        # ==================================================
        productos = {
            producto.id: producto
            for producto in ProductoBase.objects.filter(
                id__in=producto_ids,
                activo=True,
            )
        }

        telas = {
            tela.id: tela
            for tela in TipoTela.objects.filter(
                id__in=tela_ids,
                activo=True,
            )
        }

        colores = {
            color.id: color
            for color in Color.objects.filter(
                id__in=color_ids,
            )
        }

        if len(productos) != len(producto_ids):
            raise ValidationError(
                "Uno de los productos no existe o está inactivo."
            )

        if len(telas) != len(tela_ids):
            raise ValidationError(
                "Una de las telas no existe o está inactiva."
            )

        if len(colores) != len(color_ids):
            raise ValidationError("Uno de los colores no existe.")

        cortadores = {
            operario.id: operario
            for operario in OperarioProduccion.objects.filter(
                id__in=operarios_ids,
                sucursal=sucursal,
                activo=True,
                especialidad__in=[
                    OperarioProduccion.Especialidad.CORTADOR,
                    OperarioProduccion.Especialidad.AMBOS,
                ],
            )
        }

        if len(cortadores) != len(operarios_ids):
            raise ValidationError(
                "Uno de los cortadores no existe, está inactivo "
                "o no pertenece a esta sucursal."
            )

        # ==================================================
        # CREAR LOTE
        # ==================================================
        consumo_unitario = (
            consumo_total / Decimal(total_prendas)
        )

        costo_material_unitario = (
            costo_material_total / Decimal(total_prendas)
        )

        anio, numero = NumeroCorteService.siguiente_numero()

        referencia = f"CORTE-{anio}-{numero:04d}"

        lote = ProduccionLote.objects.create(
            sucursal=sucursal,
            consumo_total=consumo_total,
            consumo_unitario=consumo_unitario,
            total_prendas=total_prendas,
            costo_total=costo_material_total,
            costo_unitario_real=costo_material_unitario,
            operario=usuario,
            referencia=referencia,
            numero_corte=numero,
            anio_corte=anio,
            estado=(
                ProduccionLote.Estado.PENDIENTE_CONFECCION
            ),
            ejecutado=True,
        )

        # ==================================================
        # DESCONTAR ROLLOS Y CREAR KARDEX DE TELA
        # ==================================================
        for rollo_id, metros in consumo_por_rollo.items():
            rollo = rollos_bloqueados[rollo_id]
            costo_rollo = metros * rollo.costo_por_metro

            CorteRollo.objects.create(
                lote=lote,
                rollo=rollo,
                metros_consumidos=metros,
                costo_total=costo_rollo,
            )

            rollo.cantidad_disponible -= metros

            MovimientoRollo.objects.create(
                rollo=rollo,
                tipo="CONSUMO",
                cantidad=metros,
                saldo_post=rollo.cantidad_disponible,
                referencia=referencia,
                usuario=usuario,
            )

            if rollo.cantidad_disponible <= 0:
                rollo.estado = "CONSUMIDO"

            rollo.save(
                update_fields=[
                    "cantidad_disponible",
                    "estado",
                ]
            )

        # ==================================================
        # CREAR DETALLES Y REGISTROS DE CORTE
        #
        # IMPORTANTE:
        # Aquí NO se agrega stock. Las prendas quedan
        # pendientes de confección.
        # ==================================================
        orden = 1

        for datos_rollo in rollos:
            rollo = rollos_bloqueados[
                int(datos_rollo["rollo_id"])
            ]

            for item in datos_rollo["items"]:
                cantidad = int(item["cantidad"])

                variante = VariantService.obtener_o_crear(
                    producto_base=productos[
                        int(item["producto_base_id"])
                    ],
                    tipo_tela=telas[
                        int(item["tipo_tela_id"])
                    ],
                    color=colores[
                        int(item["color_id"])
                    ],
                    talla_nombre=item["talla"],
                )

                detalle = ProduccionDetalle.objects.create(
                    lote=lote,
                    rollo=rollo,
                    variante=variante,
                    cantidad=cantidad,
                    orden=orden,
                    consumo_unitario=consumo_unitario,
                    consumo_total=(
                        consumo_unitario * cantidad
                    ),
                    costo_unitario=costo_material_unitario,
                    costo_total=(
                        costo_material_unitario * cantidad
                    ),
                )

                OperacionProduccion.objects.create(
                    detalle=detalle,
                    operario=cortadores[
                        int(item["operario_id"])
                    ],
                    tipo=OperacionProduccion.Tipo.CORTE,
                    cantidad=cantidad,
                    registrado_por=usuario,
                )

                orden += 1

        return lote