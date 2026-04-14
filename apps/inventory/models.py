# apps/inventory/models.py
from decimal import Decimal
from django.db import models
from django.db.models import Q

from apps.core.models import Sucursal


class Color(models.Model):
    nombre = models.CharField(max_length=50)
    codigo_hex = models.CharField(max_length=7, blank=True)

    def __str__(self):
        return self.nombre


class TipoTela(models.Model):
    nombre = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


class ProductoBase(models.Model):
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre


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


class ProductoQuerySet(models.QuerySet):
    def activos(self):
        return self.filter(activo=True)

    def buscar(self, termino):
        # Busca tanto en producto como en variantes, color, tela y SKU
        return self.filter(
            Q(nombre__icontains=termino) |
            Q(codigo_barras__icontains=termino) |
            Q(variante__sku__icontains=termino) |
            Q(variante__color__nombre__icontains=termino) |
            Q(variante__tipo_tela__nombre__icontains=termino)
        ).distinct()


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
    
    def variantes_disponibles(self):
        if self.variante:
            return self.variante.producto_base.variantes.all()
        return ProductoVariante.objects.filter(producto_base=self)


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

    def save(self, *args, **kwargs):
        if self.cantidad < 0:
            raise ValueError("Stock no puede ser negativo")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.variante} - {self.sucursal.nombre}"
    

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

    referencia = models.CharField(max_length=100)

    creado = models.DateTimeField(auto_now_add=True)


# =========================================================
# TRASLADOS (NUEVO)
# =========================================================

class Traslado(models.Model):

    origen = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="traslados_origen"
    )

    destino = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="traslados_destino"
    )

    creado = models.DateTimeField(auto_now_add=True)
    ejecutado = models.BooleanField(default=False)

    def __str__(self):
        return f"Traslado #{self.id} {self.origen} → {self.destino}"


class TrasladoDetalle(models.Model):

    traslado = models.ForeignKey(
        Traslado,
        related_name="detalles",
        on_delete=models.CASCADE
    )

    variante = models.ForeignKey(
        ProductoVariante,
        on_delete=models.PROTECT
    )

    cantidad = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f"{self.variante} x {self.cantidad}"
    
usuario = models.ForeignKey(
    "auth.User",
    on_delete=models.PROTECT,
    null=True,
    blank=True
)

costo_unitario = models.DecimalField(
    max_digits=14,
    decimal_places=2,
    null=True,
    blank=True
)

saldo_post_movimiento = models.DecimalField(
    max_digits=14,
    decimal_places=2,
    null=True,
    blank=True
)