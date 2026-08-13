# apps/sales/models_caja_enterprise.py
from __future__ import annotations

import hashlib
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils import timezone


class Boveda(models.Model):
    sucursal = models.OneToOneField(
        "core.Sucursal",
        on_delete=models.PROTECT,
        related_name="boveda",
    )
    saldo_actual = models.DecimalField(
        max_digits=16,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    actualizada_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bóveda"
        verbose_name_plural = "Bóvedas"

    def __str__(self):
        return f"Bóveda - {self.sucursal}"


class TurnoCaja(models.Model):
    class Estado(models.TextChoices):
        ABIERTO = "ABIERTO", "Abierto"
        CERRADO_CAJERO = "CERRADO_CAJERO", "Cerrado por cajero"
        CERRADO_SUPERVISOR = "CERRADO_SUPERVISOR", "Cerrado por supervisor"
        AUDITADO = "AUDITADO", "Auditado"

    caja = models.ForeignKey(
        "sales.Caja",
        on_delete=models.PROTECT,
        related_name="turnos",
    )

    sucursal = models.ForeignKey(
        "core.Sucursal",
        on_delete=models.PROTECT,
        related_name="turnos_caja",
    )

    usuario_apertura = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="turnos_apertura_caja",
    )

    usuario_supervisor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="turnos_supervisados_caja",
    )

    monto_inicial = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    estado = models.CharField(
        max_length=30,
        choices=Estado.choices,
        default=Estado.ABIERTO,
        db_index=True,
    )

    abierto_en = models.DateTimeField(
        auto_now_add=True
    )

    cerrado_en = models.DateTimeField(
        null=True,
        blank=True,
    )

    cerrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cierres_turnos_caja",
    )

    monto_esperado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    monto_real = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    diferencia = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    observacion_cierre = models.TextField(
        blank=True,
        default="",
    )

    auditado_en = models.DateTimeField(
        null=True,
        blank=True,
    )

    auditado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="turnos_auditados_caja",
    )

    class Meta:
        ordering = ["-abierto_en"]

        constraints = [
            models.UniqueConstraint(
                fields=["caja"],
                condition=Q(
                    estado="ABIERTO"
                ),
                name="unique_turno_abierto_por_caja",
            ),

            models.UniqueConstraint(
                fields=["usuario_apertura"],
                condition=Q(
                    estado="ABIERTO"
                ),
                name="unique_turno_abierto_por_usuario",
            ),

            models.CheckConstraint(
                condition=Q(
                    monto_inicial__gte=0
                ),
                name="turno_monto_inicial_no_negativo",
            ),

            models.CheckConstraint(
                condition=Q(
                    monto_esperado__gte=0
                ),
                name="turno_monto_esperado_no_negativo",
            ),

            models.CheckConstraint(
                condition=Q(
                    monto_real__gte=0
                ),
                name="turno_monto_real_no_negativo",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "sucursal",
                    "estado",
                ]
            ),

            models.Index(
                fields=[
                    "usuario_apertura",
                    "estado",
                ]
            ),

            models.Index(
                fields=[
                    "caja",
                    "abierto_en",
                ]
            ),
        ]

    @property
    def esta_abierto(self):
        return (
            self.estado
            == self.Estado.ABIERTO
        )

    @property
    def esta_cerrado(self):
        return self.estado in {
            self.Estado.CERRADO_CAJERO,
            self.Estado.CERRADO_SUPERVISOR,
            self.Estado.AUDITADO,
        }

    def clean(self):
        super().clean()

        if (
            self.caja_id
            and self.sucursal_id
            and self.caja.sucursal_id
            != self.sucursal_id
        ):
            raise ValidationError(
                {
                    "sucursal": (
                        "La caja debe pertenecer "
                        "a la sucursal del turno."
                    )
                }
            )

        if self.monto_inicial < 0:
            raise ValidationError(
                {
                    "monto_inicial": (
                        "La base inicial no puede ser negativa."
                    )
                }
            )

    def cerrar(
        self,
        monto_real,
        monto_esperado,
        diferencia,
        usuario,
    ):
        if not self.esta_abierto:
            raise ValidationError(
                "El turno ya está cerrado."
            )

        monto_real = Decimal(
            str(monto_real)
        )

        monto_esperado = Decimal(
            str(monto_esperado)
        )

        diferencia = Decimal(
            str(diferencia)
        )

        if monto_real < 0:
            raise ValidationError(
                "El monto real no puede ser negativo."
            )

        if monto_esperado < 0:
            raise ValidationError(
                "El monto esperado no puede ser negativo."
            )

        self.estado = (
            self.Estado.CERRADO_CAJERO
        )

        self.cerrado_en = timezone.now()
        self.cerrado_por = usuario
        self.monto_real = monto_real
        self.monto_esperado = monto_esperado
        self.diferencia = diferencia

        self.save(
            update_fields=[
                "estado",
                "cerrado_en",
                "cerrado_por",
                "monto_real",
                "monto_esperado",
                "diferencia",
            ]
        )

    def __str__(self):
        return (
            f"{self.caja.codigo} - "
            f"{self.get_estado_display()}"
        )


class MovimientoInmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Los movimientos de caja son inmutables.")

    def delete(self):
        raise ValidationError("Los movimientos de caja no se pueden eliminar.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Los movimientos de caja no se pueden modificar masivamente.")

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        raise ValidationError("Los movimientos de caja deben crearse individualmente.")


class MovimientoInmutableManager(models.Manager.from_queryset(MovimientoInmutableQuerySet)):
    pass


class CajaMovimiento(models.Model):

    class Tipo(models.TextChoices):
        APERTURA = "APERTURA", "Apertura"
        VENTA = "VENTA", "Venta"
        RETIRO_BOVEDA = "RETIRO_BOVEDA", "Retiro a bóveda"
        INGRESO = "INGRESO", "Ingreso manual"
        EGRESO = "EGRESO", "Egreso manual"
        AJUSTE = "AJUSTE", "Ajuste"
        DEVOLUCION = "DEVOLUCION", "Devolución"

    class MedioPago(models.TextChoices):
        EFECTIVO = "EFECTIVO", "Efectivo"
        TARJETA = "TARJETA", "Tarjeta"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"
        QR = "QR", "QR"

    turno = models.ForeignKey(
        TurnoCaja,
        on_delete=models.PROTECT,
        related_name="movimientos",
    )

    sucursal = models.ForeignKey(
        "core.Sucursal",
        on_delete=models.PROTECT,
        related_name="movimientos_caja",
        editable=False,
    )

    caja = models.ForeignKey(
        "sales.Caja",
        on_delete=models.PROTECT,
        related_name="movimientos",
        editable=False,
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimientos_caja",
    )

    tipo = models.CharField(
        max_length=30,
        choices=Tipo.choices,
    )

    medio_pago = models.CharField(
        max_length=20,
        choices=MedioPago.choices,
        null=True,
        blank=True,
    )

    monto = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    observacion = models.TextField(
        blank=True,
        default="",
    )

    referencia_venta = models.ForeignKey(
        "sales.Venta",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="movimientos_caja",
    )

    numero_secuencia = models.PositiveIntegerField(
        null=True,
        blank=True,
        editable=False,
    )

    hash_anterior = models.CharField(
        max_length=64,
        editable=False,
        default="GENESIS",
    )

    hash_integridad = models.CharField(
        max_length=64,
        editable=False,
        db_index=True,
    )

    creado_en = models.DateTimeField(
        default=timezone.now,
        editable=False,
    )

    objects = MovimientoInmutableManager()

    class Meta:
        ordering = [
            "-creado_en",
            "-id",
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(monto__gt=0)
                    | Q(
                        tipo="APERTURA",
                        monto=0,
                    )
                ),
                name="movimiento_caja_monto_valido",
            ),

            models.UniqueConstraint(
                fields=[
                    "turno",
                    "numero_secuencia",
                ],
                name="unique_movimiento_numero_por_turno",
            ),

            models.UniqueConstraint(
                fields=[
                    "referencia_venta",
                    "medio_pago",
                ],
                condition=Q(
                    tipo="VENTA"
                ),
                name="unique_movimiento_venta_por_medio",
            ),
        ]

        indexes = [
            models.Index(
                fields=[
                    "turno",
                    "tipo",
                ]
            ),

            models.Index(
                fields=[
                    "turno",
                    "numero_secuencia",
                ]
            ),

            models.Index(
                fields=[
                    "sucursal",
                    "creado_en",
                ]
            ),

            models.Index(
                fields=[
                    "caja",
                    "creado_en",
                ]
            ),

            models.Index(
                fields=[
                    "referencia_venta",
                ]
            ),
        ]

    def clean(self):
        super().clean()

        if self.monto < 0:
            raise ValidationError(
                {
                    "monto": (
                        "El monto no puede ser negativo."
                    )
                }
            )

        if (
            self.tipo != self.Tipo.APERTURA
            and self.monto <= 0
        ):
            raise ValidationError(
                {
                    "monto": (
                        "El monto debe ser mayor que cero."
                    )
                }
            )

        if self.turno_id:
            turno = self.turno

            if (
                self.sucursal_id
                and turno.sucursal_id
                != self.sucursal_id
            ):
                raise ValidationError(
                    {
                        "sucursal": (
                            "La sucursal no coincide "
                            "con la del turno."
                        )
                    }
                )

            if (
                self.caja_id
                and turno.caja_id
                != self.caja_id
            ):
                raise ValidationError(
                    {
                        "caja": (
                            "La caja no coincide "
                            "con la del turno."
                        )
                    }
                )

        if self.tipo == self.Tipo.VENTA:
            if not self.referencia_venta_id:
                raise ValidationError(
                    {
                        "referencia_venta": (
                            "Una venta debe tener "
                            "referencia."
                        )
                    }
                )

            if not self.medio_pago:
                raise ValidationError(
                    {
                        "medio_pago": (
                            "Una venta debe indicar "
                            "medio de pago."
                        )
                    }
                )

        if self.tipo == self.Tipo.DEVOLUCION:
            if not self.referencia_venta_id:
                raise ValidationError(
                    {
                        "referencia_venta": (
                            "La devolución debe "
                            "referenciar una venta."
                        )
                    }
                )

        if self.referencia_venta_id:
            venta = self.referencia_venta

            if (
                self.sucursal_id
                and venta.sucursal_id
                != self.sucursal_id
            ):
                raise ValidationError(
                    {
                        "referencia_venta": (
                            "La venta pertenece "
                            "a otra sucursal."
                        )
                    }
                )

            if (
                self.tipo
                not in {
                    self.Tipo.DEVOLUCION,
                }
                and venta.turno_id
                != self.turno_id
            ):
                raise ValidationError(
                    {
                        "referencia_venta": (
                            "La venta debe pertenecer "
                            "al mismo turno."
                        )
                    }
                )

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError(
                "Los movimientos de caja son inmutables."
            )

        if not self.turno_id:
            raise ValidationError(
                "El turno es obligatorio."
            )

        turno = (
            TurnoCaja.objects
            .select_for_update()
            .select_related(
                "caja",
                "sucursal",
            )
            .get(pk=self.turno_id)
        )

        self.sucursal_id = turno.sucursal_id
        self.caja_id = turno.caja_id
        self.creado_en = timezone.now()

        ultimo = (
            CajaMovimiento.objects
            .filter(
                turno_id=turno.id
            )
            .order_by(
                "-numero_secuencia",
                "-id",
            )
            .first()
        )

        self.numero_secuencia = (
            (ultimo.numero_secuencia or 0) + 1
            if ultimo
            else 1
        )

        self.hash_anterior = (
            ultimo.hash_integridad
            if ultimo
            else "GENESIS"
        )

        self.full_clean(
            exclude=[
                "numero_secuencia",
                "hash_anterior",
                "hash_integridad",
            ]
        )

        cadena = "|".join(
            [
                self.hash_anterior,
                str(self.turno_id),
                str(self.numero_secuencia),
                str(self.sucursal_id),
                str(self.caja_id),
                str(self.usuario_id),
                self.tipo,
                self.medio_pago or "",
                str(self.monto),
                str(
                    self.referencia_venta_id
                    or ""
                ),
                self.observacion,
                self.creado_en.isoformat(),
            ]
        )

        self.hash_integridad = hashlib.sha256(
            cadena.encode("utf-8")
        ).hexdigest()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(
            "Los movimientos de caja no se pueden eliminar."
        )

    def __str__(self):
        return (
            f"{self.get_tipo_display()} "
            f"#{self.id} - ${self.monto}"
        )


