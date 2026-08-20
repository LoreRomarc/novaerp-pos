# apps/sales/models.py

from decimal import Decimal
import uuid

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

    sucursal = models.ForeignKey("core.Sucursal",on_delete=models.PROTECT,related_name="cajas")
    codigo = models.CharField(max_length=20)
    nombre = models.CharField(max_length=100)
    activa = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

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
    turno = models.ForeignKey(TurnoCaja,on_delete=models.CASCADE,related_name="cajeros")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    asignado_en = models.DateTimeField(auto_now_add=True)
    desasignado_en = models.DateTimeField(null=True,blank=True)
    activo = models.BooleanField(default=True)

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
# CARRITO (BORRADOR DE VENTA)
# =========================================================

class Carrito(models.Model):

    ESTADOS = (
        ("BORRADOR", "Borrador"),
        ("CANCELADO", "Cancelado"),
        ("FINALIZADO", "Finalizado"),
    )

    TIPO_VENTA = (
        ("DETAL", "Detal"),
        ("MAYORISTA", "Mayorista"),
    )

    uuid = models.UUIDField( default=uuid.uuid4,editable=False, unique=True, db_index=True, )
    sucursal = models.ForeignKey( "core.Sucursal", on_delete=models.CASCADE, related_name="carritos",)
    usuario = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.CASCADE,related_name="carritos",)
    tipo_venta = models.CharField( max_length=20, choices=TIPO_VENTA, default="MAYORISTA",)
    estado = models.CharField( max_length=20, choices=ESTADOS, default="BORRADOR", db_index=True,)
    cliente = models.CharField( max_length=150, blank=True, default="",)
    observaciones = models.TextField( blank=True, default="",)
    monto_efectivo = models.DecimalField( max_digits=14, decimal_places=2, default=0, )
    monto_tarjeta = models.DecimalField( max_digits=14, decimal_places=2, default=0 )

    monto_transferencia = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    creado = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado = models.DateTimeField(
        auto_now=True,
    )

    class Meta:

        ordering = ["-actualizado"]

        indexes = [
            models.Index(fields=["uuid"]),
            models.Index(fields=["usuario"]),
            models.Index(fields=["sucursal"]),
            models.Index(fields=[
                "usuario",
                "sucursal",
                "estado"
            ]),
        ]

    @property
    def subtotal(self):
        return sum(
            (
                item.subtotal_linea
                for item in self.items.all()
            ),
            Decimal("0"),
        )

    @property
    def total_iva(self):
        return sum(
            (
                item.iva_linea
                for item in self.items.all()
            ),
            Decimal("0"),
        )

    @property
    def total(self):
        return sum(
            (
                item.total_linea
                for item in self.items.all()
            ),
            Decimal("0"),
        )

    @property
    def total_pagado(self):

        return (
            self.monto_efectivo +
            self.monto_tarjeta +
            self.monto_transferencia
        )

# =========================================================
# ITEM DEL CARRITO
# =========================================================

class CarritoItem(models.Model):

    carrito = models.ForeignKey(
        Carrito,
        on_delete=models.CASCADE,
        related_name="items",
    )

    variante = models.ForeignKey(
        "inventory.ProductoVariante",
        on_delete=models.PROTECT,
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=1,
    )

    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    subtotal_linea = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    iva_linea = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    total_linea = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    class Meta:

        indexes = [
            models.Index(fields=["carrito"]),
        ]

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError("La cantidad debe ser mayor a cero.")

        if self.cantidad % 1 != 0:
            raise ValidationError(
                "La cantidad de prendas debe ser un número entero."
            )

        if self.precio_unitario <= 0:
            raise ValidationError("El precio debe ser mayor a cero.")

    def save(self, *args, **kwargs):

        self.clean()

        precio = redondear_a_peso_colombiano(
            self.precio_unitario
        )

        base = redondear_a_peso_colombiano(
            precio * self.cantidad
        )

        iva = Decimal("0")

        self.subtotal_linea = base
        self.iva_linea = iva
        self.total_linea = base + iva

        super().save(*args, **kwargs)
        
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

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
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

    cliente = models.CharField(
        max_length=150,
        blank=True,
        null=True
    )

    observaciones = models.TextField(
        blank=True,
        null=True
    )

    tipo_venta = models.CharField(
        max_length=20,
        choices=TIPO_VENTA,
        default="MAYORISTA"
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

        constraints = []

        indexes = [
            models.Index(fields=["uuid"]),
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
                "El pago no cubre el total de la venta."
            )

        # -----------------------------------------------------
        # VALIDAR TURNO
        # -----------------------------------------------------

        from apps.sales.services.caja_service import CajaService

        turno = CajaService.obtener_turno_bloqueado(
            self.turno_id,
            sucursal=self.sucursal,
        )

        CajaService.validar_operador_turno(
            turno,
            self.usuario,
        )

        # -----------------------------------------------------
        # INVENTARIO
        # -----------------------------------------------------

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
                    tipo="VENTA",
                )

            self.stock_descontado = True

        # -----------------------------------------------------
        # CERRAR VENTA
        # -----------------------------------------------------

        self.estado = "CERRADA"
        self.cerrada = timezone.now()

        self.save(
            update_fields=[
                "estado",
                "cerrada",
                "stock_descontado",
            ]
        )

        # -----------------------------------------------------
        # REGISTRO FINANCIERO
        # -----------------------------------------------------

        CajaService.registrar_movimientos_venta(
            venta=self,
            usuario=self.usuario,
            pagos={
                "EFECTIVO": self.monto_efectivo,
                "TARJETA": self.monto_tarjeta,
                "TRANSFERENCIA": self.monto_transferencia,
            },
        )

        return self


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
                self.variante.talla.nombre
                if self.variante.talla else ""
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
# DEVOLUCIONES Y CAMBIOS
# =========================================================

