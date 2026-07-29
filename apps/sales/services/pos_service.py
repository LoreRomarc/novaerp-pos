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
from apps.inventory.models import ProductoVariante, Stock
from apps.inventory.services.stock_service import InventoryService
from apps.sales.services.serializers import serializar_venta
from .caja_service import CajaService


class POSService:

    # =========================
    # OBTENER VENTA ABIERTA
    # =========================
    @staticmethod
    def obtener_venta_abierta(usuario, sucursal, venta_uuid=None):

        if not venta_uuid:
            return None

        return Venta.objects.filter(
            uuid=venta_uuid,
            usuario=usuario,
            sucursal=sucursal,
            estado="ABIERTA"
        ).first()


    # =========================
    # CREAR OBTENER VENTA
    # =========================
    @staticmethod
    @transaction.atomic
    def obtener_o_crear_venta(usuario, sucursal, venta_uuid=None):

        venta = None

        if venta_uuid:

            venta = (
                Venta.objects
                .select_for_update()
                .filter(
                    uuid=venta_uuid,
                    usuario=usuario,
                    sucursal=sucursal,
                    estado="ABIERTA"
                )
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


    # =========================
    # CREAR NUEVA VENTA REAL
    # =========================
    @staticmethod
    @transaction.atomic
    def crear_nueva_venta(usuario, sucursal):

        turno = CajaService.obtener_turno_abierto(
            sucursal
        )

        if not turno:
            raise ValidationError(
                "Debe abrir caja antes de vender."
            )


        return Venta.objects.create(
            sucursal=sucursal,
            turno=turno,
            usuario=usuario,
            estado="ABIERTA"
        )

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

        if not lista:
            lista = ListaPrecio.objects.filter(
                sucursal=venta.sucursal,
                tipo_venta="DETAL",
                activa=True
            ).first()

        if not lista:
            raise ValidationError("No existe lista de precios configurada.")

        precio_obj = PrecioVariante.objects.filter(
            variante=variante,
            lista=lista
        ).first()

        if not precio_obj:
            raise ValidationError(f"Sin precio para {variante}")

        return precio_obj.precio

    # =========================
    # BUSCAR VARIANTE
    # =========================
    @staticmethod
    def buscar_variante(variante_id=None, termino=None, sucursal_id=None):

        qs = ProductoVariante.objects.select_related(
            "producto_base", "color", "tipo_tela"
        )

        if variante_id:
            qs = qs.filter(id=variante_id)

        elif termino:
            qs = qs.filter(
                Q(sku__iexact=termino) |
                Q(codigo_barras__iexact=termino) |
                Q(producto_base__nombre__icontains=termino) |
                Q(talla__icontains=termino) |
                Q(color__nombre__icontains=termino) |
                Q(tipo_tela__nombre__icontains=termino)
            )
        else:
            return None

        if sucursal_id:
            qs = qs.filter(
                stocks__sucursal_id=sucursal_id,
                stocks__cantidad__gt=0
            )

        return qs.first()

    # =========================
    # VALIDAR STOCK (LOCK REAL)
    # =========================
    @staticmethod
    def validar_stock_disponible(variante, cantidad, sucursal_id):

        stock = (
            Stock.objects
            .select_for_update()
            .filter(variante=variante, sucursal_id=sucursal_id)
            .first()
        )

        if not stock or stock.cantidad < cantidad:
            raise ValidationError(
                f"Stock insuficiente de {variante}. Disponible: {stock.cantidad if stock else 0}"
            )

    # =========================
    # AGREGAR PRODUCTO
    # =========================
    @staticmethod
    @transaction.atomic
    def agregar_producto(usuario,sucursal, variante_id=None, termino=None, cantidad=Decimal("1"), venta_uuid=None):

        if cantidad is None:
            cantidad = Decimal("1")

        cantidad = Decimal(str(cantidad))

        if cantidad <= 0:
            raise ValidationError("Cantidad inválida.")

        variante = POSService.buscar_variante(variante_id, termino, sucursal.id)

        if not variante:
            raise ValidationError("Producto no encontrado.")

        venta = POSService.obtener_o_crear_venta(usuario, sucursal, venta_uuid)

        precio = POSService.obtener_precio_variante(variante, venta)

        item = VentaItem.objects.filter(
            venta=venta,
            variante=variante
        ).first()

        nueva_cantidad = cantidad + (item.cantidad if item else 0)

        POSService.validar_stock_disponible(variante, nueva_cantidad, sucursal.id)

        if item:
            item.cantidad = nueva_cantidad
            item.precio_unitario = precio
            item.save()
        else:
            VentaItem.objects.create(
                venta=venta,
                variante=variante,
                cantidad=cantidad,
                precio_unitario=precio
            )

        venta.recalcular_totales()

        return serializar_venta(venta)

    # =========================
    # CERRAR VENTA (CORE)
    # =========================
    @staticmethod
    @transaction.atomic
    def cerrar_venta(usuario, sucursal, pagos: dict, cliente="", observaciones="", venta_uuid=None):
  
        if not venta_uuid:
            raise ValidationError(
                "UUID de venta requerido."
            )


        venta = (
            Venta.objects
            .select_for_update()
            .filter(
                uuid=venta_uuid,
                usuario=usuario,
                sucursal=sucursal,
                estado="ABIERTA"
            )
            .first()
        )

        if not venta:
            raise ValidationError("No hay venta abierta.")

        venta.monto_efectivo = Decimal(pagos.get("EFECTIVO", 0))
        venta.monto_tarjeta = Decimal(pagos.get("TARJETA", 0))
        venta.monto_transferencia = Decimal(pagos.get("TRANSFERENCIA", 0))
        venta.cliente = cliente
        venta.observaciones = observaciones


        if not venta.puede_cerrar():
            raise ValidationError("Pago insuficiente.")

        total_original = venta.total
        ajuste = Decimal("0.00")

        if venta.monto_efectivo > 0 and venta.monto_tarjeta == 0:
            total_redondeado = redondear_a_peso_colombiano(total_original)
            ajuste = total_redondeado - total_original
            venta.total = total_redondeado

        venta.ajuste_redondeo = ajuste

        # DESCUENTO DE STOCK CENTRALIZADO + USER
        for item in venta.items.select_related("variante").select_for_update():

            InventoryService.descontar_stock(
                variante=item.variante,
                cantidad=item.cantidad,
                user=usuario,
                sucursal_id=sucursal.id,
                referencia=f"Venta {venta.id}",
                tipo="VENTA"
            )

        #  MOVIMIENTOS FINANCIEROS
        CajaService.registrar_movimientos_venta(
            venta,
            usuario,
            pagos
        )


        venta.estado = "CERRADA"
        venta.cerrada = timezone.now()

        venta.save(update_fields=[
            "estado", "cerrada",
            "total", "ajuste_redondeo",
            "monto_efectivo", "monto_tarjeta", "monto_transferencia",
            "cliente", "observaciones"
        ])

        return venta
    

    # =========================
    # ELIMINAR ITEM (FIX REAL)
    # =========================
    @staticmethod
    @transaction.atomic
    def eliminar_item(usuario, sucursal, item_id, venta_uuid=None):

        venta = POSService.obtener_venta_abierta(
            usuario,
            sucursal,
            venta_uuid
        )

        if not venta:
            raise ValidationError("No hay venta activa.")

        item = (
            venta.items
            .select_for_update()
            .filter(id=item_id)
            .first()
        )

        if not item:
            raise ValidationError("Item no encontrado.")

        item.delete()

        # Si ya no quedan productos, eliminar completamente la venta
        if not venta.items.exists():

            venta.delete()

            return {
                "id": None,
                "uuid": None,
                "estado": None,
                "tipo_venta": "DETAL",
                "cliente": "",
                "observaciones": "",
                "efectivo": "0",
                "transferencia": "0",
                "tarjeta": "0",
                "subtotal": "0",
                "iva": "0",
                "total": "0",
                "items": [],
            }

        venta.recalcular_totales()

        return serializar_venta(venta)


    # =========================
    # ACTUALIZAR CANTIDAD / PRECIO
    # =========================
    @staticmethod
    @transaction.atomic
    def actualizar_cantidad(usuario, sucursal, item_id, cantidad=None, precio_unitario=None, venta_uuid=None):

        venta = POSService.obtener_venta_abierta(usuario, sucursal, venta_uuid)

        if not venta:
            raise ValidationError("No hay venta abierta")

        item = venta.items.select_for_update().filter(id=item_id).first()

        if not item:
            raise ValidationError("Item no encontrado")

        # actualizar cantidad
        if cantidad is not None:
            if cantidad <= 0:
                item.delete()
                venta.recalcular_totales()
                return serializar_venta(venta)

            POSService.validar_stock_disponible(
                item.variante,
                cantidad,
                sucursal.id
            )

            item.cantidad = cantidad

        # actualizar precio manual
        if precio_unitario is not None:
            if precio_unitario <= 0:
                raise ValidationError("Precio inválido")

            item.precio_unitario = Decimal(precio_unitario)

        item.save()

        venta.recalcular_totales()

        return serializar_venta(venta)

    # =========================
    # CAMBIAR TIPO DE VENTA
    # =========================
    @staticmethod
    @transaction.atomic
    def cambiar_tipo_venta(usuario, sucursal, tipo, venta_uuid=None):

        if tipo not in ["DETAL", "MAYORISTA"]:
            raise ValidationError("Tipo de venta inválido.")

        venta = POSService.obtener_o_crear_venta(
            usuario=usuario,
            sucursal=sucursal,
            venta_uuid=venta_uuid
        )

        venta.tipo_venta = tipo
        venta.save(update_fields=["tipo_venta"])

        for item in venta.items.select_related("variante"):

            item.precio_unitario = POSService.obtener_precio_variante(
                item.variante,
                venta
            )

            item.save(update_fields=["precio_unitario"])

        venta.recalcular_totales()

        return serializar_venta(venta)


    # =========================
    # CANCELAR VENTA
    # =========================

    @staticmethod
    @transaction.atomic
    def cancelar_venta(
        usuario,
        sucursal,
        venta_uuid=None
    ):

        if not venta_uuid:
            raise ValidationError("UUID requerido.")

        venta = (
            Venta.objects
            .select_for_update()
            .filter(
                uuid=venta_uuid,
                usuario=usuario,
                sucursal=sucursal,
                estado="ABIERTA"
            )
            .first()
        )

        if not venta:
            raise ValidationError("Venta abierta no encontrada.")

        # Elimina también todos los VentaItem (CASCADE)
        venta.delete()

        return True


    @staticmethod
    @transaction.atomic
    def guardar_estado(
        usuario,
        sucursal,
        venta_uuid,
        cliente,
        observaciones,
        efectivo,
        transferencia,
        tarjeta,
    ):

        venta = POSService.obtener_venta_abierta(
            usuario,
            sucursal,
            venta_uuid
        )

        if not venta:
            raise ValidationError("Venta no encontrada")

        venta.cliente = cliente
        venta.observaciones = observaciones

        venta.monto_efectivo = Decimal(str(efectivo or 0))
        venta.monto_transferencia = Decimal(str(transferencia or 0))
        venta.monto_tarjeta = Decimal(str(tarjeta or 0))

        venta.save()

        return serializar_venta(venta)