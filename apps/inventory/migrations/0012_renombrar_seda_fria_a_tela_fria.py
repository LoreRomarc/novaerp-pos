"""Corrige el nombre comercial de la tela sin alterar sus relaciones."""

from django.db import migrations


def renombrar_tela(apps, schema_editor):
    TipoTela = apps.get_model("inventory", "TipoTela")

    anterior = TipoTela.objects.filter(nombre__iexact="Seda Fría").first()
    destino = TipoTela.objects.filter(nombre__iexact="Tela Fría").first()

    # Se mantiene el mismo registro y sus claves foráneas (variantes, rollos,
    # producción y movimientos). Si alguien ya creó "Tela Fría" manualmente,
    # no se fusionan datos automáticamente para evitar modificar historial.
    if anterior and not destino:
        TipoTela.objects.filter(pk=anterior.pk).update(nombre="Tela Fría")


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0011_normalizar_skus_legacy"),
    ]

    operations = [
        migrations.RunPython(renombrar_tela, migrations.RunPython.noop),
    ]
