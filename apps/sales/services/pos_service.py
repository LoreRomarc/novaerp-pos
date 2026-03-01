# apps/sales/services/pos_service.py
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.utils import timezone

from apps.sales.models import (
    Venta,
    VentaItem,
    ListaPrecio,
    PrecioProducto,
    redondear_peso,
)
from apps.inventory.models import MovimientoStock, Producto, Stock
from apps.sales.services.serializers import serializar_venta
from .stock_service import StockService
from .caja_service import CajaService


class POSService:

    # ======================================================
    # OBTENER VENTA ABIERTA
    # ======================================================

    @staticmethod
    def obtener_venta_abierta(usuario, sucursal):
        return Venta.objects.filter(
            usuario=usuario,
            sucursal=sucursal,
            estado="ABIERTA"
        ).first()

    # ======================================================
    # CREAR U OBTENER VENTA
    # ======================================================

    @staticmethod
    @transaction.atomic
    def obtener_o_crear_venta(usuario, sucursal):

        venta = (
            Venta.objects
            .select_for_update()
            .filter(usuario=usuario, sucursal=sucursal, estado="ABIERTA")
            .first()
        )

        if venta:
            return venta

        turno = CajaService.obtener_turno_abierto(sucursal)

        if not turno:
            raise ValidationError("Debe abrir caja antes de vender.")

        return Venta.objects.create(
            sucursal=sucursal,
            turno=turno,
            usuario=usuario
        )

    # ======================================================
    # OBTENER PRECIO DESDE LISTA
    # ======================================================

    @staticmethod
    def obtener_precio_producto(producto, venta):

        lista = ListaPrecio.objects.filter(
            sucursal=venta.sucursal,
            tipo_venta=venta.tipo_venta,
            activa=True
        ).first()

        if not lista:
            raise ValidationError("No existe lista de precios configurada.")

        precio_obj = PrecioProducto.objects.filter(
            producto=producto,
            lista=lista
        ).first()

        if not precio_obj:
            raise ValidationError(
                f"El producto '{producto.nombre}' no tiene precio configurado."
            )

        return precio_obj.precio

    # ======================================================
    # AGREGAR PRODUCTO
    # ======================================================

    @staticmethod
    @transaction.atomic
    def agregar_producto(usuario, sucursal, producto_id=None, termino=None, cantidad=Decimal("1")):

        if cantidad <= 0:
            raise ValidationError("Cantidad inválida.")

        if producto_id:
            producto = Producto.objects.filter(id=producto_id, activo=True).first()
        else:
            producto = Producto.objects.filter(
                Q(codigo_barras__iexact=termino) |
                Q(nombre__icontains=termino),
                activo=True
            ).first()

        if not producto:
            raise ValidationError("Producto no encontrado.")

        venta = POSService.obtener_o_crear_venta(usuario, sucursal)

        precio = POSService.obtener_precio_producto(producto, venta)

        item = VentaItem.objects.filter(
            venta=venta,
            producto=producto
        ).first()

        nueva_cantidad = cantidad + (item.cantidad if item else 0)

        if producto.controla_stock:
            StockService.validar_stock_disponible(
                producto,
                sucursal,
                nueva_cantidad
            )

        if item:
            item.cantidad = nueva_cantidad
            item.precio_unitario = precio
            item.save()
        else:
            VentaItem.objects.create(
                venta=venta,
                producto=producto,
                cantidad=nueva_cantidad,
                precio_unitario=precio,
            )

        venta.recalcular_totales()

        return serializar_venta(venta)

    # ======================================================
    # ACTUALIZAR CANTIDAD
    # ======================================================

    @staticmethod
    @transaction.atomic
    def actualizar_cantidad(usuario, sucursal, item_id, cantidad):

        venta = POSService.obtener_venta_abierta(usuario, sucursal)

        if not venta:
            raise ValidationError("No hay venta activa.")

        item = VentaItem.objects.select_for_update().filter(
            id=item_id,
            venta=venta
        ).first()

        if not item:
            raise ValidationError("Item no encontrado.")

        # Si es 0 o menor → eliminar
        if cantidad <= 0:
            item.delete()

            if not venta.items.exists():
                venta.subtotal = 0
                venta.total_iva = 0
                venta.total = 0
                venta.save(update_fields=["subtotal", "total_iva", "total"])
                return serializar_venta(venta)

            venta.recalcular_totales()
            return serializar_venta(venta)

        # Validar stock
        if item.producto.controla_stock:
            StockService.validar_stock_disponible(
                item.producto,
                sucursal,
                cantidad
            )

        item.cantidad = cantidad
        item.save()

        venta.recalcular_totales()

        return serializar_venta(venta)

    # ======================================================
    # ELIMINAR ITEM
    # ======================================================

    @staticmethod
    @transaction.atomic
    def eliminar_item(usuario, sucursal, item_id):

        venta = POSService.obtener_venta_abierta(usuario, sucursal)

        if not venta:
            raise ValidationError("No hay venta activa.")

        item = VentaItem.objects.select_for_update().filter(
            id=item_id,
            venta=venta
        ).first()

        if not item:
            raise ValidationError("Item no encontrado.")

        item.delete()

        if not venta.items.exists():
            venta.subtotal = 0
            venta.total_iva = 0
            venta.total = 0
            venta.save(update_fields=["subtotal", "total_iva", "total"])
            return serializar_venta(venta)

        venta.recalcular_totales()

        return serializar_venta(venta)

    # ======================================================
    # CANCELAR VENTA
    # ======================================================

    @staticmethod
    @transaction.atomic
    def cancelar_venta(usuario, sucursal):

        venta = POSService.obtener_venta_abierta(usuario, sucursal)

        if venta:
            venta.delete()

        return True

    # ======================================================
    # CERRAR VENTA
    # ======================================================

    @staticmethod
    @transaction.atomic
    def cerrar_venta(usuario, sucursal, pagos: dict):
        """
        Cierra la venta ABIERTA del usuario en la sucursal.

        Args:
            usuario: User que cierra la venta
            sucursal: Sucursal donde se realiza la venta
            pagos: dict con montos {'EFECTIVO': 0, 'TARJETA':0, 'TRANSFERENCIA':0}
        """
        try:
            venta = Venta.objects.select_for_update().get(
                usuario=usuario,
                sucursal=sucursal,
                estado="ABIERTA"
            )
        except Venta.DoesNotExist:
            raise ValidationError("No hay una venta abierta para este usuario.")

        # Actualizar pagos
        venta.monto_efectivo = Decimal(pagos.get("EFECTIVO", 0))
        venta.monto_tarjeta = Decimal(pagos.get("TARJETA", 0))
        venta.monto_transferencia = Decimal(pagos.get("TRANSFERENCIA", 0))

        if not venta.puede_cerrar():
            raise ValidationError("El pago no cubre el total.")

        # Redondeo si es solo efectivo
        total_original = venta.total
        ajuste = Decimal("0.00")

        if venta.monto_efectivo > 0 and venta.monto_tarjeta == 0 and venta.monto_transferencia == 0:
            total_redondeado = redondear_peso(total_original)
            ajuste = total_redondeado - total_original
            venta.total = total_redondeado

        venta.ajuste_redondeo = ajuste

        # Descuento stock
        for item in venta.items.select_related("producto").select_for_update():
            if item.producto.controla_stock:
                stock = Stock.objects.select_for_update().get(
                    producto=item.producto,
                    sucursal=venta.sucursal
                )

                if stock.cantidad < item.cantidad:
                    raise ValidationError(f"Stock insuficiente para {item.producto.nombre}")

                stock.cantidad -= item.cantidad
                stock.save(update_fields=["cantidad"])

                MovimientoStock.objects.create(
                    producto=item.producto,
                    sucursal=venta.sucursal,
                    tipo="VENTA",
                    cantidad=item.cantidad,
                    referencia=venta.id
                )

        # Cerrar venta
        venta.estado = "CERRADA"
        venta.cerrada = timezone.now()
        venta.save(update_fields=[
            "estado", "cerrada", "total", "ajuste_redondeo",
            "monto_efectivo", "monto_tarjeta", "monto_transferencia"
        ])

        return venta

    # ======================================================
    # CAMBIAR TIPO
    # ======================================================

    @staticmethod
    @transaction.atomic
    def cambiar_tipo_venta(usuario, sucursal, tipo):

        if tipo not in ["DETAL", "MAYORISTA"]:
            raise ValidationError("Tipo inválido.")

        venta = POSService.obtener_venta_abierta(usuario, sucursal)

        if not venta:
            raise ValidationError("No hay venta activa.")

        venta.tipo_venta = tipo
        venta.save(update_fields=["tipo_venta"])

        for item in venta.items.select_related("producto"):
            nuevo_precio = POSService.obtener_precio_producto(
                item.producto,
                venta
            )
            item.precio_unitario = nuevo_precio
            item.save(update_fields=["precio_unitario"])

        venta.recalcular_totales()

        return serializar_venta(venta)