from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0020_historial_pos_jnstudio")]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionEtiquetaProducto",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ancho_mm", models.DecimalField(decimal_places=2, default=45, max_digits=5)),
                ("alto_mm", models.DecimalField(decimal_places=2, default=35, max_digits=5)),
                ("margen_lateral_mm", models.DecimalField(decimal_places=2, default=1, max_digits=4)),
                ("margen_superior_mm", models.DecimalField(decimal_places=2, default=3, max_digits=4)),
                ("margen_inferior_mm", models.DecimalField(decimal_places=2, default=3, max_digits=4)),
                ("alto_barra_mm", models.DecimalField(decimal_places=2, default=13.5, max_digits=5)),
                ("ancho_modulo_mm", models.DecimalField(decimal_places=3, default=0.25, max_digits=4)),
                ("tamano_nombre_pt", models.DecimalField(decimal_places=1, default=8, max_digits=4)),
                ("tamano_codigo_pt", models.DecimalField(decimal_places=1, default=7.5, max_digits=4)),
                ("espacio_nombre_codigo_mm", models.DecimalField(decimal_places=2, default=1, max_digits=4)),
                ("espacio_codigo_texto_mm", models.DecimalField(decimal_places=2, default=3, max_digits=4)),
                ("actualizado", models.DateTimeField(auto_now=True)),
            ],
        )
    ]
