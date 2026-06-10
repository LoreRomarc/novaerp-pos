# apps/sales/models.py

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from apps.inventory.services.stock_service import InventoryService
from apps.sales.models_caja_enterprise import TurnoCaja


# =========================================================
# HELPERS
# =========================================================

def redondear_a_peso_colombiano(valor: Decimal) -> Decimal:
    """
    Redondea al múltiplo de 100 más cercano.
    Ajusta según necesidad del negocio.
    """

    valor = Decimal(valor or 0)

    return (
        (valor / Decimal("100"))
        .quantize(Decimal("1"))
        * Decimal("100")
    )


# =========================================================
# CAJA FÍSICA
# =========================================================

class Caja(models.Model):

    sucursal = models.ForeignKey(
        "core.Sucursal",
        on_delete=models.PROTECT,
        related_name="cajas"
    )

    codigo = models.CharField(
        max_length=20
    )

    nombre = models.CharField(
        max_length=100
    )

    activa = models.BooleanField(
        default=True
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        ordering = ["codigo"]

        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "codigo"],
                name="unique_caja_codigo_por_sucursal"
            )
        ]

        indexes = [
            models.Index(fields=["sucursal", "activa"]),
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

    asignado_en = models.DateTimeField(
        auto_now_add=True
    )

    desasignado_en = models.DateTimeField(
        null=True,
        blank=True
    )

    activo = models.BooleanField(
        default=True
    )

    class Meta:

        ordering = ["-asignado_en"]

        constraints = [
            models.UniqueConstraint(
                fields=["turno", "usuario"],
                condition=Q(activo=True),
                name="unique_usuario_activo_por_turno"
            )
        ]

        indexes = [
            models.Index(fields=["activo"]),
        ]

    def __str__(self):
        return f"{self.usuario} - {self.turno}"


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

    sucursal = models.ForeignKey(
        "core.Sucursal",
        on_delete=models.PROTECT,
        related_name="ventas"
    )

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

    tipo_venta = models.CharField(
        max_length=20,
        choices=TIPO_VENTA,
        default="DETAL"
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="ABIERTA"
    )

    # =====================================================
    # TOTALES
    # =====================================================

    subtotal = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    total_iva = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    # =====================================================
    # PAGOS
    # =====================================================

    monto_efectivo = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    monto_tarjeta = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    monto_transferencia = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    ajuste_redondeo = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    # =====================================================
    # CONTROL INVENTARIO
    # =====================================================

    stock_descontado = models.BooleanField(
        default=False
    )

    # =====================================================
    # FECHAS
    # =====================================================

    creada = models.DateTimeField(
        auto_now_add=True
    )

    cerrada = models.DateTimeField(
        null=True,
        blank=True
    )

    anulada = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:

        ordering = ["-creada", "-id"]

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
            models.Index(fields=["estado"]),
            models.Index(fields=["creada"]),
        ]

    def __str__(self):

        return (
            f"Venta #{self.id} - "
            f"{self.sucursal.nombre} - "
            f"Total: ${self.total:,.0f}"
        )

    # =====================================================
    # CÁLCULOS
    # =====================================================

    def recalcular_totales(self):

        totales = self.items.aggregate(
            subtotal=Sum("subtotal_linea"),
            iva=Sum("iva_linea"),
            total=Sum("total_linea"),
        )

        self.subtotal = redondear_a_peso_colombiano(
            totales["subtotal"] or Decimal("0")
        )

        self.total_iva = redondear_a_peso_colombiano(
            totales["iva"] or Decimal("0")
        )

        self.total = redondear_a_peso_colombiano(
            totales["total"] or Decimal("0")
        )

        self.save(
            update_fields=[
                "subtotal",
                "total_iva",
                "total"
            ]
        )

    @property
    def total_pagado(self):

        return (
            self.monto_efectivo +
            self.monto_tarjeta +
            self.monto_transferencia
        )

    @property
    def saldo_pendiente(self):

        saldo = self.total - self.total_pagado

        if saldo < 0:
            return Decimal("0")

        return saldo

    @property
    def cambio(self):

        excedente = self.total_pagado - self.total

        if excedente < 0:
            return Decimal("0")

        return excedente

    def puede_cerrar(self):

        return (
            self.estado == "ABIERTA"
            and self.items.exists()
            and self.total_pagado >= self.total
        )

    # =====================================================
    # CIERRE DE VENTA
    # =====================================================

    @transaction.atomic
    def cerrar_venta(self):

        if self.estado != "ABIERTA":
            raise ValidationError(
                "La venta no está abierta."
            )

        if not self.items.exists():
            raise ValidationError(
                "La venta no tiene items."
            )

        self.recalcular_totales()

        if not self.puede_cerrar():
            raise ValidationError(
                "El pago no cubre el total."
            )

        # =================================================
        # DESCONTAR INVENTARIO
        # =================================================

        if not self.stock_descontado:

            for item in (
                self.items
                .select_related("variante")
            ):

                InventoryService.descontar_stock(
                    variante=item.variante,
                    cantidad=item.cantidad,
                    user=self.usuario,
                    sucursal_id=self.sucursal_id,
                    referencia=f"VENTA-{self.id}",
                    tipo="VENTA"
                )

            self.stock_descontado = True

        # =================================================
        # CERRAR
        # =================================================

        self.estado = "CERRADA"

        self.cerrada = timezone.now()

        self.save(
            update_fields=[
                "estado",
                "cerrada",
                "stock_descontado",
            ]
        )

    # =====================================================
    # ANULAR VENTA
    # =====================================================

    @transaction.atomic
    def anular_venta(self):

        if self.estado == "ANULADA":
            raise ValidationError(
                "La venta ya fue anulada."
            )

        # =================================================
        # DEVOLVER INVENTARIO
        # =================================================

        if self.stock_descontado:

            for item in (
                self.items
                .select_related("variante")
            ):

                InventoryService.agregar_stock(
                    variante=item.variante,
                    cantidad=item.cantidad,
                    user=self.usuario,
                    sucursal_id=self.sucursal_id,
                    referencia=f"ANULACION-{self.id}",
                    tipo="ANULACION"
                )

        self.estado = "ANULADA"

        self.anulada = timezone.now()

        self.save(
            update_fields=[
                "estado",
                "anulada"
            ]
        )


