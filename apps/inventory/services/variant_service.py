# apps/inventory/services/variant_service.py
from django.db import transaction
from django.core.exceptions import ValidationError

from apps.inventory.models import (
    ProductoVariante,
    Talla,
    TipoTela,
    Color,
)


class VariantService:

    @staticmethod
    def generar_sku(producto_base, tipo_tela, color, talla):
        return (
            f"{producto_base.nombre[:3]}"
            f"-{tipo_tela.nombre[:3]}"
            f"-{color.nombre[:3]}"
            f"-{talla.nombre}"
        ).upper()

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

        sku = VariantService.generar_sku(
            producto_base,
            tipo_tela,
            color,
            talla,
        )

        return ProductoVariante.objects.create(
            producto_base=producto_base,
            tipo_tela=tipo_tela,
            color=color,
            talla=talla,
            sku=sku,
            activo=True,
            precio_venta=0,
            costo_unitario=0,
            stock_minimo=0,
        )