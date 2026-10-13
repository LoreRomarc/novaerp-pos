from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0005_turno_abierto_por_usuario_y_sucursal"),
    ]

    operations = [
        migrations.CreateModel(
            name="ConfiguracionImpresionVenta",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("impresion_automatica", models.BooleanField(default=True)),
                (
                    "ancho_papel_mm",
                    models.PositiveSmallIntegerField(
                        choices=[
                            (25, "25 mm (prueba / mini ticket)"),
                            (58, "58 mm (térmica POS estándar)"),
                            (80, "80 mm (térmica POS ancha)"),
                        ],
                        default=25,
                    ),
                ),
                (
                    "mensaje_pie",
                    models.CharField(
                        blank=True,
                        default="Gracias por su compra.",
                        max_length=180,
                    ),
                ),
                ("actualizado", models.DateTimeField(auto_now=True)),
                (
                    "sucursal",
                    models.OneToOneField(
                        on_delete=models.deletion.CASCADE,
                        related_name="configuracion_impresion_venta",
                        to="core.sucursal",
                    ),
                ),
            ],
            options={
                "verbose_name": "Configuración de impresión de venta",
                "verbose_name_plural": "Configuraciones de impresión de venta",
            },
        ),
    ]
