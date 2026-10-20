# apps/inventory/models.py

import re
import unicodedata

from django.utils import timezone
from django.db import models, transaction
from django.db.models import Q, Sum
from django.core.exceptions import ValidationError
from django.db.models.functions import Lower
from django.utils.text import slugify

from apps.core.models import Sucursal


def normalizar_busqueda(valor):
    """Texto comparable para búsquedas humanas (sin depender de tildes)."""
    return "".join(
        caracter
        for caracter in unicodedata.normalize("NFD", str(valor or "").casefold())
        if unicodedata.category(caracter) != "Mn"
    )


# Los nombres comerciales se conservan como fueron escritos por el usuario.
# Los identificadores internos, en cambio, deben ser cortos, estables y
# comparables entre módulos (SKU, rollos y códigos de barra).
CODIGOS_CONOCIDOS = {
    "producto": {
        "sueter": "STR",
        "sueter-oversize": "STO",
        "sueter-combinado": "STC",
        "short": "SHT",
        "pantaloneta": "PNT",
        "pantalon-con-vena": "PCV",
        "pantalon-3-rayas": "P3R",
        "jogger": "JGR",
        "camiseta-polo": "POL",
        "licra-larga": "LCL",
        "licra-corta": "LCC",
        "sueter-de-pechera": "STP",
    },
    "tela": {
        "lycra-algodon": "ALGL",
        "algodon-puro": "ALG100",
        "tela-fria": "TFRI",
        "algodon-pesado-250gr": "ALGP250",
        "algodon-perchado": "ALGP",
        "tela-burda": "BURD",
        "suplex-poliamida": "SUPL",
        "tela-pique": "PIQ",
    },
    "color": {
        "sin-definir": "SDF",
        "negro": "NEG",
    },
    "talla": {
        "adulto": "ADU",
        "nino": "NIN",
        "unica": "UNI",
        "plus": "PLS",
    },
}


def codigo_identificador(valor, tipo, limite=12):
    """Devuelve un código técnico seguro, en mayúsculas y sin espacios."""
    clave = slugify(str(valor or ""))
    conocido = CODIGOS_CONOCIDOS.get(tipo, {}).get(clave)
    if conocido:
        return conocido

    # Conserva dígitos útiles (2XL, 250G) y elimina separadores extraños.
    codigo = clave.replace("-", "").upper()
    return (codigo[:limite] or "ITEM")


# ======================================================
# MAESTROS
# ======================================================

class Color(models.Model):

    nombre = models.CharField(
        max_length=50,
        unique=True
    )

    codigo_hex = models.CharField(
        max_length=7,
        blank=True
    )

    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                name="unique_color_nombre_lower"
            )
        ]

    def clean(self):
        self.nombre = self.nombre.strip()

    def save(self, *args, **kwargs):

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class TipoTela(models.Model):

    nombre = models.CharField(
        max_length=100,
        unique=True
    )

    descripcion = models.TextField(blank=True)

    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                name="unique_tela_nombre_lower"
            )
        ]

    def clean(self):
        self.nombre = self.nombre.strip()

    def save(self, *args, **kwargs):

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class Talla(models.Model):

    nombre = models.CharField(
        max_length=20,
        unique=True
    )

    orden = models.PositiveIntegerField(default=0)

    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["orden", "nombre"]

        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                name="unique_talla_nombre_lower"
            )
        ]

    def clean(self):
        self.nombre = self.nombre.strip()

    def save(self, *args, **kwargs):

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


class ProductoBase(models.Model):

    nombre = models.CharField(
        max_length=200,
        unique=True
    )

    descripcion = models.TextField(blank=True)

    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ["nombre"]

        constraints = [
            models.UniqueConstraint(
                Lower("nombre"),
                name="unique_producto_base_lower"
            )
        ]

    def clean(self):
        self.nombre = self.nombre.strip()

    def save(self, *args, **kwargs):

        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return self.nombre


# ======================================================
# PRODUCTO VARIANTE
# ======================================================

