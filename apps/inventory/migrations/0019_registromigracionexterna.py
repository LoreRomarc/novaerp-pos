from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0018_productovariantecodigobarra"),
    ]

    operations = [
        migrations.CreateModel(
            name="RegistroMigracionExterna",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("origen", models.CharField(max_length=80)),
                ("tipo_registro", models.CharField(max_length=80)),
                ("id_origen", models.CharField(max_length=100)),
                ("modelo_destino", models.CharField(max_length=120)),
                ("id_destino", models.BigIntegerField()),
                ("datos_origen", models.JSONField(blank=True, default=dict)),
                ("importado_en", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["origen", "tipo_registro", "id_origen"]},
        ),
        migrations.AddConstraint(
            model_name="registromigracionexterna",
            constraint=models.UniqueConstraint(fields=("origen", "tipo_registro", "id_origen"), name="inventory_migracion_externa_origen_unico"),
        ),
        migrations.AddIndex(
            model_name="registromigracionexterna",
            index=models.Index(fields=["origen", "tipo_registro"], name="inventory_reg_origen_tipo_idx"),
        ),
        migrations.AddIndex(
            model_name="registromigracionexterna",
            index=models.Index(fields=["modelo_destino", "id_destino"], name="inventory_reg_destino_idx"),
        ),
    ]
