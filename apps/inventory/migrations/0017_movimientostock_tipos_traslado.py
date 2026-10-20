from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("inventory", "0013_renombrar_algodon_pesado")]

    operations = [
        migrations.AlterField(
            model_name="movimientostock",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("VENTA", "Venta"), ("ANULACION", "Anulación"),
                    ("AJUSTE_ENTRADA", "Ajuste entrada"), ("AJUSTE_SALIDA", "Ajuste salida"),
                    ("TRASLADO", "Traslado"), ("COMPLETO", "Traslado completo"),
                    ("SALIDA", "Salida entre sucursales"), ("ENTRADA", "Entrada entre sucursales"),
                    ("DANADO", "Dañado"), ("MERMA", "Merma"),
                    ("CONSUMO_INTERNO", "Consumo interno"),
                    ("DEVOLUCION_CLIENTE", "Devolución cliente"),
                    ("DEVOLUCION_PROVEEDOR", "Devolución proveedor"),
                    ("PRODUCCION", "Producción"), ("INICIAL", "Inventario inicial"),
                ],
                max_length=30,
            ),
        ),
    ]