class Devolucion(models.Model):
    """
    Comprobante de una devolución parcial o cambio.
    La venta original NO se modifica ni se elimina.
    """

    class Tipo(models.TextChoices):
        DEVOLUCION = "DEVOLUCION", "Devolución"
        CAMBIO = "CAMBIO", "Cambio de prenda"

    uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        db_index=True,
    )

    venta = models.ForeignKey(
        Venta,
        on_delete=models.PROTECT,
        related_name="devoluciones",
        null=True,
        blank=True,
    )

    referencia_externa = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text=(
            "Factura, nota o referencia opcional "
            "proporcionada por el cliente."
        ),
    )

    tipo_venta = models.CharField(
        max_length=20,
        choices=Venta.TIPO_VENTA,
        default="MAYORISTA",
    )

    sucursal = models.ForeignKey(
        "core.Sucursal",
        on_delete=models.PROTECT,
        related_name="devoluciones",
    )

    turno = models.ForeignKey(
        "sales.TurnoCaja",
        on_delete=models.PROTECT,
        related_name="devoluciones",
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="devoluciones_procesadas",
    )

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
    )

    motivo = models.TextField()

    # Si es False, el cliente puede aceptar una prenda
    # más barata sin recibir dinero.
    permite_reembolso = models.BooleanField(
        default=False,
    )

    medio_reembolso = models.CharField(
        max_length=20,
        blank=True,
        default="",
    )

    # Valor de prendas que entrega el cliente.
    total_devuelto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    # Valor de prendas nuevas que se lleva el cliente.
    total_entregado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    # total_entregado - total_devuelto
    # Positivo: cliente paga.
    # Negativo: existe saldo a favor del cliente.
    diferencia = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    # Dinero adicional cobrado al cliente si lleva
    # una prenda de mayor valor.
    monto_cobrado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    # Dinero realmente devuelto al cliente.
    monto_reembolsado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    # Diferencia que el cliente acepta no recibir.
    monto_no_reembolsado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creada", "-id"]

        indexes = [
            models.Index(fields=["sucursal", "creada"]),
            models.Index(fields=["venta", "creada"]),
            models.Index(fields=["turno"]),
        ]

    def clean(self):
        if (
            self.venta_id
            and self.sucursal_id
            and self.sucursal_id != self.venta.sucursal_id
        ):
            raise ValidationError(
                "La devolución debe pertenecer a la sucursal de la venta."
            )

        if (
            self.turno_id
            and self.sucursal_id
            and self.sucursal_id != self.turno.sucursal_id
        ):
            raise ValidationError(
                "El turno de caja pertenece a otra sucursal."
            )

    def __str__(self):
        origen = (
            f"Venta #{self.venta_id}"
            if self.venta_id
            else "Cambio directo"
        )

        return (
            f"{self.get_tipo_display()} #{self.id} "
            f"- {origen}"
        )


class DevolucionDetalle(models.Model):
    """
    Prenda que el cliente entrega.
    APTA: entra nuevamente a stock.
    DANADA: se registra devolución y baja por daño.
    """

    class EstadoPrenda(models.TextChoices):
        APTA = "APTA", "Apta para la venta"
        DANADA = "DANADA", "Dañada / no apta para la venta"

    devolucion = models.ForeignKey(
        Devolucion,
        on_delete=models.PROTECT,
        related_name="items_devueltos",
    )

    venta_item = models.ForeignKey(
        VentaItem,
        on_delete=models.PROTECT,
        related_name="devoluciones",
        null=True,
        blank=True,
    )

    variante = models.ForeignKey(
        "inventory.ProductoVariante",
        on_delete=models.PROTECT,
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    estado_prenda = models.CharField(
        max_length=12,
        choices=EstadoPrenda.choices,
    )

    # Precio que el cliente pagó en la venta original.
    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    precio_modificado = models.BooleanField(
        default=False,
    )

    motivo_precio = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["devolucion", "venta_item"],
                name="unique_item_por_devolucion",
            )
        ]

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError(
                "La cantidad devuelta debe ser mayor a cero."
            )

        if self.cantidad % 1 != 0:
            raise ValidationError(
                "La cantidad de prendas devueltas debe ser entera."
            )

        if (
            self.venta_item_id
            and self.variante_id != self.venta_item.variante_id
        ):
            raise ValidationError(
                "La variante devuelta no coincide con el ítem vendido."
            )

        if self.precio_modificado and not self.motivo_precio.strip():
            raise ValidationError(
                "Debe indicar el motivo de la modificación de precio."
            )

    def __str__(self):
        return (
            f"Devolución #{self.devolucion_id} - "
            f"{self.variante} x {self.cantidad}"
        )


class CambioDetalle(models.Model):
    """
    Prenda nueva que el cliente se lleva durante el cambio.
    """

    devolucion = models.ForeignKey(
        Devolucion,
        on_delete=models.PROTECT,
        related_name="items_entregados",
    )

    variante = models.ForeignKey(
        "inventory.ProductoVariante",
        on_delete=models.PROTECT,
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    precio_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    precio_modificado = models.BooleanField(default=False)

    motivo_precio = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError(
                "La cantidad entregada debe ser mayor a cero."
            )

        if self.cantidad % 1 != 0:
            raise ValidationError(
                "La cantidad de prendas entregadas debe ser entera."
            )

        if self.precio_modificado and not self.motivo_precio.strip():
            raise ValidationError(
                "Debe indicar el motivo de la modificación de precio."
            )

    def __str__(self):
        return (
            f"Cambio #{self.devolucion_id} - "
            f"{self.variante} x {self.cantidad}"
        )

    
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
