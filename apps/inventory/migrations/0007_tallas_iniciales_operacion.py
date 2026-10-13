from django.db import migrations


TALLAS_INICIALES = [
    ("ADULTO", 1),
    ("NIÑO", 2),
    ("16", 3),
    ("S", 4),
    ("M", 5),
    ("L", 6),
    ("XL", 7),
    ("2XL", 8),
    ("3XL", 9),
    ("4XL", 10),
    ("UNICA", 11),
    ("PLUS", 12),
]


def crear_tallas_iniciales(apps, schema_editor):
    """Amplía el catálogo sin tocar nombres ni variantes existentes."""
    Talla = apps.get_model("inventory", "Talla")
    for nombre, orden in TALLAS_INICIALES:
        talla = Talla.objects.filter(nombre__iexact=nombre).first()
        if talla is None:
            Talla.objects.create(nombre=nombre, orden=orden, activo=True)


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_movimiento_stock_observacion"),
    ]

    operations = [
        migrations.RunPython(crear_tallas_iniciales, migrations.RunPython.noop),
    ]