class ProductoVariante(models.Model):

    producto_base = models.ForeignKey(
        ProductoBase,
        on_delete=models.CASCADE,
        related_name="variantes"
    )

    tipo_tela = models.ForeignKey(
        TipoTela,
        on_delete=models.PROTECT
    )

    color = models.ForeignKey(
        Color,
        on_delete=models.PROTECT
    )

    talla = models.ForeignKey(
        Talla,
        on_delete=models.PROTECT
    )

    sku = models.CharField(
        max_length=100,
        unique=True,
        blank=True,
    )

    codigo_barras = models.CharField(
        max_length=120,
        null=True,
        blank=True,
        unique=True
    )

    precio_venta = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    costo_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    stock_minimo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(
        auto_now_add=True,
        null=True,
        blank=True
    )

    class Meta:

        ordering = ["-id"]

        indexes = [
            models.Index(fields=["sku"]),
            models.Index(fields=["codigo_barras"]),
        ]

        unique_together = (
            "producto_base",
            "tipo_tela",
            "color",
            "talla"
        )

    def clean(self):
        self.sku = re.sub(
            r"[^A-Z0-9]+",
            "-",
            (self.sku or "").upper(),
        ).strip("-")
        self.codigo_barras = (self.codigo_barras or "").strip().upper() or None
        # En formularios Django la validación ocurre antes de `save()`. El
        # SKU vacío es válido temporalmente y se genera justo antes de guardar.

    @staticmethod
    def _codigo_legible(valor, limite=12):
        return codigo_identificador(valor, "producto", limite)

    def _generar_sku_automatico(self):
        base = "-".join([
            codigo_identificador(self.producto_base.nombre, "producto", 8),
            codigo_identificador(self.tipo_tela.nombre, "tela", 8),
            codigo_identificador(self.color.nombre, "color", 5),
            codigo_identificador(self.talla.nombre, "talla", 4),
        ])
        candidato = base
        consecutivo = 2
        while ProductoVariante.objects.exclude(pk=self.pk).filter(
            sku__iexact=candidato
        ).exists():
            sufijo = f"-{consecutivo}"
            candidato = f"{base[:100 - len(sufijo)]}{sufijo}"
            consecutivo += 1
        return candidato

    @staticmethod
    def _codigo_barras_interno_ean13(pk):
        """EAN-13 interno con prefijo 770 y dígito verificador.

        No se debe presentar como un código GS1 asignado por GS1 Colombia;
        sirve para identificar de forma única productos dentro del ERP y para
        lectores configurados como teclado.
        """
        base = f"770{int(pk):09d}"  # 12 dígitos sin verificador.
        suma = sum(
            int(digito) * (3 if indice % 2 else 1)
            for indice, digito in enumerate(reversed(base))
        )
        return f"{base}{(10 - suma % 10) % 10}"

    def save(self, *args, **kwargs):
        if not (self.sku or "").strip():
            self.sku = self._generar_sku_automatico()
        self.full_clean()
        super().save(*args, **kwargs)

        # Código EAN-13 interno, estable y escaneable. Solo se crea si el
        # usuario no registró uno propio; no modifica códigos existentes.
        if not self.codigo_barras:
            codigo = self._codigo_barras_interno_ean13(self.pk)
            type(self).objects.filter(pk=self.pk).update(codigo_barras=codigo)
            self.codigo_barras = codigo

    def __str__(self):
        return self.nombre_completo

    @property
    def stock_total(self):

        return (
            self.stocks.aggregate(
                total=Sum("cantidad")
            )["total"] or 0
        )

    @property
    def nombre_completo(self):
        # Esta etiqueta es el estándar visual para cada punto del ERP. El
        # SKU conserva el identificador técnico; la etiqueta permite a una
        # persona reconocer la prenda sin conocer códigos internos.
        partes = (
            self.producto_base.nombre,
            self.tipo_tela.nombre,
            self.talla.nombre,
            self.color.nombre,
        )
        return " · ".join(str(parte or "").upper() for parte in partes)

    @property
    def nombre(self):
        return self.nombre_completo

    @property
    def codigo(self):
        return self.sku
    
    @classmethod
    def generar_sku_unico(
        cls,
        producto_base,
        tipo_tela,
        color,
        talla,
    ):
        return (
            f"{producto_base.id}"
            f"-{tipo_tela.id}"
            f"-{color.id}"
            f"-{talla.id}"
        )


# PRODUCTO FINAL
class ProductoQuerySet(models.QuerySet):
    def activos(self):
        return self.filter(activo=True)

    def buscar(self, termino):
        return self.filter(
            Q(nombre__icontains=termino) |
            Q(codigo_barras__icontains=termino) |
            Q(variante__sku__icontains=termino) |
            Q(variante__color__nombre__icontains=termino) |
            Q(variante__tipo_tela__nombre__icontains=termino)
        ).distinct()


# STOCK
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

    costo_promedio = models.DecimalField(max_digits=14, decimal_places=2, default=0)

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

    def actualizar_stock(variante, sucursal, cantidad):
        from apps.inventory.models import Stock

        with transaction.atomic():
            stock = Stock.objects.select_for_update().get(
                variante=variante,
                sucursal=sucursal
            )

            stock.cantidad += cantidad
            stock.save()

    def __str__(self):
        return f"{self.variante} - {self.sucursal.nombre}"


