from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.sales.models import AbonoVenta, Venta
from apps.sales.services.caja_service import CajaService


class CreditoService:
    """Cuentas por cobrar de ventas finalizadas a crédito."""

    MEDIOS_PERMITIDOS = {
        "EFECTIVO",
        "TRANSFERENCIA",
        # TARJETA: conservar preparado para una activación futura.
        "TARJETA",
    }

    @staticmethod
    def _decimal(valor, mensaje):
        try:
            return Decimal(str(valor or 0))
        except Exception as error:
            raise ValidationError(mensaje) from error

    @staticmethod
    @transaction.atomic
    def registrar_abono(*, venta_id, sucursal, turno_id, usuario, pagos, observacion=""):
        venta = (
            Venta.objects.select_for_update()
            .select_related("sucursal")
            .filter(pk=venta_id, sucursal=sucursal)
            .first()
        )
        if not venta:
            raise ValidationError("La venta a crédito no existe en la sucursal activa.")
        if venta.estado != "CREDITO":
            raise ValidationError("La venta no tiene saldo pendiente de crédito.")

        pagos = pagos if isinstance(pagos, dict) else {}
        if set(pagos) - CreditoService.MEDIOS_PERMITIDOS:
            raise ValidationError("El abono contiene un medio de pago inválido.")

        pagos = {
            medio: CreditoService._decimal(
                pagos.get(medio, 0), f"El valor de {medio.lower()} no es válido."
            )
            for medio in CreditoService.MEDIOS_PERMITIDOS
        }
        total = sum(pagos.values(), Decimal("0.00"))
        if total <= 0:
            raise ValidationError("Ingrese un abono mayor a cero.")
        if total > venta.saldo_pendiente:
            raise ValidationError("El abono supera el saldo pendiente de la venta.")

        turno, pagos = CajaService.registrar_abonos_credito(
            venta=venta,
            turno_id=turno_id,
            usuario=usuario,
            pagos=pagos,
        )
        nota = (observacion or "").strip().upper()
        for medio, monto in pagos.items():
            if monto <= 0:
                continue
            abono = AbonoVenta(
                venta=venta,
                turno=turno,
                usuario=usuario,
                medio_pago=medio,
                monto=monto,
                observacion=nota,
            )
            abono.full_clean()
            abono.save()

        venta.monto_efectivo += pagos["EFECTIVO"]
        venta.monto_transferencia += pagos["TRANSFERENCIA"]
        venta.monto_tarjeta += pagos["TARJETA"]
        if venta.saldo_pendiente == 0:
            venta.estado = "CERRADA"
        venta.save(
            update_fields=[
                "monto_efectivo",
                "monto_transferencia",
                "monto_tarjeta",
                "estado",
            ]
        )
        return venta
