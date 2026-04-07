# apps/inventory/models_produccion.py
from django.db import models
from decimal import Decimal

from apps.core.models import Sucursal
from apps.inventory.models import ProductoVariante, TipoTela, Color, ProductoBase


# =========================================================
# ROLLOS (ACTUALIZADO)
# =========================================================

class RolloTela(models.Model):

    tipo_tela = models.ForeignKey(TipoTela, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, on_delete=models.PROTECT)

    codigo = models.CharField(max_length=50, unique=True)

    cantidad_disponible = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    ESTADOS = (
        ("DISPONIBLE", "Disponible"),
        ("CONSUMIDO", "Consumido"),
    )

    estado = models.CharField(max_length=20, choices=ESTADOS, default="DISPONIBLE")

    def __str__(self):
        return f"{self.codigo} - {self.tipo_tela} - {self.color}"


# =========================================================
# PRODUCCION DESDE CORTE (NUEVO)
# =========================================================

class ProduccionLote(models.Model):
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT)

    rollo = models.ForeignKey(RolloTela, on_delete=models.PROTECT)

    tipo_tela = models.ForeignKey(TipoTela, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, on_delete=models.PROTECT)

    consumo_total = models.DecimalField(max_digits=12, decimal_places=2)
    consumo_unitario = models.DecimalField(max_digits=12, decimal_places=6)

    total_prendas = models.IntegerField()

    ejecutado = models.BooleanField(default=False)

    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Lote #{self.id} - {self.rollo.codigo}"


class ProduccionDetalle(models.Model):

    lote = models.ForeignKey(
        ProduccionLote,
        related_name="detalles",
        on_delete=models.CASCADE
    )

    producto_base = models.ForeignKey(ProductoBase, on_delete=models.PROTECT)
    talla = models.CharField(max_length=10)

    variante = models.ForeignKey(
        ProductoVariante,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    cantidad = models.IntegerField()

    tipo_tela = models.ForeignKey(TipoTela, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.producto_base} - {self.talla} x {self.cantidad}"


# =========================================================
# ORDEN CORTE (SE MANTIENE)
# =========================================================

class OrdenCorte(models.Model):

    sucursal = models.ForeignKey("core.Sucursal", on_delete=models.PROTECT)

    ESTADOS = (
        ("PENDIENTE", "Pendiente"),
        ("EN_PROCESO", "En proceso"),
        ("TERMINADO", "Terminado"),
    )

    estado = models.CharField(max_length=20, choices=ESTADOS, default="PENDIENTE")


class OrdenCorteDetalle(models.Model):

    orden = models.ForeignKey(OrdenCorte, related_name="detalles", on_delete=models.CASCADE)

    variante = models.ForeignKey(ProductoVariante, on_delete=models.PROTECT)

    cantidad = models.IntegerField()


# =========================================================
# INGRESO PRODUCCION (NO MODIFICADO)
# =========================================================

class IngresoProduccion(models.Model):
    orden = models.ForeignKey(OrdenCorte, on_delete=models.CASCADE, null=True, blank=True)


class IngresoProduccionDetalle(models.Model):

    ingreso = models.ForeignKey(IngresoProduccion, related_name="detalles", on_delete=models.CASCADE)

    variante = models.ForeignKey(ProductoVariante, on_delete=models.PROTECT)

    cantidad = models.IntegerField()