class BovedaMovimiento(models.Model):
    class Tipo(models.TextChoices):
        RETIRO_CAJA = "RETIRO_CAJA", "Retiro desde caja"
        INGRESO_EXTERNO = "INGRESO_EXTERNO", "Ingreso externo"
        EGRESO_BOVEDA = "EGRESO_BOVEDA", "Egreso de bóveda"
        AJUSTE = "AJUSTE", "Ajuste de bóveda"

    boveda = models.ForeignKey(
        Boveda,
        on_delete=models.PROTECT,
        related_name="movimientos",
    )
    turno = models.ForeignKey(
        TurnoCaja,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimientos_boveda",
    )
    movimiento_caja = models.OneToOneField(
        CajaMovimiento,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="movimiento_boveda",
    )
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="movimientos_boveda",
    )
    tipo = models.CharField(max_length=30, choices=Tipo.choices)
    monto = models.DecimalField(max_digits=14, decimal_places=2)
    observacion = models.TextField(blank=True, default="")
    numero_secuencia = models.PositiveIntegerField(
        null=True,
        blank=True,
        editable=False,
    )
    hash_anterior = models.CharField(
        max_length=64,
        editable=False,
        default="GENESIS",
    )
    hash_integridad = models.CharField(
        max_length=64,
        editable=False,
        db_index=True,
    )
    creado_en = models.DateTimeField(default=timezone.now, editable=False)

    objects = MovimientoInmutableManager()

    class Meta:
        ordering = ["-creado_en", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(monto__gt=0),
                name="movimiento_boveda_monto_positivo",
            ),
            models.UniqueConstraint(
                fields=["boveda", "numero_secuencia"],
                name="unique_movimiento_boveda_numero",
            ),
        ]
        indexes = [
            models.Index(fields=["boveda", "numero_secuencia"]),
            models.Index(fields=["boveda", "creado_en"]),
            models.Index(fields=["turno", "creado_en"]),
        ]

    def clean(self):
        super().clean()

        if (
            self.turno_id
            and self.boveda_id
            and self.turno.sucursal_id != self.boveda.sucursal_id
        ):
            raise ValidationError(
                {"boveda": "La bóveda debe pertenecer a la sucursal del turno."}
            )

        if (
            self.movimiento_caja_id
            and self.boveda_id
            and self.movimiento_caja.sucursal_id != self.boveda.sucursal_id
        ):
            raise ValidationError(
                {
                    "movimiento_caja": (
                        "El movimiento de caja debe pertenecer "
                        "a la sucursal de la bóveda."
                    )
                }
            )

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.pk or not self._state.adding:
            raise ValidationError("Los movimientos de bóveda son inmutables.")

        if not self.boveda_id:
            raise ValidationError("La bóveda es obligatoria.")

        boveda = Boveda.objects.select_for_update().get(pk=self.boveda_id)
        self.creado_en = timezone.now()

        ultimo_movimiento = (
            BovedaMovimiento.objects.filter(boveda_id=boveda.id)
            .order_by("-numero_secuencia", "-id")
            .first()
        )

        self.numero_secuencia = (
            (ultimo_movimiento.numero_secuencia or 0) + 1
            if ultimo_movimiento
            else 1
        )
        self.hash_anterior = (
            ultimo_movimiento.hash_integridad
            if ultimo_movimiento
            else "GENESIS"
        )

        self.full_clean(
            exclude=[
                "numero_secuencia",
                "hash_anterior",
                "hash_integridad",
            ]
        )

        cadena_integridad = "|".join(
            [
                self.hash_anterior,
                str(self.boveda_id),
                str(self.numero_secuencia),
                str(self.turno_id or ""),
                str(self.movimiento_caja_id or ""),
                str(self.usuario_id),
                self.tipo,
                str(self.monto),
                self.observacion,
                self.creado_en.isoformat(),
            ]
        )

        self.hash_integridad = hashlib.sha256(
            cadena_integridad.encode("utf-8")
        ).hexdigest()

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los movimientos de bóveda no se pueden eliminar.")

    def __str__(self):
        return f"{self.get_tipo_display()} #{self.id} - ${self.monto}"

    
