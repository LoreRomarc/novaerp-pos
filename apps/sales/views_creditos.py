from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.views.generic import TemplateView

from apps.sales.mixins import SucursalIsolationMixin
from apps.sales.models import Venta
from apps.sales.models_caja_enterprise import CajaMovimiento
from apps.sales.permissions import RolePermissionMixin
from apps.sales.services.caja_service import CajaService
from apps.sales.services.credito_service import CreditoService


class CreditoListView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    TemplateView,
):
    """Lista y recaudo de cuentas por cobrar de la sucursal activa."""

    template_name = "sales/creditos.html"
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def _ventas(self):
        ventas = (
            Venta.objects.select_related("usuario", "vendedor", "sucursal")
            .prefetch_related("abonos")
            .filter(sucursal=self.get_sucursal())
            # Una vez pagado, el crédito queda CERRADO pero conserva sus
            # abonos. Se muestra en historial sin volver a ser cobrable.
            .filter(Q(estado="CREDITO") | Q(estado="CERRADA", abonos__isnull=False))
            .distinct()
            .order_by("creada", "id")
        )
        buscar = self.request.GET.get("q", "").strip()
        medio_pago = self.request.GET.get("medio_pago", "").strip()
        estado_credito = self.request.GET.get("estado", "PENDIENTES").strip()
        if estado_credito == "PAGADOS":
            ventas = ventas.filter(estado="CERRADA")
        elif estado_credito != "TODOS":
            estado_credito = "PENDIENTES"
            ventas = ventas.filter(estado="CREDITO")
        if buscar:
            filtros = (
                Q(cliente__icontains=buscar)
                | Q(observaciones__icontains=buscar)
                | Q(vendedor__nombre__icontains=buscar)
            )
            if buscar.isdigit():
                filtros |= Q(id=int(buscar))
            ventas = ventas.filter(filtros)

        if medio_pago == "EFECTIVO":
            ventas = ventas.filter(
                Q(monto_efectivo__gt=0)
                | Q(abonos__medio_pago="EFECTIVO")
            ).distinct()
        elif medio_pago == "TRANSFERENCIA":
            ventas = ventas.filter(
                Q(monto_transferencia__gt=0)
                | Q(abonos__medio_pago="TRANSFERENCIA")
            ).distinct()
        elif medio_pago == "COMBINADO":
            ventas = ventas.filter(
                monto_efectivo__gt=0,
                monto_transferencia__gt=0,
            )
        return ventas

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sucursal = self.get_sucursal()
        venta_id = self.request.GET.get("abonar", "")
        venta_seleccionada = self._ventas().filter(pk=venta_id).first() if venta_id else None
        historial_pagos = []
        if venta_seleccionada:
            # VENTA corresponde al abono inicial del crédito y
            # ABONO_CREDITO a cada cuota posterior. Juntos forman el
            # historial financiero real, sin duplicar registros.
            historial_pagos = (
                CajaMovimiento.objects.select_related("caja", "turno", "usuario")
                .filter(
                    referencia_venta=venta_seleccionada,
                    tipo__in=[
                        CajaMovimiento.Tipo.VENTA,
                        CajaMovimiento.Tipo.ABONO_CREDITO,
                    ],
                )
                .order_by("creado_en", "id")
            )
        context.update(
            {
                "ventas_credito": self._ventas(),
                "venta_seleccionada": venta_seleccionada,
                "historial_pagos": historial_pagos,
                "q": self.request.GET.get("q", "").strip(),
                "medio_pago": self.request.GET.get("medio_pago", "").strip(),
                "estado_credito": self.request.GET.get("estado", "PENDIENTES").strip(),
                "turno": CajaService.obtener_turno_operable(sucursal, self.request.user),
                "error_abono": getattr(self, "error_abono", ""),
                "exito_abono": getattr(self, "exito_abono", ""),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        venta_id = request.POST.get("venta_id")
        try:
            turno = CajaService.obtener_turno_operable(
                self.get_sucursal(), request.user
            )
            if not turno:
                raise ValidationError("Abra o active una caja antes de registrar un abono.")

            venta = CreditoService.registrar_abono(
                venta_id=venta_id,
                sucursal=self.get_sucursal(),
                turno_id=turno.id,
                usuario=request.user,
                pagos={
                    "EFECTIVO": request.POST.get("efectivo", 0),
                    "TRANSFERENCIA": request.POST.get("transferencia", 0),
                    # TARJETA: preparada en backend; la interfaz permanece oculta.
                    "TARJETA": 0,
                },
                observacion=request.POST.get("observacion", ""),
            )
            self.exito_abono = (
                f"Abono registrado. Saldo pendiente: ${venta.saldo_pendiente:,.0f}."
            )
            request.GET = request.GET.copy()
            request.GET["abonar"] = str(venta.id) if venta.estado == "CREDITO" else ""
        except ValidationError as error:
            self.error_abono = error.messages[0]
            request.GET = request.GET.copy()
            request.GET["abonar"] = str(venta_id or "")
        return self.render_to_response(self.get_context_data())
