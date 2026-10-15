# apps/inventory/services/variant_service.py
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import (
    ProductoVariante,
    Talla,
    TipoTela,
    Color,
    codigo_identificador,
)


class VariantService:

    @staticmethod
    def generar_sku(producto_base, tipo_tela, color, talla):
        return "-".join((
            codigo_identificador(producto_base.nombre, "producto", 8),
            codigo_identificador(tipo_tela.nombre, "tela", 8),
            codigo_identificador(color.nombre, "color", 5),
            codigo_identificador(talla.nombre, "talla", 4),
        ))

    @staticmethod
    @transaction.atomic
    def obtener_o_crear(
        producto_base,
        tipo_tela,
        color,
        talla_nombre,
    ):

        talla = Talla.objects.filter(
            nombre__iexact=talla_nombre.strip()
        ).first()

        if not talla:
            raise ValidationError(f"Talla no existe: {talla_nombre}")

        variante = (
            ProductoVariante.objects
            .select_for_update()
            .filter(
                producto_base=producto_base,
                tipo_tela=tipo_tela,
                color=color,
                talla=talla,
            )
            .first()
        )

        if variante:
            return variante

        return ProductoVariante.objects.create(
            producto_base=producto_base,
            tipo_tela=tipo_tela,
            color=color,
            talla=talla,
            # El modelo genera SKU y código de barras legibles y únicos.
            sku="",
            activo=True,
            precio_venta=0,
            costo_unitario=0,
            stock_minimo=0,
        )