# =========================================================
# VENTA ITEM
# =========================================================

class VentaItem(models.Model):

    venta = models.ForeignKey(
        "sales.Venta",
        on_delete=models.CASCADE,
        related_name="items"
    )

    variante = models.ForeignKey(
        "inventory.ProductoVariante",
        on_delete=models.PROTECT
    )

    # =====================================================
    # SNAPSHOT HISTÓRICO
    # =====================================================

    nombre_producto = models.CharField(
        max_length=300,
        blank=True,
        default=""
    )

    sku = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    color = models.CharField(
        max_length=50,
        blank=True,
        default=""
    )

    talla = models.CharField(
        max_length=20,
        blank=True,
        default=""
    )

    tipo_tela = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    # =====================================================
    # CANTIDADES
    # =====================================================

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1
    )

    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )

    subtotal_linea = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    iva_linea = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    total_linea = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

    class Meta:

        ordering = ["id"]

        indexes = [
            models.Index(fields=["venta"]),
            models.Index(fields=["sku"]),
        ]

    @property
    def subtotal_calculado(self):

        return (
            self.cantidad *
            self.precio_unitario
        )

    def __str__(self):

        return (
            f"{self.nombre_producto} "
            f"{self.talla} "
            f"x {self.cantidad}"
        )

    def clean(self):

        if self.cantidad <= 0:
            raise ValidationError(
                "Cantidad debe ser mayor a 0."
            )

        if self.precio_unitario <= 0:
            raise ValidationError(
                "Precio inválido."
            )

    def save(self, *args, **kwargs):

        if (
            self.venta_id and
            self.venta.estado != "ABIERTA"
        ):
            raise ValidationError(
                "No se puede modificar una venta cerrada."
            )

        self.clean()

        # =================================================
        # CÁLCULOS
        # =================================================

        precio = redondear_a_peso_colombiano(
            self.precio_unitario
        )

        base = redondear_a_peso_colombiano(
            precio * self.cantidad
        )

        iva = Decimal("0.00")

        total = base + iva

        self.subtotal_linea = base
        self.iva_linea = iva
        self.total_linea = total

        # =================================================
        # SNAPSHOT HISTÓRICO
        # =================================================

        if self.variante:

            self.nombre_producto = (
                self.variante.producto_base.nombre
            )

            self.sku = (
                self.variante.sku
            )

            self.color = (
                self.variante.color.nombre
                if self.variante.color else ""
            )

            self.talla = (
                self.variante.talla or ""
            )

            self.tipo_tela = (
                self.variante.tipo_tela.nombre
                if self.variante.tipo_tela else ""
            )

        super().save(*args, **kwargs)

        # =================================================
        # RECALCULAR VENTA
        # =================================================

        if self.venta_id:
            self.venta.recalcular_totales()

    def delete(self, *args, **kwargs):

        venta = self.venta

        super().delete(*args, **kwargs)

        if venta:
            venta.recalcular_totales()


# =========================================================
# LISTA DE PRECIOS
# =========================================================

class ListaPrecio(models.Model):

    sucursal = models.ForeignKey(
        "core.Sucursal",
        on_delete=models.CASCADE,
        related_name="listas_precios",
    )

    nombre = models.CharField(
        max_length=100
    )

    tipo_venta = models.CharField(
        max_length=20,
        choices=Venta.TIPO_VENTA
    )

    activa = models.BooleanField(
        default=True
    )

    creada = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        ordering = ["nombre"]

        constraints = [
            models.UniqueConstraint(
                fields=["sucursal", "tipo_venta"],
                name="unique_lista_por_sucursal_tipo"
            )
        ]

        indexes = [
            models.Index(fields=["sucursal", "activa"]),
        ]

    def __str__(self):

        return (
            f"{self.sucursal} - {self.nombre}"
        )


# =========================================================
# PRECIO POR VARIANTE
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

    precio = models.DecimalField(
        max_digits=14,
        decimal_places=2
    )

    class Meta:

        ordering = ["variante"]

        unique_together = (
            "variante",
            "lista"
        )

        indexes = [
            models.Index(fields=["lista"]),
            models.Index(fields=["variante"]),
        ]

    def clean(self):

        if self.precio <= 0:
            raise ValidationError(
                "Precio inválido."
            )

    def __str__(self):

        return (
            f"{self.variante} - "
            f"{self.lista.nombre} - "
            f"${self.precio:,.0f}"
        )