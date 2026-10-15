"""Corrige solamente los SKU automáticos generados con el formato anterior.

No se cambian SKU escritos manualmente: el patrón legado se reconstruye desde
los cuatro maestros y sólo se actualiza si coincide exactamente.
"""

import re

from django.db import migrations
from django.utils.text import slugify


CODIGOS_CONOCIDOS = {
    "producto": {
        "sueter": "STR",
        "short": "SHT",
    },
    "tela": {
        "lycra-algodon": "ALGL",
        "algodon-puro": "ALG100",
        "seda-fria": "TFRI",
        "algodon-heavy-weight-250g": "ALGP250",
        "algodon-perchado": "ALGP",
        "tela-burda": "BURD",
        "suplex-poliamida": "SUPL",
    },
    "color": {
        "sin-definir": "SDF",
        "negro": "NEG",
    },
    "talla": {
        "adulto": "ADU",
        "nino": "NIN",
        "unica": "UNI",
        "plus": "PLS",
    },
}


def codigo_tecnico(valor, tipo, limite):
    clave = slugify(str(valor or ""))
    return CODIGOS_CONOCIDOS.get(tipo, {}).get(
        clave,
        (clave.replace("-", "").upper()[:limite] or "ITEM"),
    )


def codigo_legacy(valor, limite):
    """Formato usado por la versión que recortaba nombres visibles."""
    valor_limpio = re.sub(r"[^A-Z0-9]", "", slugify(str(valor or "")).upper())
    return valor_limpio[:limite] or "ITEM"


def normalizar_skus_automaticos(apps, schema_editor):
    ProductoVariante = apps.get_model("inventory", "ProductoVariante")

    for variante in ProductoVariante.objects.select_related(
        "producto_base",
        "tipo_tela",
        "color",
        "talla",
    ).iterator():
        sku_anterior = "-".join((
            codigo_legacy(variante.producto_base.nombre, 6),
            codigo_legacy(variante.tipo_tela.nombre, 5),
            codigo_legacy(variante.color.nombre, 5),
            codigo_legacy(variante.talla.nombre, 4),
        ))

        # Se preservan por completo códigos personalizados o ya normalizados.
        if (variante.sku or "").upper() != sku_anterior:
            continue

        sku_nuevo = "-".join((
            codigo_tecnico(variante.producto_base.nombre, "producto", 8),
            codigo_tecnico(variante.tipo_tela.nombre, "tela", 8),
            codigo_tecnico(variante.color.nombre, "color", 5),
            codigo_tecnico(variante.talla.nombre, "talla", 4),
        ))

        # No sustituye un SKU si otro registro ya usa el destino por decisión
        # manual. Así una migración nunca rompe la restricción de unicidad.
        existe_destino = ProductoVariante.objects.exclude(pk=variante.pk).filter(
            sku__iexact=sku_nuevo
        ).exists()
        if not existe_destino:
            ProductoVariante.objects.filter(pk=variante.pk).update(sku=sku_nuevo)


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0010_participantes_corte"),
    ]

    operations = [
        migrations.RunPython(
            normalizar_skus_automaticos,
            migrations.RunPython.noop,
        ),
    ]
