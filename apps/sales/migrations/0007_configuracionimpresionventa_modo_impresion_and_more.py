from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [("sales", "0006_configuracionimpresionventa")]

    operations = [
        migrations.AddField(model_name="configuracionimpresionventa", name="cortar_papel", field=models.BooleanField(default=True)),
        migrations.AddField(model_name="configuracionimpresionventa", name="modo_impresion", field=models.CharField(choices=[("DIRECTA_WINDOWS", "Directa por Windows (sin diálogo)"), ("NAVEGADOR", "Navegador (muestra diálogo de impresión)")], default="DIRECTA_WINDOWS", max_length=20)),
        migrations.AddField(model_name="configuracionimpresionventa", name="nombre_impresora", field=models.CharField(blank=True, default="", help_text="Vacío: usa la impresora predeterminada de Windows.", max_length=255)),
    ]
