# apps/sales/services/serializers.py
from decimal import Decimal


def _decimal(valor):
    return str(valor if valor is not None else Decimal("0.00"))


def _serializar_item(item, usar_snapshot=False):
    variante = item.variante

    if usar_snapshot:
        sku = item.sku
        nombre = item.nombre_producto
        color = item.color
        talla = item.talla
    else:
        sku = variante.sku
        nombre = variante.producto_base.nombre
        color = variante.color.nombre if variante.color else ""
        talla = variante.talla.nombre if variante.talla else ""

    return {
        "id": item.id,
        "variante_id": variante.id,
        "sku": sku,
        "nombre": nombre,
        "color": color,
        "talla": talla,
        "cantidad": _decimal(item.cantidad),
        "precio_unitario": _decimal(item.precio_unitario),
        "iva_linea": _decimal(item.iva_linea),
        "subtotal_linea": _decimal(item.subtotal_linea),
    }


def _obtener_items(documento):
    return list(
        documento.items.select_related(
            "variante",
            "variante__producto_base",
            "variante__color",
            "variante__talla",
        )
    )


def _calcular_totales(items):
    subtotal = sum(
        (item.subtotal_linea for item in items),
        Decimal("0.00"),
    )
    iva = sum(
        (item.iva_linea for item in items),
        Decimal("0.00"),
    )
    total = sum(
        (item.total_linea for item in items),
        Decimal("0.00"),
    )

    return subtotal, iva, total


def _serializar_documento(
    documento,
    *,
    identificador,
    usar_snapshot,
    usar_totales_guardados=False,
):
    items = _obtener_items(documento)

    if usar_totales_guardados:
        subtotal = documento.subtotal
        iva = documento.total_iva
        total = documento.total
    else:
        subtotal, iva, total = _calcular_totales(items)

    return {
        "id": identificador,
        "uuid": str(documento.uuid),
        "estado": documento.estado,
        "tipo_venta": documento.tipo_venta,
        "cliente": documento.cliente or "",
        "observaciones": documento.observaciones or "",
        "efectivo": _decimal(documento.monto_efectivo),
        "transferencia": _decimal(documento.monto_transferencia),
        "tarjeta": _decimal(documento.monto_tarjeta),
        "subtotal": _decimal(subtotal),
        "iva": _decimal(iva),
        "total": _decimal(total),
        "items": [
            _serializar_item(
                item,
                usar_snapshot=usar_snapshot,
            )
            for item in items
        ],
    }


def serializar_venta(venta):
    return _serializar_documento(
        venta,
        identificador=venta.id,
        usar_snapshot=True,
        usar_totales_guardados=True,
    )


def serializar_carrito(carrito):
    carrito.refresh_from_db()

    return _serializar_documento(
        carrito,
        identificador=None,
        usar_snapshot=False,
    )