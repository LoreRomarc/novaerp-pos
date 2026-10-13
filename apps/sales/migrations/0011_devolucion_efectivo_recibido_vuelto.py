# Generated manually for the change/devolution receipt audit values.
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0010_vendedores_y_ticket_zpl")]

    operations = [
        migrations.AddField(
            model_name="devolucion",
            name="monto_recibido_efectivo",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
        migrations.AddField(
            model_name="devolucion",
            name="vuelto_efectivo",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=14),
        ),
    ]
