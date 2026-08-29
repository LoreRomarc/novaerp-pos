# apps/inventory/models_produccion.py
from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.core.exceptions import ValidationError

from apps.core.models import Sucursal
from apps.inventory.models import (
    Color,
    ProductoVariante,
    TipoTela,
)


class RolloTela(models.Model):
    tipo_tela = models.ForeignKey(
        TipoTela,
        on_delete=models.PROTECT,
    )
    color = models.ForeignKey(
        Color,
        on_delete=models.PROTECT,
    )

    codigo = models.CharField(
        max_length=50,
        unique=True,
    )

    cantidad_inicial = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    cantidad_disponible = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    costo_por_metro = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    ESTADOS = (
        ("DISPONIBLE", "Disponible"),
        ("CONSUMIDO", "Consumido"),
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="DISPONIBLE",
    )

    creado = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return (
            f"{self.codigo} - {self.tipo_tela} - {self.color}"
        )


class MovimientoRollo(models.Model):
    TIPOS = (
        ("ENTRADA", "Entrada"),
        ("CONSUMO", "Consumo"),
        ("AJUSTE", "Ajuste"),
    )

    rollo = models.ForeignKey(
        RolloTela,
        on_delete=models.PROTECT,
    )
    tipo = models.CharField(
        max_length=20,
        choices=TIPOS,
    )

    cantidad = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    saldo_post = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    referencia = models.CharField(
        max_length=100,
        null=True,
        blank=True,
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )

    creado = models.DateTimeField(auto_now_add=True)


class OperarioProduccion(models.Model):
    """
    Empleado de planta. No requiere usuario ni contraseña.
    """

    class Especialidad(models.TextChoices):
        CORTADOR = "CORTADOR", "Cortador"
        COSTURERA = "COSTURERA", "Costurera"
        AMBOS = "AMBOS", "Corte y confección"

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="operarios_produccion",
    )

    nombre = models.CharField(max_length=150)

    documento = models.CharField(
        max_length=30,
        blank=True,
        default="",
    )

    especialidad = models.CharField(
        max_length=20,
        choices=Especialidad.choices,
        default=Especialidad.AMBOS,
    )

    activo = models.BooleanField(default=True)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nombre"]
        indexes = [
            models.Index(fields=["sucursal", "activo"]),
            models.Index(fields=["especialidad", "activo"]),
        ]

    def __str__(self):
        return self.nombre


class ProduccionLote(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE_CONFECCION = (
            "PENDIENTE_CONFECCION",
            "Pendiente de confección",
        )
        EN_CONFECCION = (
            "EN_CONFECCION",
            "En confección",
        )
        FINALIZADO = (
            "FINALIZADO",
            "Finalizado e ingresado a inventario",
        )

    numero_corte = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    anio_corte = models.PositiveIntegerField(
        null=True,
        blank=True,
    )

    referencia = models.CharField(
        max_length=100,
        unique=True,
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
    )

    consumo_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )
    consumo_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=6,
    )

    total_prendas = models.IntegerField()

    merma = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    eficiencia = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=100,
    )

    costo_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    costo_unitario_real = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
    )

    # Usuario que registró el corte en el sistema.
    operario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
    )

    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.PENDIENTE_CONFECCION,
        db_index=True,
    )

    # Indica que el corte de tela ya fue ejecutado.
    ejecutado = models.BooleanField(default=False)

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado", "-id"]
        indexes = [
            models.Index(fields=["sucursal", "estado"]),
        ]

    def __str__(self):
        return self.referencia


class CorteRollo(models.Model):
    lote = models.ForeignKey(
        ProduccionLote,
        related_name="rollos",
        on_delete=models.CASCADE,
    )

    rollo = models.ForeignKey(
        RolloTela,
        on_delete=models.PROTECT,
    )

    metros_consumidos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    costo_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    def __str__(self):
        return f"{self.lote.referencia} | {self.rollo.codigo}"


class ProduccionDetalle(models.Model):
    """
    Prendas cortadas por variante.
    `cantidad` es la cantidad total cortada, no inventario vendido.
    """

    lote = models.ForeignKey(
        ProduccionLote,
        related_name="detalles",
        on_delete=models.CASCADE,
    )

    variante = models.ForeignKey(
        ProductoVariante,
        on_delete=models.PROTECT,
    )

    rollo = models.ForeignKey(
        RolloTela,
        on_delete=models.PROTECT,
        related_name="producciones",
    )

    cantidad = models.PositiveIntegerField()

    orden = models.PositiveIntegerField(default=1)

    consumo_unitario = models.DecimalField(
        max_digits=12,
        decimal_places=6,
    )

    consumo_total = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    costo_unitario = models.DecimalField(
        max_digits=14,
        decimal_places=6,
        default=0,
    )

    costo_total = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )

    @property
    def cantidad_confeccionada(self):
        return (
            self.operaciones
            .filter(
                tipo=OperacionProduccion.Tipo.CONFECCION
            )
            .aggregate(total=Sum("cantidad"))["total"]
            or 0
        )

    @property
    def cantidad_pendiente_confeccion(self):
        return self.cantidad - self.cantidad_confeccionada

    def __str__(self):
        return f"{self.variante} x {self.cantidad}"


class OperacionProduccion(models.Model):
    """
    Registro histórico de quién realizó cada operación.
    No maneja pagos; solo cantidades y trazabilidad.
    """

    class Tipo(models.TextChoices):
        CORTE = "CORTE", "Corte"
        CONFECCION = "CONFECCION", "Confección"

    detalle = models.ForeignKey(
        ProduccionDetalle,
        related_name="operaciones",
        on_delete=models.PROTECT,
    )

    operario = models.ForeignKey(
        OperarioProduccion,
        related_name="operaciones",
        on_delete=models.PROTECT,
    )

    tipo = models.CharField(
        max_length=20,
        choices=Tipo.choices,
    )

    cantidad = models.PositiveIntegerField()

    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="operaciones_produccion_registradas",
    )

    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-creado", "-id"]
        indexes = [
            models.Index(fields=["detalle", "tipo"]),
            models.Index(fields=["operario", "creado"]),
            models.Index(fields=["tipo", "creado"]),
        ]

    def clean(self):
        if self.cantidad <= 0:
            raise ValidationError(
                "La cantidad de producción debe ser mayor a cero."
            )

        if (
            self.operario_id
            and self.detalle_id
            and self.operario.sucursal_id
            != self.detalle.lote.sucursal_id
        ):
            raise ValidationError(
                "El operario pertenece a otra sucursal."
            )

    def __str__(self):
        return (
            f"{self.get_tipo_display()} | "
            f"{self.operario} | "
            f"{self.detalle.variante} x {self.cantidad}"
        )