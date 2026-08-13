from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.inventory.models import Stock
from apps.sales.models import (
    Carrito,
    CarritoItem,
    ListaPrecio,
    PrecioVariante,
)
from apps.sales.services.carrito_service import CarritoService
from apps.sales.services.serializers import serializar_carrito
from .caja_service import CajaService


class POSService:
    MEDIOS_PAGO = {
        "EFECTIVO",
        "TARJETA",
        "TRANSFERENCIA",
    }

    TIPOS_VENTA = {
        "DETAL",
        "MAYORISTA",
    }

    @staticmethod
    def _decimal(valor, mensaje):
        try:
            return Decimal(str(valor or 0))
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as error:
            raise ValidationError(mensaje) from error

    @staticmethod
    def _obtener_carrito_bloqueado(
        usuario,
        sucursal,
        venta_uuid,
    ):
        if not venta_uuid:
            raise ValidationError("Carrito inválido.")

        carrito = (
            Carrito.objects
            .select_for_update()
            .filter(
                uuid=venta_uuid,
                usuario=usuario,
                sucursal=sucursal,
                estado="BORRADOR",
            )
            .first()
        )

        if not carrito:
            raise ValidationError(
                "El carrito no existe o ya fue procesado."
            )

        return carrito

    @staticmethod
    def validar_stock_disponible(
        variante,
        cantidad,
        sucursal_id,
    ):
        cantidad = POSService._decimal(
            cantidad,
            "La cantidad es inválida.",
        )

        if cantidad <= 0:
            raise ValidationError(
                "La cantidad debe ser mayor a cero."
            )

        stock = (
            Stock.objects
            .select_for_update()
            .filter(
                variante=variante,
                sucursal_id=sucursal_id,
            )
            .first()
        )

        if not stock or stock.cantidad < cantidad:
            raise ValidationError(
                "Cantidad supera el inventario disponible."
            )

        return stock

    @staticmethod
    @transaction.atomic
    def crear_carrito(usuario, sucursal):
        return CarritoService.crear(
            usuario=usuario,
            sucursal=sucursal,
        )

    @staticmethod
    def obtener_carrito(usuario, sucursal):
        return (
            Carrito.objects
            .prefetch_related("items")
            .filter(
                usuario=usuario,
                sucursal=sucursal,
                estado="BORRADOR",
            )
            .order_by("-actualizado")
            .first()
        )

    @staticmethod
    def obtener_carrito_por_uuid(
        usuario,
        sucursal,
        carrito_uuid,
    ):
        return (
            Carrito.objects
            .prefetch_related(
                "items",
                "items__variante",
                "items__variante__producto_base",
                "items__variante__color",
                "items__variante__talla",
            )
            .filter(
                uuid=carrito_uuid,
                usuario=usuario,
                sucursal=sucursal,
                estado="BORRADOR",
            )
            .first()
        )

    @staticmethod
    def obtener_carritos_abiertos(usuario, sucursal):
        return (
            Carrito.objects
            .prefetch_related("items")
            .filter(
                usuario=usuario,
                sucursal=sucursal,
                estado="BORRADOR",
            )
            .order_by("-actualizado")
        )

    @staticmethod
    @transaction.atomic
    def agregar_producto(
        usuario,
        sucursal,
        venta_uuid,
        variante_id,
        cantidad=Decimal("1"),
    ):
        if venta_uuid:
            carrito = POSService._obtener_carrito_bloqueado(
                usuario=usuario,
                sucursal=sucursal,
                venta_uuid=venta_uuid,
            )
        else:
            carrito = CarritoService.crear(
                usuario=usuario,
                sucursal=sucursal,
            )

        CarritoService.agregar_item(
            carrito=carrito,
            variante_id=variante_id,
            cantidad=POSService._decimal(
                cantidad,
                "La cantidad es inválida.",
            ),
        )

        return serializar_carrito(carrito)

    @staticmethod
    @transaction.atomic
    def actualizar_cantidad(
        usuario,
        sucursal,
        item_id,
        cantidad=None,
        precio_unitario=None,
        venta_uuid=None,
    ):
        carrito = POSService._obtener_carrito_bloqueado(
            usuario=usuario,
            sucursal=sucursal,
            venta_uuid=venta_uuid,
        )

        item = (
            CarritoItem.objects
            .select_for_update()
            .select_related("variante")
            .filter(
                pk=item_id,
                carrito=carrito,
            )
            .first()
        )

        if not item:
            raise ValidationError("Item no encontrado.")

        actualizar_item = False

        if cantidad is not None:
            cantidad = POSService._decimal(
                cantidad,
                "La cantidad es inválida.",
            )

            if cantidad <= 0:
                item.delete()
                return serializar_carrito(carrito)

            POSService.validar_stock_disponible(
                variante=item.variante,
                cantidad=cantidad,
                sucursal_id=sucursal.id,
            )

            item.cantidad = cantidad
            actualizar_item = True

        if precio_unitario is not None:
            precio_unitario = POSService._decimal(
                precio_unitario,
                "El precio es inválido.",
            )

            if precio_unitario <= 0:
                raise ValidationError(
                    "El precio debe ser mayor a cero."
                )

            item.precio_unitario = precio_unitario
            actualizar_item = True

        if not actualizar_item:
            raise ValidationError(
                "Debe indicar cantidad o precio para actualizar."
            )

        item.save()

        return serializar_carrito(carrito)

    @staticmethod
    @transaction.atomic
    def eliminar_item(
        usuario,
        sucursal,
        item_id,
        venta_uuid=None,
    ):
        carrito = POSService._obtener_carrito_bloqueado(
            usuario=usuario,
            sucursal=sucursal,
            venta_uuid=venta_uuid,
        )

        item = (
            CarritoItem.objects
            .select_for_update()
            .filter(
                pk=item_id,
                carrito=carrito,
            )
            .first()
        )

        if not item:
            raise ValidationError("Item no encontrado.")

        item.delete()

        return serializar_carrito(carrito)

    @staticmethod
    @transaction.atomic
    def cambiar_tipo_venta(
        usuario,
        sucursal,
        tipo,
        venta_uuid=None,
    ):
        if tipo not in POSService.TIPOS_VENTA:
            raise ValidationError(
                "Tipo de venta inválido."
            )

        carrito = POSService._obtener_carrito_bloqueado(
            usuario=usuario,
            sucursal=sucursal,
            venta_uuid=venta_uuid,
        )

        lista = (
            ListaPrecio.objects
            .filter(
                sucursal=sucursal,
                tipo_venta=tipo,
                activa=True,
            )
            .order_by("id")
            .first()
        )

        if not lista:
            raise ValidationError(
                "No existe una lista de precios activa "
                "para este tipo de venta."
            )

        items = list(
            CarritoItem.objects
            .select_for_update()
            .select_related("variante")
            .filter(carrito=carrito)
        )

        precios = {
            precio.variante_id: precio.precio
            for precio in PrecioVariante.objects.filter(
                lista=lista,
                variante_id__in=[
                    item.variante_id
                    for item in items
                ],
            )
        }

        faltantes = [
            item.variante.sku
            for item in items
            if item.variante_id not in precios
        ]

        if faltantes:
            raise ValidationError(
                "Productos sin precio en la lista seleccionada: "
                + ", ".join(faltantes)
            )

        carrito.tipo_venta = tipo
        carrito.save(
            update_fields=[
                "tipo_venta",
                "actualizado",
            ]
        )

        for item in items:
            item.precio_unitario = precios[item.variante_id]
            item.save()

        return serializar_carrito(carrito)

    @staticmethod
    @transaction.atomic
    def guardar_estado(
        usuario,
        sucursal,
        venta_uuid,
        cliente="",
        observaciones="",
        efectivo=0,
        transferencia=0,
        tarjeta=0,
    ):
        carrito = POSService._obtener_carrito_bloqueado(
            usuario=usuario,
            sucursal=sucursal,
            venta_uuid=venta_uuid,
        )

        pagos = {
            "EFECTIVO": POSService._decimal(
                efectivo,
                "El monto de efectivo es inválido.",
            ),
            "TRANSFERENCIA": POSService._decimal(
                transferencia,
                "El monto de transferencia es inválido.",
            ),
            "TARJETA": POSService._decimal(
                tarjeta,
                "El monto de tarjeta es inválido.",
            ),
        }

        if any(monto < 0 for monto in pagos.values()):
            raise ValidationError(
                "Los montos de pago no pueden ser negativos."
            )

        carrito.cliente = (cliente or "").strip()
        carrito.observaciones = (
            observaciones or ""
        ).strip()
        carrito.monto_efectivo = pagos["EFECTIVO"]
        carrito.monto_transferencia = pagos[
            "TRANSFERENCIA"
        ]
        carrito.monto_tarjeta = pagos["TARJETA"]

        carrito.save(
            update_fields=[
                "cliente",
                "observaciones",
                "monto_efectivo",
                "monto_transferencia",
                "monto_tarjeta",
                "actualizado",
            ]
        )

        return serializar_carrito(carrito)

    @staticmethod
    @transaction.atomic
    def cerrar_venta(
        usuario,
        sucursal,
        turno_id,
        pagos,
        cliente="",
        observaciones="",
        venta_uuid=None,
    ):
        if not turno_id:
            raise ValidationError(
                "Debe abrir una caja antes de finalizar una venta."
            )

        if not isinstance(pagos, dict):
            raise ValidationError(
                "Los pagos de la venta son inválidos."
            )

        medios_no_permitidos = (
            set(pagos.keys()) - POSService.MEDIOS_PAGO
        )

        if medios_no_permitidos:
            raise ValidationError(
                "La venta contiene medios de pago no permitidos."
            )

        pagos_normalizados = {
            medio: POSService._decimal(
                pagos.get(medio, 0),
                f"El monto para {medio} es inválido.",
            )
            for medio in POSService.MEDIOS_PAGO
        }

        if any(
            monto < 0
            for monto in pagos_normalizados.values()
        ):
            raise ValidationError(
                "Los montos de pago no pueden ser negativos."
            )

        carrito = POSService._obtener_carrito_bloqueado(
            usuario=usuario,
            sucursal=sucursal,
            venta_uuid=venta_uuid,
        )

        if not carrito.items.exists():
            raise ValidationError(
                "No hay productos en la venta."
            )

        turno = CajaService.obtener_turno_bloqueado(
            turno_id=turno_id,
            sucursal=sucursal,
        )

        CajaService.validar_operador_turno(
            turno=turno,
            usuario=usuario,
        )

        carrito.cliente = (cliente or "").strip()
        carrito.observaciones = (
            observaciones or ""
        ).strip()
        carrito.monto_efectivo = pagos_normalizados[
            "EFECTIVO"
        ]
        carrito.monto_tarjeta = pagos_normalizados[
            "TARJETA"
        ]
        carrito.monto_transferencia = pagos_normalizados[
            "TRANSFERENCIA"
        ]

        carrito.save(
            update_fields=[
                "cliente",
                "observaciones",
                "monto_efectivo",
                "monto_tarjeta",
                "monto_transferencia",
                "actualizado",
            ]
        )

        if (
            sum(
                pagos_normalizados.values(),
                Decimal("0.00"),
            )
            < carrito.total
        ):
            raise ValidationError(
                "El pago no cubre el total de la venta."
            )

        return CarritoService.finalizar(
            carrito=carrito,
            turno=turno,
            usuario=usuario,
            pagos=pagos_normalizados,
        )

    @staticmethod
    @transaction.atomic
    def cancelar_venta(
        usuario,
        sucursal,
        venta_uuid=None,
    ):
        carrito = POSService._obtener_carrito_bloqueado(
            usuario=usuario,
            sucursal=sucursal,
            venta_uuid=venta_uuid,
        )

        carrito.estado = "CANCELADO"
        carrito.save(
            update_fields=[
                "estado",
                "actualizado",
            ]
        )

        carritos = list(
            POSService.obtener_carritos_abiertos(
                usuario=usuario,
                sucursal=sucursal,
            )
        )

        if not carritos:
            carritos = [
                CarritoService.crear(
                    usuario=usuario,
                    sucursal=sucursal,
                )
            ]

        return [
            serializar_carrito(carrito_abierto)
            for carrito_abierto in carritos
        ]