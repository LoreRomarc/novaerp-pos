# apps/sales/models.py
from decimal import ROUND_HALF_UP, Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.utils import timezone
from django.conf import settings

from apps.inventory.models import MovimientoStock, Stock
from apps.sales.models_caja_enterprise import TurnoCaja


# =========================================================
# HELPERS
# =========================================================

def redondear_a_peso_colombiano(valor: Decimal) -> Decimal:
    """
    Redondea al múltiplo de 50 o 100 más cercano (estilo efectivo Colombia).
    Ajusta según regla de negocio.
    """

    valor = Decimal(valor)

    # redondeo a 100 (puedes cambiar a 50 si quieres más precisión)
    return (valor / Decimal("100")).quantize(Decimal("1")) * Decimal("100")


# =========================================================
# CAJA FÍSICA
# =========================================================

class Caja(models.Model):

    sucursal = models.ForeignKey(
        "core.Sucursal",
        on_delete=models.PROTECT,
        related_name="cajas"
    )

    codigo = models.CharField(max_length=20)
    nombre = models.CharField(max_length=100)

    activa = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "codigo"],
                name="unique_caja_codigo_por_sucursal"
            )
        ]

    def __str__(self):
        return f"{self.sucursal} - {self.codigo}"


# =========================================================
# CAJEROS EN TURNO
# =========================================================

class TurnoCajaUsuario(models.Model):

    turno = models.ForeignKey(
        TurnoCaja,
        on_delete=models.CASCADE,
        related_name="cajeros"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )

    asignado_en = models.DateTimeField(auto_now_add=True)
    desasignado_en = models.DateTimeField(null=True, blank=True)

    activo = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["turno", "usuario"],
                condition=Q(activo=True),
                name="unique_usuario_activo_por_turno"
            )
        ]


# =========================================================
# VENTA
# =========================================================

class Venta(models.Model):

    ESTADOS = (
        ("ABIERTA", "Abierta"),
        ("CERRADA", "Cerrada"),
        ("ANULADA", "Anulada"),
    )

    TIPO_VENTA = (
        ("DETAL", "Detal"),
        ("MAYORISTA", "Mayorista"),
    )

    sucursal = models.ForeignKey("core.Sucursal", on_delete=models.PROTECT, related_name="ventas")

    turno = models.ForeignKey(
        "sales.TurnoCaja",
        on_delete=models.PROTECT,
        related_name="ventas"
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ventas"
    )

    tipo_venta = models.CharField(max_length=20, choices=TIPO_VENTA, default="DETAL")

    estado = models.CharField(max_length=20, choices=ESTADOS, default="ABIERTA")

    # ===============================
    # TOTALES
    # ===============================

    subtotal = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_iva = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    # ===============================
    # PAGOS
    # ===============================

    monto_efectivo = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_tarjeta = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    monto_transferencia = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    ajuste_redondeo = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    creada = models.DateTimeField(auto_now_add=True)
    cerrada = models.DateTimeField(null=True, blank=True)
    anulada = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creada"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario"],
                condition=Q(estado="ABIERTA"),
                name="unique_open_sale_per_user"
            )
        ]
        indexes = [
            models.Index(fields=["sucursal", "estado"]),
            models.Index(fields=["sucursal", "creada"]),
        ]

    def __str__(self):
        return f"Venta #{self.id} - {self.sucursal.nombre} - Total: ${self.total:,.0f}"

    # =========================================================
    # CÁLCULOS
    # =========================================================

    def recalcular_totales(self):

        totales = self.items.aggregate(
            subtotal=Sum("subtotal_linea"),
            iva=Sum("iva_linea"),
            total=Sum("total_linea"),
        )

        self.subtotal = redondear_a_peso_colombiano(totales["subtotal"] or Decimal("0"))
        self.total_iva = redondear_a_peso_colombiano(totales["iva"] or Decimal("0"))
        self.total = redondear_a_peso_colombiano(totales["total"] or Decimal("0"))

        self.save(update_fields=["subtotal", "total_iva", "total"])

    def total_pagado(self):
        return (
            self.monto_efectivo +
            self.monto_tarjeta +
            self.monto_transferencia
        )

    def puede_cerrar(self):
        return (
            self.estado == "ABIERTA"
            and self.items.exists()
            and self.total_pagado() >= self.total
        )

    # =========================================================
    # CIERRE DE VENTA
    # =========================================================

    @transaction.atomic
    def cerrar_venta(self):

        if not self.puede_cerrar():
            raise ValidationError("El pago no cubre el total.")

        for item in self.items.select_for_update():

            stock = Stock.objects.select_for_update().get(
                variante=item.variante,
                sucursal=self.sucursal
            )

            if stock.cantidad < item.cantidad:
                raise ValidationError(
                    f"Stock insuficiente para {item.variante}"
                )

            stock.cantidad -= item.cantidad
            stock.save(update_fields=["cantidad"])

            MovimientoStock.objects.create(
                variante=item.variante,
                sucursal=self.sucursal,
                tipo="VENTA",
                cantidad=item.cantidad,
                referencia=self.id
            )

        self.estado = "CERRADA"
        self.cerrada = timezone.now()

        self.save(update_fields=["estado", "cerrada"])


# =========================================================
# VENTA ITEM (🔥 VARIANTE)
# =========================================================

from django.db import models
from decimal import Decimal


class VentaItem(models.Model):

    venta = models.ForeignKey(
        "sales.Venta",
        on_delete=models.CASCADE,
        related_name="items"
    )

    # CAMBIO CLAVE: ahora es VARIANTE
    variante = models.ForeignKey(
        "inventory.ProductoVariante",
        on_delete=models.PROTECT
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1
    )

    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )
    subtotal_linea = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    iva_linea = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_linea = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    def subtotal(self):
        return self.cantidad * self.precio_unitario

    def __str__(self):
        return f"{self.variante} x {self.cantidad}"
    
    def save(self, *args, **kwargs):

        if self.venta.estado != "ABIERTA":
            raise ValidationError("No se puede modificar una venta cerrada.")

        precio = redondear_a_peso_colombiano(self.precio_unitario)
        base = redondear_a_peso_colombiano(precio * self.cantidad)

        iva = Decimal("0.00")  # puedes ajustar si quieres IVA después
        total = base + iva

        self.subtotal_linea = base
        self.iva_linea = iva
        self.total_linea = total

        super().save(*args, **kwargs)


# =========================================================
# LISTA DE PRECIOS
# =========================================================

class ListaPrecio(models.Model):

    sucursal = models.ForeignKey(
        "core.Sucursal",
        on_delete=models.CASCADE,
        related_name="listas_precios",
    )

    nombre = models.CharField(max_length=100)

    tipo_venta = models.CharField(max_length=20, choices=Venta.TIPO_VENTA)

    activa = models.BooleanField(default=True)

    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "tipo_venta"],
                name="unique_lista_por_sucursal_tipo"
            )
        ]

    def __str__(self):
        return f"{self.sucursal} - {self.nombre}"


# =========================================================
# PRECIO POR VARIANTE (🔥 CORRECTO)
# =========================================================

class PrecioVariante(models.Model):

    variante = models.ForeignKey(
        "inventory.ProductoVariante",
        on_delete=models.CASCADE,
        related_name="precios"
    )

    lista = models.ForeignKey(
        ListaPrecio,
        on_delete=models.CASCADE,
        related_name="precios"
    )

    precio = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        unique_together = ("variante", "lista")

    def __str__(self):
        return f"{self.variante} - {self.lista.nombre} - ${self.precio:,.0f}"