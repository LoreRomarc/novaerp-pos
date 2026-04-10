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
    PrecioVariante,
    redondear_a_peso_colombiano,
)
from apps.inventory.models import ProductoVariante
from apps.inventory.services.stock_service import InventoryService
from apps.sales.services.serializers import serializar_venta
from .caja_service import CajaService


class POSService:

    # =========================
    # OBTENER VENTA ABIERTA
    # =========================
    @staticmethod
    def obtener_venta_abierta(usuario, sucursal):
        return Venta.objects.filter(usuario=usuario, sucursal=sucursal, estado="ABIERTA").first()

    # =========================
    # CREAR OBTENER VENTA
    # =========================
    @staticmethod
    @transaction.atomic
    def obtener_o_crear_venta(usuario, sucursal):
        venta = Venta.objects.select_for_update().filter(usuario=usuario, sucursal=sucursal, estado="ABIERTA").first()
        if venta:
            return venta

        turno = CajaService.obtener_turno_abierto(sucursal)
        if not turno:
            raise ValidationError("Debe abrir caja antes de vender.")

        return Venta.objects.create(sucursal=sucursal, turno=turno, usuario=usuario)

    # =========================
    # PRECIO POR VARIANTE
    # =========================
    @staticmethod
    def obtener_precio_variante(variante, venta):
        lista = ListaPrecio.objects.filter(
            sucursal=venta.sucursal,
            tipo_venta=venta.tipo_venta,
            activa=True
        ).first()

        # fallback a DETAL si no existe lista
        if not lista:
            lista = ListaPrecio.objects.filter(
                sucursal=venta.sucursal,
                tipo_venta="DETAL",
                activa=True
            ).first()

        if not lista:
            raise ValidationError("No existe lista de precios configurada (ni DETAL fallback).")

        precio_obj = PrecioVariante.objects.filter(
            variante=variante,
            lista=lista
        ).first()

        if not precio_obj:
            raise ValidationError(
                f"No hay precio configurado para {variante} en lista {lista.id}"
            )

        return precio_obj.precio

    # =========================
    # BUSCAR VARIANTE
    # =========================
    @staticmethod
    def buscar_variante(variante_id=None, termino=None, sucursal_id=None):
        """
        Busca la variante por id o término (nombre, SKU, talla, color, tipo de tela).
        Opcional: filtra por stock en sucursal si sucursal_id se pasa.
        """
        qs = ProductoVariante.objects.select_related("producto_base", "color", "tipo_tela")
        
        if variante_id:
            qs = qs.filter(id=variante_id)
        elif termino:
            qs = qs.filter(
                Q(sku__iexact=termino) |
                Q(producto_base__nombre__icontains=termino) |
                Q(talla__icontains=termino) |
                Q(color__nombre__icontains=termino) |
                Q(tipo_tela__nombre__icontains=termino)
            )
        else:
            return None

        if sucursal_id:
            qs = qs.filter(stocks__sucursal_id=sucursal_id, stocks__cantidad__gt=0)

        return qs.first()

    # =========================
    # VALIDAR STOCK
    # =========================
    @staticmethod
    def validar_stock_disponible(variante, cantidad, sucursal_id):
        stock = variante.stocks.filter(sucursal_id=sucursal_id).first()
        if not stock or stock.cantidad < cantidad:
            raise ValidationError(f"No hay suficiente stock de {variante}. Disponible: {stock.cantidad if stock else 0}")

    # =========================
    # AGREGAR PRODUCTO
    # =========================
    @staticmethod
    @transaction.atomic
    def agregar_producto(usuario, sucursal, variante_id=None, termino=None, cantidad=Decimal("1")):
        if cantidad <= 0:
            raise ValidationError("Cantidad inválida.")

        variante = POSService.buscar_variante(variante_id, termino, sucursal.id)
        if not variante:
            raise ValidationError("Producto no encontrado o sin stock disponible.")

        venta = POSService.obtener_o_crear_venta(usuario, sucursal)
        precio = POSService.obtener_precio_variante(variante, venta)

        item = VentaItem.objects.filter(venta=venta, variante=variante).first()
        nueva_cantidad = cantidad + (item.cantidad if item else 0)

        POSService.validar_stock_disponible(variante, nueva_cantidad, sucursal.id)

        if item:
            item.cantidad = nueva_cantidad
            item.precio_unitario = precio
            item.save()
        else:
            VentaItem.objects.create(venta=venta, variante=variante, cantidad=nueva_cantidad, precio_unitario=precio)

        venta.recalcular_totales()
        return serializar_venta(venta)

    # =========================
    # ACTUALIZAR CANTIDAD
    # =========================
    @staticmethod
    @transaction.atomic
    def actualizar_cantidad(usuario, sucursal, item_id, cantidad):
        venta = POSService.obtener_venta_abierta(usuario, sucursal)
        if not venta:
            raise ValidationError("No hay venta activa.")

        item = VentaItem.objects.select_for_update().filter(id=item_id, venta=venta).first()
        if not item:
            raise ValidationError("Item no encontrado.")

        if cantidad <= 0:
            item.delete()
            if not venta.items.exists():
                venta.subtotal = venta.total_iva = venta.total = 0
                venta.save(update_fields=["subtotal", "total_iva", "total"])
                return serializar_venta(venta)
            venta.recalcular_totales()
            return serializar_venta(venta)

        POSService.validar_stock_disponible(item.variante, cantidad, sucursal.id)
        item.cantidad = cantidad
        item.save()
        venta.recalcular_totales()
        return serializar_venta(venta)

    # =========================
    # ELIMINAR ITEM
    # =========================
    @staticmethod
    @transaction.atomic
    def eliminar_item(usuario, sucursal, item_id):
        venta = POSService.obtener_venta_abierta(usuario, sucursal)
        if not venta:
            raise ValidationError("No hay venta activa.")

        item = VentaItem.objects.select_for_update().filter(id=item_id, venta=venta).first()
        if not item:
            raise ValidationError("Item no encontrado.")

        item.delete()
        if not venta.items.exists():
            venta.subtotal = venta.total_iva = venta.total = 0
            venta.save(update_fields=["subtotal", "total_iva", "total"])
            return serializar_venta(venta)

        venta.recalcular_totales()
        return serializar_venta(venta)

    # =========================
    # CANCELAR VENTA
    # =========================
    @staticmethod
    @transaction.atomic
    def cancelar_venta(usuario, sucursal):
        venta = POSService.obtener_venta_abierta(usuario, sucursal)
        if venta:
            venta.delete()
        return True

    # =========================
    # CERRAR VENTA
    # =========================
    @staticmethod
    @transaction.atomic
    def cerrar_venta(usuario, sucursal, pagos: dict):
        venta = Venta.objects.select_for_update().filter(usuario=usuario, sucursal=sucursal, estado="ABIERTA").first()
        if not venta:
            raise ValidationError("No hay una venta abierta.")

        venta.monto_efectivo = Decimal(pagos.get("EFECTIVO", 0))
        venta.monto_tarjeta = Decimal(pagos.get("TARJETA", 0))
        venta.monto_transferencia = Decimal(pagos.get("TRANSFERENCIA", 0))

        if not venta.puede_cerrar():
            raise ValidationError("El pago no cubre el total.")

        total_original = venta.total
        ajuste = Decimal("0.00")
        if venta.monto_efectivo > 0 and venta.monto_tarjeta == 0 and venta.monto_transferencia == 0:
            total_redondeado = redondear_a_peso_colombiano(total_original)
            ajuste = total_redondeado - total_original
            venta.total = total_redondeado
        venta.ajuste_redondeo = ajuste

        for item in venta.items.select_related("variante").select_for_update():
            POSService.validar_stock_disponible(item.variante, item.cantidad, sucursal.id)
            InventoryService.descontar_stock(item.variante, item.cantidad, sucursal.id, referencia=venta.id, tipo="VENTA")

        CajaService.registrar_movimientos_venta(venta, usuario, pagos)

        venta.estado = "CERRADA"
        venta.cerrada = timezone.now()
        venta.save(update_fields=[
            "estado", "cerrada", "total", "ajuste_redondeo",
            "monto_efectivo", "monto_tarjeta", "monto_transferencia"
        ])

        return venta

    # =========================
    # CAMBIAR TIPO DE VENTA
    # =========================

    @staticmethod
    @transaction.atomic
    def cambiar_tipo_venta(usuario, sucursal, tipo):
        if tipo not in ["DETAL", "MAYORISTA"]:
            raise ValidationError("Tipo inválido.")

        venta = POSService.obtener_o_crear_venta(usuario, sucursal)

        venta.tipo_venta = tipo
        venta.save(update_fields=["tipo_venta"])

        for item in venta.items.select_related("variante"):
            nuevo_precio = POSService.obtener_precio_variante(item.variante, venta)
            item.precio_unitario = nuevo_precio
            item.save(update_fields=["precio_unitario"])

        venta.recalcular_totales()
        return serializar_venta(venta)