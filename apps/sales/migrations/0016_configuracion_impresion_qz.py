from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("sales", "0015_preferencias_vendedores_pos")]

    operations = [
        migrations.AlterField(
            model_name="configuracionimpresionventa",
            name="modo_impresion",
            field=models.CharField(
                choices=[
                    (
                        "QZ_PIXEL",
                        "Impresora de Windows mediante QZ Tray (recomendado)",
                    ),
                ],
                default="QZ_PIXEL",
                max_length=20,
            ),
        ),
    ]
