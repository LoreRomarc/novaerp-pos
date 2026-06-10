# apps/inventory/models_produccion.py
from django.db import models
from apps.core.models import Sucursal
from apps.inventory.models import ProductoVariante, TipoTela, Color


class RolloTela(models.Model):

    tipo_tela = models.ForeignKey(TipoTela, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, on_delete=models.PROTECT)

    codigo = models.CharField(max_length=50, unique=True)

    cantidad_inicial = models.DecimalField(max_digits=12, decimal_places=2)
    cantidad_disponible = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    costo_por_metro = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    ESTADOS = (
        ("DISPONIBLE", "Disponible"),
        ("CONSUMIDO", "Consumido"),
    )

    estado = models.CharField(max_length=20, choices=ESTADOS, default="DISPONIBLE")

    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.codigo} - {self.tipo_tela} - {self.color}"


class MovimientoRollo(models.Model):

    TIPOS = (
        ("ENTRADA", "Entrada"),
        ("CONSUMO", "Consumo"),
        ("AJUSTE", "Ajuste"),
    )

    rollo = models.ForeignKey(RolloTela, on_delete=models.PROTECT)
    tipo = models.CharField(max_length=20, choices=TIPOS)

    cantidad = models.DecimalField(max_digits=12, decimal_places=2)
    saldo_post = models.DecimalField(max_digits=12, decimal_places=2)

    referencia = models.CharField(max_length=100, null=True, blank=True)

    usuario = models.ForeignKey("auth.User", on_delete=models.PROTECT)

    creado = models.DateTimeField(auto_now_add=True)


# ======================================================
# RELACIÓN DE CONSUMO POR ROLLO
# ======================================================

class CorteRollo(models.Model):

    lote = models.ForeignKey(
        "ProduccionLote",
        related_name="rollos",
        on_delete=models.CASCADE
    )

    rollo = models.ForeignKey(RolloTela, on_delete=models.PROTECT)

    metros_consumidos = models.DecimalField(max_digits=12, decimal_places=2)

    costo_total = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.lote.referencia} | {self.rollo.codigo}"


# ======================================================
# PRODUCCIÓN
# ======================================================

class ProduccionLote(models.Model):

    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT)

    consumo_total = models.DecimalField(max_digits=12, decimal_places=2)
    consumo_unitario = models.DecimalField(max_digits=12, decimal_places=6)

    total_prendas = models.IntegerField()

    merma = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    eficiencia = models.DecimalField(max_digits=5, decimal_places=2, default=100)

    costo_total = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    costo_unitario_real = models.DecimalField(max_digits=14, decimal_places=6, default=0)

    operario = models.ForeignKey("auth.User", on_delete=models.PROTECT)

    referencia = models.CharField(max_length=100, unique=True)

    ejecutado = models.BooleanField(default=False)

    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.referencia


class ProduccionDetalle(models.Model):

    lote = models.ForeignKey(
        ProduccionLote,
        related_name="detalles",
        on_delete=models.CASCADE
    )

    variante = models.ForeignKey(ProductoVariante, on_delete=models.PROTECT)

    cantidad = models.IntegerField()

    consumo_unitario = models.DecimalField(max_digits=12, decimal_places=6)
    consumo_total = models.DecimalField(max_digits=12, decimal_places=2)

    costo_unitario = models.DecimalField(max_digits=14, decimal_places=6)
    costo_total = models.DecimalField(max_digits=14, decimal_places=2)

    def __str__(self):
        return f"{self.variante} x {self.cantidad}"