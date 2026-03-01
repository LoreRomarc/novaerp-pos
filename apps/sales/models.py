# apps/sales/models.py

from decimal import ROUND_HALF_UP, Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum
from django.utils import timezone
from django.conf import settings

from apps.inventory.models import MovimientoStock, Producto, Stock
from apps.sales.models_caja_enterprise import TurnoCaja


def redondear_2(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def redondear_peso(valor: Decimal) -> Decimal:
    return valor.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


# =========================================================
# CAJA FÍSICA
# =========================================================

class Caja(models.Model):
    """
    Representa el hardware físico.
    Ej: Caja 01 - POS Frente Tienda
    """

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
# CAJERO EN TURNO
# =========================================================

class TurnoCajaUsuario(models.Model):
    """
    Permite múltiples cajeros en el mismo turno.
    """

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
    """
    Modelo transaccional principal del POS.

    Flujo:
    ABIERTA -> CERRADA -> (ANULADA opcional)

    La venta solo descuenta stock al cerrarse.
    """

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
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="ventas")

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

    ajuste_redondeo = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0
    )

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
        # Ejemplo: "Venta #123 - Sucursal Soledad - Total: $123.456"
        total_formato = f"${self.total:,.0f}"
        return f"Venta #{self.id} - {self.sucursal.nombre} - Total: {total_formato} - Estado: {self.estado}"
    
    # =========================================================
    # CÁLCULOS
    # =========================================================

    def recalcular_totales(self):

        totales = self.items.aggregate(
            subtotal=Sum("subtotal_linea"),
            iva=Sum("iva_linea"),
            total=Sum("total_linea"),
        )

        subtotal = totales["subtotal"] or Decimal("0.00")
        iva = totales["iva"] or Decimal("0.00")
        total = totales["total"] or Decimal("0.00")

        # Redondeo final de agregados
        self.subtotal = redondear_2(subtotal)
        self.total_iva = redondear_2(iva)
        self.total = redondear_2(total)

        self.save(update_fields=["subtotal", "total_iva", "total"])

    def total_pagado(self):
        return (
            self.monto_efectivo +
            self.monto_transferencia +
            self.monto_tarjeta
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
        """
        - Valida pagos
        - Descuenta stock
        - Marca como cerrada
        """

        if not self.puede_cerrar():
            raise ValidationError("El pago no cubre el total.")

        for item in self.items.select_related("producto").select_for_update():

            if item.producto.controla_stock:

                stock = Stock.objects.select_for_update().get(
                    producto=item.producto,
                    sucursal=self.sucursal
                )

                if stock.cantidad < item.cantidad:
                    raise ValidationError(
                        f"Stock insuficiente para {item.producto.nombre}"
                    )

                stock.cantidad -= item.cantidad
                stock.save(update_fields=["cantidad"])

                MovimientoStock.objects.create(
                    producto=item.producto,
                    sucursal=self.sucursal,
                    tipo="VENTA",
                    cantidad=item.cantidad,
                    referencia=self.id
                )

        self.estado = "CERRADA"
        self.cerrada = timezone.now()

        self.save(update_fields=["estado", "cerrada"])


# =========================================================
# VENTA ITEM
# =========================================================
class VentaItem(models.Model):

    venta = models.ForeignKey(Venta, related_name="items", on_delete=models.CASCADE)
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)

    cantidad = models.DecimalField(max_digits=12, decimal_places=2)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    tasa_iva_aplicada = models.DecimalField(max_digits=6,decimal_places=4,default=0)
    tipo_iva_aplicado = models.CharField( max_length=20,blank=True)

    subtotal_linea = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    iva_linea = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_linea = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        # Formatear números con $ y separador de miles
        def format_cop(valor):
            return "${:,.0f}".format(valor)

        return (
            f"[Venta #{self.venta.id}] {self.producto.nombre} - "
            f"{self.cantidad} x {format_cop(self.precio_unitario)} = {format_cop(self.total_linea)}"
        )

    def save(self, *args, **kwargs):

        if self.venta.estado != "ABIERTA":
            raise ValidationError("No se puede modificar una venta cerrada.")

        producto = self.producto
        tasa = producto.tasa_iva()

        self.tasa_iva_aplicada = tasa
        self.tipo_iva_aplicado = producto.tipo_iva

        # 1. Precio unitario normalizado
        precio = redondear_2(self.precio_unitario)

        # 2. Base imponible
        base = redondear_2(precio * self.cantidad)

        # 3. Cálculo IVA por línea
        if producto.tipo_iva in ["EXENTO", "NO_SUJETO"]:
            iva = Decimal("0.00")
            total = base
        else:
            iva = redondear_2(base * tasa)
            total = redondear_2(base + iva)

        self.subtotal_linea = base
        self.iva_linea = iva
        self.total_linea = total

        super().save(*args, **kwargs)

class ListaPrecio(models.Model):

    sucursal = models.ForeignKey(
        "core.Sucursal",
        on_delete=models.CASCADE,
        related_name="listas_precios",         
    )

    nombre = models.CharField(max_length=100)

    tipo_venta = models.CharField(max_length=20,choices=Venta.TIPO_VENTA)

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
    



class PrecioProducto(models.Model):

    producto = models.ForeignKey(
        Producto,
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
        unique_together = ("producto", "lista")
        indexes = [
            models.Index(fields=["producto", "lista"])
        ]

    def __str__(self):
        precio_formateado = f"${self.precio:,.0f}"
        return f"{self.producto.nombre} - {self.lista.nombre} - {precio_formateado}"