# apps/inventory/models.py
from decimal import Decimal
from django.db import models
from django.db.models import Q

from apps.core.models import Sucursal


# =========================================================
# COLOR
# =========================================================

class Color(models.Model):
    nombre = models.CharField(max_length=50)
    codigo_hex = models.CharField(max_length=7, blank=True)

    def __str__(self):
        return self.nombre


# =========================================================
# TELA
# =========================================================

class TipoTela(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


# =========================================================
# PRODUCTO BASE
# =========================================================

class ProductoBase(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


# =========================================================
# VARIANTE (SKU REAL)
# =========================================================

class ProductoVariante(models.Model):
    producto_base = models.ForeignKey(
        ProductoBase,
        on_delete=models.CASCADE,
        related_name="variantes"
    )

    tipo_tela = models.ForeignKey(TipoTela, on_delete=models.PROTECT)
    color = models.ForeignKey(Color, on_delete=models.PROTECT)

    talla = models.CharField(max_length=10)

    sku = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return f"{self.producto_base.nombre} - {self.color.nombre} - {self.talla}"


# =========================================================
# PRODUCTO POS
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

    variante = models.ForeignKey(
        ProductoVariante,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    nombre = models.CharField(max_length=200)
    codigo_barras = models.CharField(max_length=100, unique=True, null=True, blank=True)

    tipo_iva = models.CharField(max_length=20, choices=TIPO_IVA, default="GRAVADO")
    porcentaje_iva = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("19.00"))
    incluye_iva = models.BooleanField(default=True)

    controla_stock = models.BooleanField(default=True)
    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)

    objects = ProductoQuerySet.as_manager()

    def tasa_iva(self):
        return self.porcentaje_iva / Decimal("100")

    def __str__(self):
        return self.nombre


# =========================================================
# STOCK (POR VARIANTE)
# =========================================================

class StockManager(models.Manager):
    def for_update(self):
        return self.select_for_update()


class Stock(models.Model):

    variante = models.ForeignKey(
        ProductoVariante,
        on_delete=models.CASCADE,
        related_name="stocks"
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.CASCADE,
        related_name="stocks"
    )

    cantidad = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    objects = StockManager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["variante", "sucursal"],
                name="unique_stock_variante_sucursal"
            )
        ]

    def __str__(self):
        return f"{self.variante} - {self.sucursal.nombre}"


# =========================================================
# MOVIMIENTO STOCK (🔥 CORREGIDO)
# =========================================================

class MovimientoStock(models.Model):

    TIPOS = (
        ("VENTA", "Venta"),
        ("ANULACION", "Anulación"),
        ("AJUSTE", "Ajuste"),
        ("TRASLADO", "Traslado"),
        ("PRODUCCION", "Producción"),
    )

    variante = models.ForeignKey(
        ProductoVariante,
        on_delete=models.PROTECT
    )

    sucursal = models.ForeignKey(Sucursal, on_delete=models.PROTECT)

    tipo = models.CharField(max_length=20, choices=TIPOS)

    cantidad = models.DecimalField(max_digits=12, decimal_places=2)

    referencia = models.IntegerField()

    creado = models.DateTimeField(auto_now_add=True)