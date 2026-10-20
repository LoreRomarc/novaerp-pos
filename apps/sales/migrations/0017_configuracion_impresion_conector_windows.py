from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0016_configuracion_impresion_qz")]

    operations = [
        migrations.AlterField(
            model_name="configuracionimpresionventa",
            name="modo_impresion",
            field=models.CharField(
                choices=[
                    (
                        "WINDOWS_CONNECTOR",
                        "Conector local de Windows (impresión automática)",
                    ),
                ],
                default="WINDOWS_CONNECTOR",
                max_length=20,
            ),
        ),
    ]
