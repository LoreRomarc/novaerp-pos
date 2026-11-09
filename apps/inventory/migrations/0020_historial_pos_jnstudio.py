from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0019_registromigracionexterna"),
    ]

    operations = [
        migrations.CreateModel(
            name="VarianteHistoricaPOS",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origen_id", models.PositiveIntegerField(unique=True)),
                ("producto", models.CharField(max_length=200)),
                ("tela", models.CharField(blank=True, default="", max_length=100)),
                ("talla", models.CharField(blank=True, default="", max_length=50)),
                ("codigo_barras_anterior", models.CharField(blank=True, default="", max_length=120)),
                ("precio_mayor_anterior", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("precio_detal_anterior", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("datos_origen", models.JSONField(blank=True, default=dict)),
                ("importado_en", models.DateTimeField(auto_now_add=True)),
                ("variante_nova", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="referencias_historicas_pos", to="inventory.productovariante")),
            ],
            options={"ordering": ["producto", "tela", "talla", "origen_id"]},
        ),
        migrations.CreateModel(
            name="VentaHistoricaPOS",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origen_id", models.PositiveIntegerField(unique=True)),
                ("fecha", models.DateTimeField()),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("cliente", models.CharField(blank=True, default="", max_length=255)),
                ("observaciones", models.TextField(blank=True, default="")),
                ("local_anterior", models.CharField(blank=True, default="", max_length=150)),
                ("vendedor_anterior", models.CharField(blank=True, default="", max_length=150)),
                ("pago_origen", models.JSONField(blank=True, default=dict)),
                ("datos_origen", models.JSONField(blank=True, default=dict)),
                ("importado_en", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-fecha", "-origen_id"]},
        ),
        migrations.CreateModel(
            name="VentaHistoricaPOSItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("orden", models.PositiveIntegerField()),
                ("servicio_anterior", models.CharField(blank=True, default="", max_length=200)),
                ("cantidad", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("precio", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("total", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("tipo_precio", models.CharField(blank=True, default="", max_length=30)),
                ("variante_historica", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="items_ventas_historicas", to="inventory.variantehistoricapos")),
                ("venta", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="inventory.ventahistoricapos")),
            ],
            options={"ordering": ["orden"]},
        ),
        migrations.AddIndex(
            model_name="ventahistoricapos",
            index=models.Index(fields=["fecha"], name="inventory_vhpos_fecha_idx"),
        ),
        migrations.AddConstraint(
            model_name="ventahistoricapositem",
            constraint=models.UniqueConstraint(fields=("venta", "orden"), name="inventory_venta_historica_pos_item_unico"),
        ),
    ]