# MOVIMIENTOS DE STOCK (VENTAS, AJUSTES, TRASLADOS, PRODUCCION)
class MovimientoStock(models.Model):

    TIPOS = (

        ("VENTA", "Venta"),
        ("ANULACION", "Anulación"),

        ("AJUSTE_ENTRADA", "Ajuste entrada"),
        ("AJUSTE_SALIDA", "Ajuste salida"),

        ("TRASLADO", "Traslado"),
        # Tipos usados por traslados existentes y nuevos. Se mantienen los
        # legados para que ningún kardex histórico quede sin etiqueta/filtro.
        ("COMPLETO", "Traslado completo"),
        ("SALIDA", "Salida entre sucursales"),
        ("ENTRADA", "Entrada entre sucursales"),

        ("DANADO", "Dañado"),
        ("MERMA", "Merma"),

        ("CONSUMO_INTERNO", "Consumo interno"),

        ("DEVOLUCION_CLIENTE", "Devolución cliente"),
        ("DEVOLUCION_PROVEEDOR", "Devolución proveedor"),

        ("PRODUCCION", "Producción"),

        ("INICIAL", "Inventario inicial"),
    )

    variante = models.ForeignKey(
        ProductoVariante,
        on_delete=models.PROTECT
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT
    )

    tipo = models.CharField(max_length=30, choices=TIPOS)

    cantidad = models.DecimalField(max_digits=12, decimal_places=2)

    referencia = models.CharField(max_length=100, null=True, blank=True)

    observacion = models.TextField(
        blank=True,
        default="",
        help_text="Detalle o justificación del movimiento de inventario.",
    )

    usuario = models.ForeignKey(
        "auth.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )

    saldo_post_movimiento = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True
    )

    costo_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True
    )

    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.variante} | {self.tipo} | {self.cantidad}"

    @property
    def tipo_legible(self):
        """Etiqueta clara también para tipos históricos de traslados."""
        etiquetas = dict(self.TIPOS)
        etiquetas.update({
            "COMPLETO": "Traslado completo",
            "SALIDA": "Salida entre sucursales",
            "ENTRADA": "Entrada entre sucursales",
        })
        return etiquetas.get(self.tipo, self.tipo.replace("_", " ").title())


# ======================================================
# MOVIMIENTOS INVENTARIO / TRASLADOS
# ======================================================

class Traslado(models.Model):

    ESTADOS = (
        ("BORRADOR", "Borrador"),
        ("ENVIADO", "Enviado"),
        ("RECIBIDO", "Recibido"),
        ("CANCELADO", "Cancelado"),
    )

    TIPOS = (

        # ENTRE SUCURSALES
        ("COMPLETO", "Traslado completo"),
        ("SALIDA", "Salida entre sucursales"),
        ("ENTRADA", "Entrada entre sucursales"),

        # MOVIMIENTOS INVENTARIO
        ("AJUSTE_ENTRADA", "Ajuste entrada"),
        ("AJUSTE_SALIDA", "Ajuste salida"),

        ("DANADO", "Producto dañado"),
        ("MERMA", "Merma"),
        ("CONSUMO_INTERNO", "Consumo interno"),

        ("DEVOLUCION_CLIENTE", "Devolución cliente"),
        ("DEVOLUCION_PROVEEDOR", "Devolución proveedor"),

        ("INICIAL", "Carga inventario inicial"),
    )

    numero = models.CharField(
        max_length=30,
        unique=True,
        blank=True,
        null=True
    )

    origen = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="traslados_origen",
        null=True,
        blank=True
    )

    destino = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="traslados_destino",
        null=True,
        blank=True
    )

    tipo = models.CharField(
        max_length=30,
        choices=TIPOS,
        default="COMPLETO"
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="BORRADOR"
    )

    motivo = models.CharField(
        max_length=255,
        blank=True
    )

    observaciones = models.TextField(blank=True)

    enviado_por = models.ForeignKey(
        "auth.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="traslados_enviados"
    )

    recibido_por = models.ForeignKey(
        "auth.User",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="traslados_recibidos"
    )

    fecha_envio = models.DateTimeField(null=True, blank=True)

    fecha_recepcion = models.DateTimeField(null=True, blank=True)

    creado = models.DateTimeField(auto_now_add=True)

    actualizado = models.DateTimeField(auto_now=True)

    class Meta:

        ordering = ["-id"]

        indexes = [
            models.Index(fields=["estado"]),
            models.Index(fields=["tipo"]),
            models.Index(fields=["numero"]),
            models.Index(fields=["creado"]),
        ]

    def __str__(self):

        return f"{self.numero} | {self.get_tipo_display()}"

    def save(self, *args, **kwargs):

        if not self.numero:

            fecha = timezone.now().strftime("%Y%m%d")

            ultimo = Traslado.objects.count() + 1

            self.numero = f"MOV-{fecha}-{ultimo}"

        super().save(*args, **kwargs)

    @property
    def total_items(self):
        return self.detalles.count()

    @property
    def total_unidades(self):
        return sum(i.cantidad for i in self.detalles.all())


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

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    observacion = models.CharField(
        max_length=255,
        blank=True
    )

    class Meta:
        unique_together = (
            "traslado",
            "variante"
        )

    def __str__(self):
        return f"{self.variante} x {self.cantidad}"
