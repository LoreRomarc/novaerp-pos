# apps/sales/models_caja_enterprise.py
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db.models import Q

from django.db import models

# =========================================================
# BÓVEDA DE SUCURSAL
# =========================================================

class Boveda(models.Model):
    """
    Caja fuerte principal de la sucursal.
    Recibe retiros automáticos de cajas.
    """

    sucursal = models.OneToOneField(
        "core.Sucursal",
        on_delete=models.PROTECT,
        related_name="boveda"
    )

    saldo_actual = models.DecimalField(max_digits=16, decimal_places=2, default=0)

    actualizada_en = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bóveda - {self.sucursal}"
    

class TurnoCaja(models.Model):
    """
    Apertura física de una caja.
    """

    ESTADOS = (
        ("ABIERTO", "Abierto"),
        ("CERRADO_CAJERO", "Cerrado por Cajero"),
        ("CERRADO_SUPERVISOR", "Cerrado por Supervisor"),
        ("AUDITADO", "Auditado"),
    )

    caja = models.ForeignKey("Caja", on_delete=models.PROTECT, related_name="turnos")
    usuario_apertura = models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT,related_name="turnos_abiertos")
    sucursal = models.ForeignKey("core.Sucursal", on_delete=models.PROTECT)

    monto_inicial = models.DecimalField(max_digits=14, decimal_places=2)

    estado = models.CharField(max_length=30, choices=ESTADOS, default="ABIERTO")

    abierto_en = models.DateTimeField(auto_now_add=True)
    cerrado_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["caja"],
                condition=Q(estado="ABIERTO"),
                name="unique_turno_abierto_por_caja"
            )
        ]

    def cerrar(self, monto_real, usuario):

        if self.estado != "ABIERTO":
            raise ValidationError("El turno no está abierto.")

        self.estado = "CERRADO_CAJERO"
        self.cerrado_en = timezone.now()
        self.save(update_fields=["estado", "cerrado_en"])

class CajaMovimiento(models.Model):
    """
    Registro financiero inmutable.
    """

    TIPOS = (
        ("VENTA", "Venta"),
        ("RETIRO_BOVEDA", "Retiro a Bóveda"),
        ("INGRESO", "Ingreso Manual"),
        ("AJUSTE", "Ajuste"),
        ("DEVOLUCION", "Devolución"),
    )

    MEDIOS = (
        ("EFECTIVO", "Efectivo"),
        ("TARJETA", "Tarjeta"),
        ("TRANSFERENCIA", "Transferencia"),
        ("QR", "QR"),
    )

    turno = models.ForeignKey(
        TurnoCaja,
        on_delete=models.PROTECT,
        related_name="movimientos"
    )

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    tipo = models.CharField(max_length=30, choices=TIPOS)
    medio_pago = models.CharField(max_length=20, choices=MEDIOS, null=True, blank=True)

    monto = models.DecimalField(max_digits=14, decimal_places=2)

    referencia_venta = models.ForeignKey(
        "Venta",
        null=True,
        blank=True,
        on_delete=models.PROTECT
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    hash_integridad = models.CharField(max_length=64, editable=False)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Movimiento inmutable.")

        import hashlib
        from django.utils import timezone

        self.creado_en = timezone.now()

        # Encadenamiento tipo blockchain
        ultimo = (
            CajaMovimiento.objects
            .filter(turno=self.turno)
            .order_by("-id")
            .first()
        )

        prev_hash = ultimo.hash_integridad if ultimo else "INIT"

        raw = f"{prev_hash}{self.turno_id}{self.tipo}{self.medio_pago}{self.monto}{self.creado_en}"

        self.hash_integridad = hashlib.sha256(raw.encode()).hexdigest()

        super().save(*args, **kwargs)


class ArqueoTurno(models.Model):
    """
    Arqueo físico por denominación.
    """

    turno = models.ForeignKey(
        TurnoCaja,
        on_delete=models.CASCADE,
        related_name="arqueos"
    )

    realizado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT
    )

    creado_en = models.DateTimeField(auto_now_add=True)

    total_contado = models.DecimalField(max_digits=14, decimal_places=2)
    diferencia = models.DecimalField(max_digits=14, decimal_places=2)


class ArqueoDenominacion(models.Model):
    """
    Conteo por billete/moneda.
    """

    arqueo = models.ForeignKey(
        ArqueoTurno,
        on_delete=models.CASCADE,
        related_name="denominaciones"
    )

    denominacion = models.DecimalField(max_digits=10, decimal_places=2)
    cantidad = models.IntegerField()

    @property
    def subtotal(self):
        return self.denominacion * self.cantidad