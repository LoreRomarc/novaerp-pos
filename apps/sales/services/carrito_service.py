# apps/sales/services/carrito_service.py
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from apps.inventory.models import ProductoVariante
from apps.inventory.models import Stock

from apps.sales.models import (
    Carrito,
    CarritoItem,
    ListaPrecio,
    PrecioVariante,
)


class CarritoService:

    # =====================================================
    # OBTENER CARRITO
    # =====================================================

    @staticmethod
    def obtener(usuario, sucursal, carrito_uuid):

        if not carrito_uuid:
            raise ValidationError("Carrito inválido.")

        carrito = (
            Carrito.objects
            .prefetch_related(
                "items",
                "items__variante",
                "items__variante__producto_base",
                "items__variante__color",
                "items__variante__talla",
                "items__variante__tipo_tela",
            )
            .filter(
                uuid=carrito_uuid,
                usuario=usuario,
                sucursal=sucursal,
            )
            .first()
        )

        if not carrito:
            raise ValidationError("Carrito no encontrado.")

        return carrito

    # =====================================================
    # CREAR CARRITO
    # =====================================================
    @staticmethod
    @transaction.atomic
    def crear(usuario, sucursal):

        carrito = Carrito.objects.create(
            usuario=usuario,
            sucursal=sucursal,
            estado="BORRADOR",
        )

        return carrito


    # =====================================================
    # BUSCAR VARIANTE
    # =====================================================

    @staticmethod
    def buscar_variante(variante_id=None, termino=None, sucursal=None):

        qs = ProductoVariante.objects.select_related(
            "producto_base",
            "color",
            "tipo_tela",
            "talla",
        )

        if variante_id:

            qs = qs.filter(id=variante_id)

        elif termino:

            qs = qs.filter(

                Q(sku__iexact=termino)
                |
                Q(codigo_barras__iexact=termino)
                |
                Q(producto_base__nombre__icontains=termino)

            )

        else:

            return None

        variante = qs.first()

        if not variante:
            return None

        stock = (
            Stock.objects
            .select_for_update()
            .filter(
                variante=variante,
                sucursal=sucursal,
            )
            .first()
        )

        if not stock:
            return None

        if stock.cantidad <= 0:
            raise ValidationError("No hay stock.")

        return variante

    # =====================================================
    # PRECIO
    # =====================================================

    @staticmethod
    def precio(variante, carrito):

        lista = (
            ListaPrecio.objects.filter(
                sucursal=carrito.sucursal,
                tipo_venta=carrito.tipo_venta,
                activa=True,
            )
            .first()
        )

        if not lista:

            raise ValidationError(
                "No existe lista de precios."
            )

        precio = (
            PrecioVariante.objects.filter(
                variante=variante,
                lista=lista,
            )
            .first()
        )

        if not precio:

            raise ValidationError(
                "Producto sin precio."
            )

        return precio.precio


    # =====================================================
    # AGREGAR ITEM AL CARRITO
    # =====================================================
    @staticmethod
    @transaction.atomic
    def agregar_item(
        carrito,
        variante_id,
        cantidad=1
    ):

        if cantidad <= 0:
            raise ValidationError(
                "Cantidad inválida."
            )


        variante = CarritoService.buscar_variante(
            variante_id=variante_id,
            sucursal=carrito.sucursal
        )


        if not variante:
            raise ValidationError(
                "Producto no encontrado."
            )


        precio = CarritoService.precio(
            variante,
            carrito
        )


        item = (
            CarritoItem.objects
            .filter(
                carrito=carrito,
                variante=variante
            )
            .first()
        )


        if item:

            nueva_cantidad = (
                item.cantidad +
                Decimal(str(cantidad))
            )

            item.cantidad = nueva_cantidad
            item.precio_unitario = precio

            item.save()

        else:

            CarritoItem.objects.create(

                carrito=carrito,

                variante=variante,

                cantidad=Decimal(str(cantidad)),

                precio_unitario=precio,

            )


        CarritoService.recalcular(
            carrito
        )


        return carrito

    # =====================================================
    # RECALCULAR
    # =====================================================
    @staticmethod
    def recalcular(carrito):
        """
        Compatibilidad para llamadas existentes.

        Los totales del carrito se calculan dinámicamente y cada
        CarritoItem recalcula sus importes al guardarse, por lo que
        no se deben volver a guardar todos los ítems.
        """
        carrito.refresh_from_db()

        return carrito

    # =====================================================
    # ELIMINAR ITEM
    # =====================================================

    @staticmethod
    @transaction.atomic
    def eliminar_item(
        carrito,
        item_id
    ):

        item = (
            CarritoItem.objects
            .filter(
                id=item_id,
                carrito=carrito
            )
            .first()
        )


        if not item:

            raise ValidationError(
                "Item no encontrado."
            )


        item.delete()


        CarritoService.recalcular(
            carrito
        )


        return carrito

    # =====================================================
    # ACTUALIZAR CANTIDAD
    # =====================================================

    @staticmethod
    @transaction.atomic
    def actualizar_cantidad(
        carrito,
        item_id,
        cantidad
    ):

        cantidad = Decimal(
            str(cantidad)
        )


        if cantidad <= 0:

            raise ValidationError(
                "Cantidad inválida."
            )


        item = (
            CarritoItem.objects
            .select_related(
                "variante"
            )
            .filter(
                id=item_id,
                carrito=carrito
            )
            .first()
        )


        if not item:

            raise ValidationError(
                "Item no encontrado."
            )


        # validar nuevamente stock

        stock = Stock.objects.filter(
            variante=item.variante,
            sucursal=carrito.sucursal
        ).first()


        if not stock:

            raise ValidationError(
                "Producto sin stock."
            )


        if stock.cantidad < cantidad:

            raise ValidationError(
                "Cantidad supera inventario disponible."
            )


        item.cantidad = cantidad


        item.save()


        CarritoService.recalcular(
            carrito
        )


        return carrito

    # =====================================================
    # FINALIZAR CARRITO
    # =====================================================
    @staticmethod
    @transaction.atomic
    def finalizar(
        carrito,
        turno,
        usuario,
        pagos=None,
    ):
        from apps.sales.models import Venta, VentaItem

        pagos = pagos or {}

        carrito = (
            Carrito.objects.select_for_update()
            .prefetch_related("items")
            .get(pk=carrito.pk)
        )

        if carrito.estado != "BORRADOR":
            raise ValidationError("El carrito ya fue procesado.")

        if not carrito.items.exists():
            raise ValidationError("Carrito vacío.")

        if turno.sucursal_id != carrito.sucursal_id:
            raise ValidationError(
                "El turno de caja no pertenece a la sucursal del carrito."
            )

        venta = Venta.objects.create(
            sucursal=carrito.sucursal,
            turno=turno,
            usuario=usuario,
            cliente=carrito.cliente,
            observaciones=carrito.observaciones,
            tipo_venta=carrito.tipo_venta,
            monto_efectivo=Decimal(str(pagos.get("EFECTIVO", 0) or 0)),
            monto_tarjeta=Decimal(str(pagos.get("TARJETA", 0) or 0)),
            monto_transferencia=Decimal(
                str(pagos.get("TRANSFERENCIA", 0) or 0)
            ),
        )

        for item in carrito.items.select_related(
            "variante",
            "variante__producto_base",
            "variante__color",
            "variante__talla",
            "variante__tipo_tela",
        ):
            VentaItem.objects.create(
                venta=venta,
                variante=item.variante,
                nombre_producto=item.variante.producto_base.nombre,
                sku=item.variante.sku,
                color=item.variante.color.nombre if item.variante.color else "",
                talla=item.variante.talla.nombre if item.variante.talla else "",
                tipo_tela=(
                    item.variante.tipo_tela.nombre
                    if item.variante.tipo_tela
                    else ""
                ),
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
            )

        venta.recalcular_totales()

        if venta.total_pagado < venta.total:
            raise ValidationError("Pago insuficiente.")

        venta.cerrar_venta()

        carrito.estado = "FINALIZADO"
        carrito.save(update_fields=["estado", "actualizado"])

        return venta