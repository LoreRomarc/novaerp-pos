from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0017_configuracion_impresion_conector_windows")]

    operations = [
        migrations.AddField(
            model_name="arqueoturno",
            name="actualizado_en",
            field=models.DateTimeField(auto_now=True),
        ),
        migrations.AddField(
            model_name="arqueoturno",
            name="actualizado_por",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.PROTECT,
                related_name="arqueos_actualizados",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