class ArqueoTurno(models.Model):
    class Estado(models.TextChoices):
        REGISTRADO = "REGISTRADO", "Registrado"
        APROBADO = "APROBADO", "Aprobado por supervisor"
        ANULADO = "ANULADO", "Anulado"

    turno = models.ForeignKey(
        TurnoCaja,
        on_delete=models.PROTECT,
        related_name="arqueos",
    )
    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="arqueos_realizados",
    )
    monto_esperado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_contado = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    diferencia = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    estado = models.CharField(
        max_length=20,
        choices=Estado.choices,
        default=Estado.REGISTRADO,
        db_index=True,
    )
    observacion = models.TextField(blank=True, default="")
    creado_en = models.DateTimeField(auto_now_add=True)
    aprobado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="arqueos_aprobados",
    )
    aprobado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-creado_en", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(monto_esperado__gte=0),
                name="arqueo_monto_esperado_no_negativo",
            ),
            models.CheckConstraint(
                condition=Q(total_contado__gte=0),
                name="arqueo_total_contado_no_negativo",
            ),
            models.UniqueConstraint(
                fields=["turno"],
                condition=Q(estado="REGISTRADO"),
                name="unique_arqueo_registrado_por_turno",
            ),
        ]
        indexes = [
            models.Index(fields=["turno", "creado_en"]),
            models.Index(fields=["estado", "creado_en"]),
        ]

    @property
    def pendiente_aprobacion(self):
        return self.estado == self.Estado.REGISTRADO

    def aprobar(self, usuario, observacion=""):
        if not self.pendiente_aprobacion:
            raise ValidationError(
                "Solo se pueden aprobar arqueos registrados."
            )

        self.estado = self.Estado.APROBADO
        self.aprobado_por = usuario
        self.aprobado_en = timezone.now()

        if observacion:
            self.observacion = observacion.strip()

        self.save(
            update_fields=[
                "estado",
                "aprobado_por",
                "aprobado_en",
                "observacion",
            ]
        )

    def __str__(self):
        return f"Arqueo #{self.id} - Turno #{self.turno_id}"


class ArqueoDenominacion(models.Model):
    arqueo = models.ForeignKey(
        ArqueoTurno,
        on_delete=models.CASCADE,
        related_name="denominaciones",
    )
    denominacion = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["arqueo", "denominacion"],
                name="unique_denominacion_por_arqueo",
            ),
            models.CheckConstraint(
                condition=Q(denominacion__gt=0),
                name="arqueo_denominacion_positiva",
            ),
        ]

    @property
    def subtotal(self):
        return self.denominacion * self.cantidad