"""Corrige el nombre comercial de algodón pesado manteniendo su historial."""

from django.db import migrations


def renombrar_tela(apps, schema_editor):
    TipoTela = apps.get_model("inventory", "TipoTela")

    anterior = TipoTela.objects.filter(
        nombre__iexact="Algodón Heavy Weight 250g"
    ).first()
    destino = TipoTela.objects.filter(
        nombre__iexact="Algodón Pesado 250gr"
    ).first()

    # Se conserva el mismo ID de tela; por ello sus variantes, rollos, cortes y
    # movimientos históricos siguen apuntando al mismo registro. Si el nombre
    # correcto fue creado manualmente, no se fusionan ambos registros de forma
    # automática para evitar modificar referencias existentes.
    if anterior and not destino:
        TipoTela.objects.filter(pk=anterior.pk).update(
            nombre="Algodón Pesado 250gr"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0012_renombrar_seda_fria_a_tela_fria"),
    ]

    operations = [
        migrations.RunPython(renombrar_tela, migrations.RunPython.noop),
    ]
