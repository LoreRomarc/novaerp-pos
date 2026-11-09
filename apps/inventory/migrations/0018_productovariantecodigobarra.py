from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0017_movimientostock_tipos_traslado"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductoVarianteCodigoBarra",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("codigo", models.CharField(db_index=True, max_length=120, unique=True)),
                ("origen", models.CharField(blank=True, default="", max_length=80)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                ("variante", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="codigos_barras_alternos", to="inventory.productovariante")),
            ],
            options={"ordering": ["codigo"]},
        ),
    ]
