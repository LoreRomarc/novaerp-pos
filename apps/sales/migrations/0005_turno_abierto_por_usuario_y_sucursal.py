from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0004_cambiodetalle_motivo_precio_and_more"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="turnocaja",
            name="unique_turno_abierto_por_usuario",
        ),
        migrations.AddConstraint(
            model_name="turnocaja",
            constraint=models.UniqueConstraint(
                fields=("usuario_apertura", "sucursal"),
                condition=Q(("estado", "ABIERTO")),
                name="unique_turno_abierto_usuario_sucursal",
            ),
        ),
    ]
