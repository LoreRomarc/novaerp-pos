# apps/sales/services/caja_service.py
from decimal import Decimal
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum

from apps.sales.models import Caja
from apps.sales.models_caja_enterprise import CajaMovimiento, TurnoCaja


class CajaService:

    # ======================================================
    # OBTENER TURNO ABIERTO
    # ======================================================

    @staticmethod
    def obtener_turno_abierto(sucursal):
        return (
            TurnoCaja.objects
            .select_related("caja")
            .filter(sucursal=sucursal, estado="ABIERTO")
            .first()
        )

    # ======================================================
    # ABRIR CAJA
    # ======================================================

    @staticmethod
    @transaction.atomic
    def abrir_caja(sucursal, usuario, monto_inicial, caja_id):

        caja = Caja.objects.filter(
            id=caja_id,
            sucursal=sucursal
        ).first()

        if not caja:
            raise ValidationError("La caja no pertenece a esta sucursal.")

        if TurnoCaja.objects.filter(caja=caja, estado="ABIERTO").exists():
            raise ValidationError("Ya existe un turno abierto en esta caja.")

        turno = TurnoCaja.objects.create(
            caja=caja,
            usuario_apertura=usuario,
            sucursal=sucursal,
            monto_inicial=monto_inicial
        )

        return turno

    # ======================================================
    # CERRAR CAJA
    # ======================================================

    @staticmethod
    @transaction.atomic
    def cerrar_caja(sucursal, usuario, monto_real):

        turno = (
            TurnoCaja.objects
            .select_for_update()
            .filter(sucursal=sucursal, estado="ABIERTO")
            .first()
        )

        if not turno:
            raise ValidationError("No hay turno abierto.")

        turno.cerrar(monto_real, usuario)

        return turno

    # ======================================================
    # RETIRO A BÓVEDA
    # ======================================================

    @staticmethod
    @transaction.atomic
    def retiro_caja(turno_id, monto, usuario):

        turno = TurnoCaja.objects.select_for_update().get(
            id=turno_id,
            estado="ABIERTO"
        )

        monto = Decimal(str(monto))

        if monto <= 0:
            raise ValidationError("Monto inválido.")

        CajaMovimiento.objects.create(
            turno=turno,
            usuario=usuario,
            tipo="RETIRO_BOVEDA",
            medio_pago="EFECTIVO",
            monto=monto
        )

        # Actualizar bóveda
        boveda = turno.sucursal.boveda
        boveda.saldo_actual += monto
        boveda.save(update_fields=["saldo_actual"])

    # ======================================================
    # REGISTRAR MOVIMIENTOS DE VENTA (🔥 IMPORTANTE)
    # ======================================================

    @staticmethod
    @transaction.atomic
    def registrar_movimientos_venta(venta, usuario, pagos: dict):
        """
        Genera movimientos financieros al cerrar venta.
        """

        turno = TurnoCaja.objects.select_for_update().get(id=venta.turno_id)

        for medio, monto in pagos.items():

            monto = Decimal(str(monto))

            if monto <= 0:
                continue

            CajaMovimiento.objects.create(
                turno=turno,
                usuario=usuario,
                tipo="VENTA",
                medio_pago=medio,
                monto=monto,
                referencia_venta=venta,
            )

        # 🔥 Verificar retiro automático después de registrar venta
        CajaService.verificar_retiro_automatico(turno)

        return True

    # ======================================================
    # RETIRO AUTOMÁTICO POR EXCESO DE EFECTIVO
    # ======================================================

    @staticmethod
    def verificar_retiro_automatico(turno):

        limite = getattr(settings, "LIMITE_EFECTIVO_CAJA", None)

        if not limite:
            return

        efectivo = turno.movimientos.filter(
            medio_pago="EFECTIVO",
            tipo="VENTA"
        ).aggregate(total=Sum("monto"))["total"] or Decimal("0")

        if efectivo > limite:

            monto_retiro = efectivo - limite

            CajaMovimiento.objects.create(
                turno=turno,
                usuario=turno.usuario_apertura,
                tipo="RETIRO_BOVEDA",
                medio_pago="EFECTIVO",
                monto=monto_retiro
            )

            boveda = turno.sucursal.boveda
            boveda.saldo_actual += monto_retiro
            boveda.save(update_fields=["saldo_actual"])