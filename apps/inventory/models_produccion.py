# apps/inventory/models_produccion.py
from django.db import models
from apps.inventory.models import ProductoVariante, TipoTela, Color


# =========================================================
# ROLLOS
# =========================================================

class RolloTela(models.Model):

    tipo_tela = models.ForeignKey(TipoTela, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, on_delete=models.PROTECT)

    codigo = models.CharField(max_length=50, unique=True)

    ESTADOS = (
        ("DISPONIBLE", "Disponible"),
        ("CONSUMIDO", "Consumido"),
    )

    estado = models.CharField(max_length=20, choices=ESTADOS, default="DISPONIBLE")

    def __str__(self):
        return self.codigo


# =========================================================
# ORDEN CORTE
# =========================================================

class OrdenCorte(models.Model):

    sucursal = models.ForeignKey("core.Sucursal", on_delete=models.PROTECT)

    ESTADOS = (
        ("PENDIENTE", "Pendiente"),
        ("EN_PROCESO", "En proceso"),
        ("TERMINADO", "Terminado"),
    )

    estado = models.CharField(max_length=20, choices=ESTADOS, default="PENDIENTE")


# =========================================================
# DETALLE CORTE
# =========================================================

class OrdenCorteDetalle(models.Model):

    orden = models.ForeignKey(OrdenCorte, related_name="detalles", on_delete=models.CASCADE)

    variante = models.ForeignKey(ProductoVariante, on_delete=models.PROTECT)

    cantidad = models.IntegerField()


# =========================================================
# INGRESO A INVENTARIO (CORREGIDO)
# =========================================================

class IngresoProduccion(models.Model):
    orden = models.ForeignKey(OrdenCorte, on_delete=models.CASCADE)


class IngresoProduccionDetalle(models.Model):

    ingreso = models.ForeignKey(IngresoProduccion, related_name="detalles", on_delete=models.CASCADE)

    variante = models.ForeignKey(ProductoVariante, on_delete=models.PROTECT)

    cantidad = models.IntegerField()