from django.db import migrations
from django.db.models import F


def asignar_destino_fabrica(apps, schema_editor):
    ProduccionLote = apps.get_model("inventory", "ProduccionLote")
    ProduccionLote.objects.filter(sucursal_destino__isnull=True).update(
        sucursal_destino_id=F("sucursal_id")
    )


class Migration(migrations.Migration):
    dependencies = [("inventory", "0003_produccion_destino_y_sku")]

    operations = [migrations.RunPython(asignar_destino_fabrica, migrations.RunPython.noop)]
