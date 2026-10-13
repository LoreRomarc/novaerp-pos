from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("sales", "0008_alter_configuracionimpresionventa_modo_impresion")]

    operations = [
        migrations.AlterField(
            model_name="configuracionimpresionventa",
            name="ancho_papel_mm",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (25, "25 mm (prueba / mini ticket)"),
                    (33, "33 mm (etiqueta SAT de prueba)"),
                    (58, "58 mm (térmica POS estándar)"),
                    (80, "80 mm (térmica POS ancha)"),
                ],
                default=25,
            ),
        ),
        migrations.AlterField(
            model_name="configuracionimpresionventa",
            name="modo_impresion",
            field=models.CharField(
                choices=[
                    ("DIRECTA_WINDOWS", "Directa por Windows (sin diálogo)"),
                    ("ZPL_WINDOWS", "Etiquetas ZPL por Windows (SAT TT448 / Zebra)"),
                    ("ESC_POS_WINDOWS", "Ticket POS ESC/POS por Windows (58/80 mm)"),
                    ("NAVEGADOR", "Navegador (muestra diálogo de impresión)"),
                ],
                default="DIRECTA_WINDOWS",
                max_length=20,
            ),
        ),
    ]
