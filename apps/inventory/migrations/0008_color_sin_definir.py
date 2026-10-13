from django.db import migrations


def crear_color_neutro(apps, schema_editor):
    """Permite una transición gradual a inventario discriminado por color."""
    Color = apps.get_model("inventory", "Color")
    if not Color.objects.filter(nombre__iexact="SIN DEFINIR").exists():
        Color.objects.create(nombre="SIN DEFINIR", codigo_hex="#6B7280")


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0007_tallas_iniciales_operacion"),
    ]

    operations = [
        migrations.RunPython(crear_color_neutro, migrations.RunPython.noop),
    ]
