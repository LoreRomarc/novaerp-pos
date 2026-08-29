# apps/sales/services/devolucion_service.py
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.inventory.models import ProductoVariante
from apps.inventory.services.stock_service import InventoryService
from apps.sales.models import (
    CambioDetalle,
    Devolucion,
    DevolucionDetalle,
    ListaPrecio,
    PrecioVariante,
    Venta,
    redondear_a_peso_colombiano,
)
from apps.sales.models_caja_enterprise import CajaMovimiento
from apps.sales.services.caja_service import CajaService


class DevolucionService:
    """
    Cambios y devoluciones directas.

    No requiere venta original. Si se indica venta_id, solo se guarda
    como referencia de auditoría.
    """

    MEDIOS_PAGO = {
        CajaMovimiento.MedioPago.EFECTIVO,
        CajaMovimiento.MedioPago.TARJETA,
        CajaMovimiento.MedioPago.TRANSFERENCIA,
    }

    ROLES_PUEDEN_MODIFICAR_PRECIO = {
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "SUPERVISOR",
    }

    @staticmethod
    def _decimal(valor, mensaje):
        try:
            monto = Decimal(
                str(valor if valor not in (None, "") else "0")
            )
        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as error:
            raise ValidationError(mensaje) from error

        if not monto.is_finite():
            raise ValidationError(mensaje)

        return monto

    @staticmethod
    def _cantidad(valor):
        cantidad = DevolucionService._decimal(
            valor,
            "La cantidad es inválida.",
        )

        if cantidad <= 0:
            raise ValidationError(
                "La cantidad debe ser mayor a cero."
            )

        if cantidad % 1 != 0:
            raise ValidationError(
                "La cantidad de prendas debe ser un número entero."
            )

        return cantidad

    @staticmethod
    def _usuario_puede_modificar_precio(usuario):
        perfil = getattr(usuario, "profile", None)

        return bool(
            perfil
            and perfil.role
            in DevolucionService.ROLES_PUEDEN_MODIFICAR_PRECIO
        )

    @staticmethod
    def _obtener_venta(venta_id, sucursal):
        if not venta_id:
            return None

        venta = (
            Venta.objects
            .select_for_update()
            .filter(
                pk=venta_id,
                sucursal=sucursal,
            )
            .first()
        )

        if not venta:
            raise ValidationError(
                "La venta de referencia no existe "
                "o pertenece a otra sucursal."
            )

        return venta

    @staticmethod
    def _obtener_lista_precios(sucursal, tipo_venta):
        if tipo_venta not in {
            "DETAL",
            "MAYORISTA",
        }:
            raise ValidationError(
                "El tipo de venta es inválido."
            )

        lista = (
            ListaPrecio.objects
            .filter(
                sucursal=sucursal,
                tipo_venta=tipo_venta,
                activa=True,
            )
            .order_by("id")
            .first()
        )

        if not lista:
            raise ValidationError(
                "No existe una lista de precios activa "
                "para esta sucursal."
            )

        return lista

    @staticmethod
    def _normalizar_pagos(pagos):
        pagos = pagos or {}

        if not isinstance(pagos, dict):
            raise ValidationError(
                "Los pagos adicionales son inválidos."
            )

        medios_invalidos = (
            set(pagos.keys())
            - DevolucionService.MEDIOS_PAGO
        )

        if medios_invalidos:
            raise ValidationError(
                "Hay medios de pago no permitidos."
            )

        pagos_limpios = {}

        for medio in DevolucionService.MEDIOS_PAGO:
            monto = DevolucionService._decimal(
                pagos.get(medio, 0),
                f"El monto de {medio} es inválido.",
            )

            if monto < 0:
                raise ValidationError(
                    "Los pagos no pueden ser negativos."
                )

            pagos_limpios[medio] = monto

        return pagos_limpios

    @staticmethod
    def _obtener_variantes_y_precios(
        *,
        lista,
        datos,
        exigir_activo,
        nombre_operacion,
    ):
        """
        Recibe una lista con variante_id y cantidad.
        Devuelve variantes, cantidades y precio vigente.
        """

        if not isinstance(datos, list):
            raise ValidationError(
                f"Los productos de {nombre_operacion} son inválidos."
            )

        if not datos:
            return []

        cantidades_por_variante = {}

        for dato in datos:
            if not isinstance(dato, dict):
                raise ValidationError(
                    f"Un producto de {nombre_operacion} es inválido."
                )

            try:
                variante_id = int(dato.get("variante_id"))
            except (TypeError, ValueError) as error:
                raise ValidationError(
                    f"Debe seleccionar un producto válido para "
                    f"{nombre_operacion}."
                ) from error

            if variante_id in cantidades_por_variante:
                raise ValidationError(
                    "No puede repetir el mismo producto "
                    "en una sola operación."
                )

            cantidades_por_variante[variante_id] = (
                DevolucionService._cantidad(
                    dato.get("cantidad")
                )
            )

        filtros = {
            "id__in": cantidades_por_variante.keys(),
        }

        if exigir_activo:
            filtros["activo"] = True

        variantes = {
            variante.id: variante
            for variante in (
                ProductoVariante.objects
                .filter(**filtros)
                .select_related(
                    "producto_base",
                    "tipo_tela",
                    "color",
                    "talla",
                )
            )
        }

        if len(variantes) != len(cantidades_por_variante):
            raise ValidationError(
                f"Uno de los productos de {nombre_operacion} "
                f"no existe o no está activo."
            )

        precios = {
            precio.variante_id: precio.precio
            for precio in PrecioVariante.objects.filter(
                lista=lista,
                variante_id__in=cantidades_por_variante.keys(),
            )
        }

        return [
            {
                "variante": variantes[variante_id],
                "cantidad": cantidad,
                "precio_lista": precios.get(variante_id),
                "dato_original": next(
                    dato
                    for dato in datos
                    if int(dato["variante_id"]) == variante_id
                ),
            }
            for variante_id, cantidad
            in cantidades_por_variante.items()
        ]

    @staticmethod
    def _resolver_precio(
        *,
        usuario,
        dato,
        precio_lista,
    ):
        precio_manual = dato.get("precio_unitario")
        motivo_precio = (dato.get("motivo_precio") or "").strip()

        if precio_manual in (None, ""):
            if precio_lista is None:
                raise ValidationError(
                    "El producto no tiene precio en la lista activa. "
                    "Un supervisor debe indicar el precio manual."
                )

            return precio_lista, False, ""

        precio_manual = DevolucionService._decimal(
            precio_manual,
            "El precio manual es inválido.",
        )

        if precio_manual <= 0:
            raise ValidationError(
                "El precio manual debe ser mayor a cero."
            )

        if precio_manual == precio_lista:
            return precio_lista, False, ""

        if not DevolucionService._usuario_puede_modificar_precio(
            usuario
        ):
            raise ValidationError(
                "No tiene permiso para modificar precios."
            )

        if not motivo_precio:
            raise ValidationError(
                "Indique el motivo de la modificación de precio."
            )

        return precio_manual, True, motivo_precio
    
    @staticmethod
    def _preparar_productos_recibidos(
        *,
        usuario,
        lista,
        productos,
    ):
        """
        La prenda recibida puede ser apta o dañada.
        El precio se toma de lista; administradores y supervisores
        pueden reconocer otro valor con motivo obligatorio.
        """

        preparados = DevolucionService._obtener_variantes_y_precios(
            lista=lista,
            datos=productos,
            exigir_activo=False,
            nombre_operacion="la devolución",
        )

        if not preparados:
            raise ValidationError(
                "Debe registrar al menos una prenda recibida."
            )

        for item in preparados:
            dato = item["dato_original"]

            estado_prenda = dato.get("estado_prenda")

            if estado_prenda not in {
                DevolucionDetalle.EstadoPrenda.APTA,
                DevolucionDetalle.EstadoPrenda.DANADA,
            }:
                raise ValidationError(
                    "Debe indicar si la prenda recibida "
                    "está apta o dañada."
                )

            precio_final, precio_modificado, motivo_precio = (
                DevolucionService._resolver_precio(
                    usuario=usuario,
                    dato=dato,
                    precio_lista=item["precio_lista"],
                )
            )

            item["estado_prenda"] = estado_prenda
            item["precio_unitario"] = precio_final
            item["precio_modificado"] = precio_modificado
            item["motivo_precio"] = motivo_precio
            item["total"] = redondear_a_peso_colombiano(
                precio_final * item["cantidad"]
            )

        return preparados

    @staticmethod
    def _preparar_productos_entregados(
        *,
        usuario,
        lista,
        productos,
    ):
        preparados = DevolucionService._obtener_variantes_y_precios(
            lista=lista,
            datos=productos,
            exigir_activo=True,
            nombre_operacion="el cambio",
        )

        for item in preparados:
            precio, precio_modificado, motivo_precio = (
                DevolucionService._resolver_precio(
                    usuario=usuario,
                    dato=item["dato_original"],
                    precio_lista=item["precio_lista"],
                )
            )

            item["precio_unitario"] = precio
            item["precio_modificado"] = precio_modificado
            item["motivo_precio"] = motivo_precio
            item["total"] = redondear_a_peso_colombiano(
                precio * item["cantidad"]
            )

        return preparados

    @staticmethod
    @transaction.atomic
    def procesar(
        *,
        usuario,
        sucursal,
        turno_id,
        productos_recibidos,
        productos_entregados=None,
        permite_reembolso=False,
        medio_reembolso="",
        pagos_adicionales=None,
        motivo="",
        venta_id=None,
        referencia_externa="",
        tipo_venta="MAYORISTA",
    ):
        """
        Procesa una devolución o cambio directo.

        Stock, kardex, caja y comprobante se revierten completamente
        si cualquier validación falla.
        """

        motivo = (motivo or "").strip()
        referencia_externa = (
            referencia_externa
            or ""
        ).strip()

        if not motivo:
            raise ValidationError(
                "El motivo de la operación es obligatorio."
            )

        if not turno_id:
            raise ValidationError(
                "Debe tener una caja abierta para procesar un cambio."
            )

        venta = DevolucionService._obtener_venta(
            venta_id,
            sucursal,
        )

        turno = CajaService.obtener_turno_bloqueado(
            turno_id,
            sucursal=sucursal,
        )

        CajaService.validar_operador_turno(
            turno,
            usuario,
        )

        lista = DevolucionService._obtener_lista_precios(
            sucursal,
            tipo_venta,
        )

        recibidos = (
            DevolucionService
            ._preparar_productos_recibidos(
                usuario=usuario,
                lista=lista,
                productos=productos_recibidos,
            )
        )

        entregados = (
            DevolucionService
            ._preparar_productos_entregados(
                usuario=usuario,
                lista=lista,
                productos=productos_entregados or [],
            )
        )

        total_devuelto = sum(
            (item["total"] for item in recibidos),
            Decimal("0.00"),
        )

        total_entregado = sum(
            (item["total"] for item in entregados),
            Decimal("0.00"),
        )

        diferencia = total_entregado - total_devuelto

        monto_cobrado = (
            diferencia
            if diferencia > 0
            else Decimal("0.00")
        )

        saldo_a_favor = (
            abs(diferencia)
            if diferencia < 0
            else Decimal("0.00")
        )

        monto_reembolsado = (
            saldo_a_favor
            if permite_reembolso
            else Decimal("0.00")
        )

        monto_no_reembolsado = (
            Decimal("0.00")
            if permite_reembolso
            else saldo_a_favor
        )

        pagos_adicionales = (
            DevolucionService._normalizar_pagos(
                pagos_adicionales
            )
        )

        # Una devolución o un cambio por igual valor no recibe dinero del
        # cliente. La interfaz puede conservar valores escritos antes de que
        # se cambien los productos, por lo que esos valores no deben bloquear
        # ni afectar una operación cuyo saldo a cobrar sea cero.
        if monto_cobrado == Decimal("0.00"):
            pagos_adicionales = {
                medio: Decimal("0.00")
                for medio in DevolucionService.MEDIOS_PAGO
            }

        total_pagos = sum(
            pagos_adicionales.values(),
            Decimal("0.00"),
        )

        if total_pagos != monto_cobrado:
            raise ValidationError(
                "El pago adicional no coincide con "
                "la diferencia del cambio."
            )

        if monto_reembolsado > 0:
            if medio_reembolso not in DevolucionService.MEDIOS_PAGO:
                raise ValidationError(
                    "Debe seleccionar el medio para el reembolso."
                )
        else:
            medio_reembolso = ""

        devolucion = Devolucion.objects.create(
            venta=venta,
            sucursal=sucursal,
            turno=turno,
            usuario=usuario,
            tipo=(
                Devolucion.Tipo.CAMBIO
                if entregados
                else Devolucion.Tipo.DEVOLUCION
            ),
            tipo_venta=tipo_venta,
            referencia_externa=referencia_externa,
            motivo=motivo,
            permite_reembolso=permite_reembolso,
            medio_reembolso=medio_reembolso,
            total_devuelto=total_devuelto,
            total_entregado=total_entregado,
            diferencia=diferencia,
            monto_cobrado=monto_cobrado,
            monto_reembolsado=monto_reembolsado,
            monto_no_reembolsado=monto_no_reembolsado,
        )

        referencia = f"CAMBIO-{devolucion.id}"

        # 1. Recibir prendas del cliente.
        for item in recibidos:
            DevolucionDetalle.objects.create(
                devolucion=devolucion,
                variante=item["variante"],
                cantidad=item["cantidad"],
                estado_prenda=item["estado_prenda"],
                precio_unitario=item["precio_unitario"],
                precio_modificado=item["precio_modificado"],
                motivo_precio=item["motivo_precio"],
                total=item["total"],
            )

            # Primero se registra la devolución.
            InventoryService.agregar_stock(
                variante=item["variante"],
                cantidad=item["cantidad"],
                user=usuario,
                sucursal_id=sucursal.id,
                referencia=referencia,
                tipo="DEVOLUCION_CLIENTE",
            )

            # Si está dañada, se da de baja inmediatamente.
            if (
                item["estado_prenda"]
                == DevolucionDetalle.EstadoPrenda.DANADA
            ):
                InventoryService.descontar_stock(
                    variante=item["variante"],
                    cantidad=item["cantidad"],
                    user=usuario,
                    sucursal_id=sucursal.id,
                    referencia=referencia,
                    tipo="DANADO",
                )

        # 2. Entregar prendas nuevas.
        for item in entregados:
            CambioDetalle.objects.create(
                devolucion=devolucion,
                variante=item["variante"],
                cantidad=item["cantidad"],
                precio_unitario=item["precio_unitario"],
                precio_modificado=item["precio_modificado"],
                motivo_precio=item["motivo_precio"],
                total=item["total"],
            )

            InventoryService.descontar_stock(
                variante=item["variante"],
                cantidad=item["cantidad"],
                user=usuario,
                sucursal_id=sucursal.id,
                referencia=referencia,
                tipo="VENTA",
            )

        # 3. Registrar excedente cobrado o dinero reembolsado.
        CajaService.registrar_movimientos_devolucion(
            devolucion=devolucion,
            turno=turno,
            usuario=usuario,
            pagos_adicionales=pagos_adicionales,
            medio_reembolso=medio_reembolso,
        )

        return devolucion


    
