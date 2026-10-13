from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("sales", "0007_configuracionimpresionventa_modo_impresion_and_more")]

    operations = [
        migrations.AlterField(
            model_name="configuracionimpresionventa",
            name="modo_impresion",
            field=models.CharField(
                choices=[
                    ("DIRECTA_WINDOWS", "Directa por Windows (sin diálogo)"),
                    ("ZPL_WINDOWS", "Etiquetas ZPL por Windows (SAT TT448 / Zebra)"),
                    ("NAVEGADOR", "Navegador (muestra diálogo de impresión)"),
                ],
                default="DIRECTA_WINDOWS",
                max_length=20,
            ),
        ),
    ]
