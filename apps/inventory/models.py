# apps/inventory/models.py

from decimal import Decimal
from django.db import models
from django.db.models import Q
from apps.core.models import Sucursal


# =========================================================
# PRODUCTO
# =========================================================

class ProductoQuerySet(models.QuerySet):
    def activos(self):
        return self.filter(activo=True)

    def buscar(self, termino):
        return self.filter(
            Q(nombre__icontains=termino) |
            Q(codigo_barras__icontains=termino)
        )


class Producto(models.Model):

    TIPO_IVA = (
        ("GRAVADO", "Gravado"),
        ("EXENTO", "Exento"),
        ("NO_SUJETO", "No sujeto"),
    )

    nombre = models.CharField(max_length=200)
    codigo_barras = models.CharField(max_length=100, unique=True, null=True, blank=True)

    # Información fiscal
    tipo_iva = models.CharField(max_length=20, choices=TIPO_IVA, default="GRAVADO")
    porcentaje_iva = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("19.00"))
    incluye_iva = models.BooleanField(default=True)

    controla_stock = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)

    objects = ProductoQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["nombre"]),
            models.Index(fields=["codigo_barras"]),
            models.Index(fields=["activo"]),
        ]

    def tasa_iva(self):
        return self.porcentaje_iva / Decimal("100")

    def __str__(self):
        return f"{self.nombre} ({self.codigo_barras})"
 

# =========================================================
# STOCK
# =========================================================

class StockManager(models.Manager):
    def for_update(self):
        return self.select_for_update()


class Stock(models.Model):

    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        related_name="stocks"
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="stocks"
    )

    cantidad = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    objects = StockManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["producto", "sucursal"],
                name="unique_stock_producto_sucursal"
            )
        ]
        indexes = [
            models.Index(fields=["producto", "sucursal"]),
        ]

    def __str__(self):
        return f"{self.producto.nombre} - {self.sucursal.nombre}"


# =========================================================
# MOVIMIENTO STOCK
# =========================================================

class MovimientoStock(models.Model):

    TIPOS = (
        ("VENTA", "Venta"),
        ("ANULACION", "Anulación"),
        ("AJUSTE", "Ajuste"),
        ("TRASLADO", "Traslado"),
    )

    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT)

    tipo = models.CharField(max_length=20, choices=TIPOS)
    cantidad = models.DecimalField(max_digits=12, decimal_places=2)

    referencia = models.IntegerField()  # id venta o ajuste
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["producto", "sucursal"]),
            models.Index(fields=["tipo"]),
        ]