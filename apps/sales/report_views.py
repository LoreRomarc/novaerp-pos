# apps/sales/report_views.py
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ( DecimalField, OuterRef, Subquery, Sum,Count,Avg,Q, Value,)
from django.db.models.functions import Coalesce
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import DetailView, TemplateView

from apps.sales.models import Caja, Venta, Vendedor
from apps.sales.models_caja_enterprise import (
    ArqueoTurno,
    Boveda,
    CajaMovimiento,
    TurnoCaja,
)
from apps.sales.services.caja_service import CajaService
from apps.accounts.models import UserProfile
from apps.core.models import Sucursal
from apps.sales.services.report_pdf_service import ReportePDFService
from apps.sales.services.pos_service import POSService
from .mixins import SucursalIsolationMixin
from .permissions import RolePermissionMixin


class ReporteVentasView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    TemplateView
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO",
    ]

    template_name = "sales/reportes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sucursal = self.get_sucursal()
        perfil = self.request.user.profile
        sucursal_id = self.request.GET.get("sucursal", "")
        if perfil.role == UserProfile.Role.SUPER_ADMIN and sucursal_id:
            sucursal = Sucursal.objects.filter(pk=sucursal_id, activa=True).first() or sucursal

        ventas = (
            Venta.objects.select_related(
                "usuario",
                "vendedor",
                "sucursal",
                "turno",
                "turno__caja",
            )
            .prefetch_related("items")
            .filter(sucursal=sucursal)
        )

        inicio = self.request.GET.get("inicio", "").strip()
        fin = self.request.GET.get("fin", "").strip()
        estado = self.request.GET.get("estado", "").strip()
        usuario = self.request.GET.get("usuario", "").strip()
        vendedor = self.request.GET.get("vendedor", "").strip()
        tipo_pago = self.request.GET.get("tipo_pago", "").strip()
        buscar = self.request.GET.get("buscar", "").strip()

        if inicio:
            ventas = ventas.filter(creada__date__gte=inicio)

        if fin:
            ventas = ventas.filter(creada__date__lte=fin)

        if estado:
            ventas = ventas.filter(estado=estado)

        if usuario:
            ventas = ventas.filter(usuario_id=usuario)
        if vendedor:
            ventas = ventas.filter(vendedor_id=vendedor)

        if buscar:
            filtros = (
                Q(cliente__icontains=buscar)
                | Q(observaciones__icontains=buscar)
                | Q(usuario__first_name__icontains=buscar)
                | Q(usuario__last_name__icontains=buscar)
                | Q(usuario__username__icontains=buscar)
                | Q(vendedor__nombre__icontains=buscar)
                | Q(items__variante__sku__icontains=buscar)
                | Q(items__variante__codigo_barras__icontains=buscar)
                | Q(items__variante__producto_base__nombre__icontains=buscar)
                | Q(items__variante__color__nombre__icontains=buscar)
                | Q(items__variante__tipo_tela__nombre__icontains=buscar)
                | Q(items__variante__talla__nombre__icontains=buscar)
            )

            if buscar.isdigit():
                filtros |= Q(id=int(buscar))

            ventas = ventas.filter(filtros).distinct()

        if tipo_pago == "EFECTIVO":
            ventas = ventas.filter(
                monto_efectivo__gt=0,
                monto_tarjeta=0,
                monto_transferencia=0,
            )

        elif tipo_pago == "TRANSFERENCIA":
            ventas = ventas.filter(
                monto_transferencia__gt=0,
                monto_efectivo=0,
                monto_tarjeta=0,
            )

        elif tipo_pago == "TARJETA":
            ventas = ventas.filter(
                monto_tarjeta__gt=0,
                monto_efectivo=0,
                monto_transferencia=0,
            )

        elif tipo_pago == "MIXTO":
            ventas = ventas.filter(
                (
                    Q(monto_efectivo__gt=0)
                    & (
                        Q(monto_tarjeta__gt=0)
                        | Q(monto_transferencia__gt=0)
                    )
                )
                | (
                    Q(monto_tarjeta__gt=0)
                    & Q(monto_transferencia__gt=0)
                )
            )

        elif tipo_pago == "CREDITO":
            # Una venta que terminó de pagarse sigue siendo una venta a
            # crédito si recibió cuotas posteriores; por eso no basta con
            # revisar el estado actual CREDITO.
            ventas = ventas.filter(
                Q(estado="CREDITO")
                | Q(movimientos_caja__tipo=CajaMovimiento.Tipo.ABONO_CREDITO)
            ).distinct()

        monto_field = DecimalField(max_digits=16, decimal_places=2)
        cero = Value(Decimal("0.00"), output_field=monto_field)

        efectivo_caja = (
            CajaMovimiento.objects.filter(
                referencia_venta_id=OuterRef("pk"),
                tipo__in=[
                    CajaMovimiento.Tipo.VENTA,
                    CajaMovimiento.Tipo.ABONO_CREDITO,
                ],
                medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
            )
            .values("referencia_venta_id")
            .annotate(total=Sum("monto"))
            .values("total")[:1]
        )

        tarjeta_caja = (
            CajaMovimiento.objects.filter(
                referencia_venta_id=OuterRef("pk"),
                tipo__in=[
                    CajaMovimiento.Tipo.VENTA,
                    CajaMovimiento.Tipo.ABONO_CREDITO,
                ],
                medio_pago=CajaMovimiento.MedioPago.TARJETA,
            )
            .values("referencia_venta_id")
            .annotate(total=Sum("monto"))
            .values("total")[:1]
        )

        transferencia_caja = (
            CajaMovimiento.objects.filter(
                referencia_venta_id=OuterRef("pk"),
                tipo__in=[
                    CajaMovimiento.Tipo.VENTA,
                    CajaMovimiento.Tipo.ABONO_CREDITO,
                ],
                medio_pago=CajaMovimiento.MedioPago.TRANSFERENCIA,
            )
            .values("referencia_venta_id")
            .annotate(total=Sum("monto"))
            .values("total")[:1]
        )

        ventas = ventas.annotate(
            efectivo_caja=Coalesce(
                Subquery(efectivo_caja, output_field=monto_field),
                cero,
                output_field=monto_field,
            ),
            tarjeta_caja=Coalesce(
                Subquery(tarjeta_caja, output_field=monto_field),
                cero,
                output_field=monto_field,
            ),
            transferencia_caja=Coalesce(
                Subquery(transferencia_caja, output_field=monto_field),
                cero,
                output_field=monto_field,
            ),
        )

        resumen = ventas.exclude(estado="ANULADA").aggregate(
            total_general=Coalesce(
                Sum("total"),
                cero,
                output_field=monto_field,
            ),
            total_efectivo=Coalesce(
                Sum("efectivo_caja"),
                cero,
                output_field=monto_field,
            ),
            total_transferencia=Coalesce(
                Sum("transferencia_caja"),
                cero,
                output_field=monto_field,
            ),
            total_tarjeta=Coalesce(
                Sum("tarjeta_caja"),
                cero,
                output_field=monto_field,
            ),
            cantidad_ventas=Count("id"),
            promedio=Coalesce(
                Avg("total"),
                cero,
                output_field=monto_field,
            ),
        )

        context["ventas"] = ventas.order_by("-creada", "-id")
        context["resumen"] = resumen
        context["estado"] = estado
        context["tipo_pago"] = tipo_pago
        context["inicio"] = inicio
        context["fin"] = fin
        context["buscar"] = buscar
        context["usuario_id"] = usuario
        context["vendedor_id"] = vendedor
        context["puede_filtrar_sucursales"] = (
            perfil.role == UserProfile.Role.SUPER_ADMIN
        )
        context["sucursales"] = Sucursal.objects.filter(activa=True).order_by("nombre")
        context["sucursal_id"] = str(sucursal.id)
        context["sucursal_reporte"] = sucursal

        context["usuarios"] = (
            Venta.objects.filter(sucursal=sucursal)
            .values(
                "usuario__id",
                "usuario__username",
                "usuario__first_name",
                "usuario__last_name",
            )
            .distinct()
            .order_by("usuario__first_name", "usuario__last_name")
        )
        context["vendedores"] = Vendedor.objects.filter(
            sucursal=sucursal, activo=True
        ).order_by("nombre")

        return context


class VentaDetalleView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    DetailView
):

    model = Venta
    template_name = "sales/venta_detalle_modal.html"
    context_object_name = "venta"

    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO",
    ]

    def get_queryset(self):
        qs = (
            Venta.objects
            .select_related(
                "usuario",
                "vendedor",
                "sucursal",
                "turno",
                "turno__caja",
            )
            .prefetch_related(
                "items",
                "items__variante",
                "items__variante__producto_base",
                "items__variante__color",
                "items__variante__tipo_tela",
                "items__variante__talla",
                "abonos",
            )
        )
        if self.request.user.profile.role != UserProfile.Role.SUPER_ADMIN:
            qs = qs.filter(sucursal=self.get_sucursal())
        return qs


class VentaActualizarObservacionView(
    LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View
):
    """Única edición posterior permitida a una venta: su nota operativa."""

    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request, pk):
        ventas = Venta.objects.select_related("sucursal")
        if request.user.profile.role != UserProfile.Role.SUPER_ADMIN:
            ventas = ventas.filter(sucursal=self.get_sucursal())

        venta = get_object_or_404(ventas, pk=pk)
        if venta.estado == "ANULADA":
            return JsonResponse(
                {"success": False, "error": "No se editan observaciones de ventas anuladas."},
                status=400,
            )

        observacion = (request.POST.get("observacion") or "").strip().upper()
        if len(observacion) > 2000:
            return JsonResponse(
                {"success": False, "error": "La observación no puede superar 2.000 caracteres."},
                status=400,
            )

        venta.observaciones = observacion
        venta.save(update_fields=["observaciones"])
        return JsonResponse({"success": True, "observacion": venta.observaciones})


class VentaAnularReporteView(
    LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View
):
    """Anulación administrativa, conservando el registro para auditoría."""

    allowed_roles = ["SUPER_ADMIN"]

    def post(self, request, pk):
        try:
            venta = Venta.objects.select_related("sucursal").filter(pk=pk).first()
            if not venta:
                return redirect("sales:reportes")
            # El superadministrador puede anular desde cualquier sucursal
            # mostrada en el reporte; se usa el turno abierto de esa sede.
            turno = CajaService.obtener_turno_activo_sucursal(venta.sucursal)
            POSService.anular_venta(
                usuario=request.user,
                sucursal=venta.sucursal,
                turno_id=turno.id if turno else None,
                venta_id=pk,
                observacion=(request.POST.get("observacion") or "Anulación administrativa desde reporte.").strip(),
            )
        except ValidationError:
            # No se muestran mensajes de otras secciones; la operación es
            # atómica, por lo que un fallo no altera venta, caja ni stock.
            pass
        return redirect("sales:reportes")


class ReporteVentasPDFView(ReporteVentasView):
    """Descarga el mismo resultado filtrado que el reporte visual."""

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        archivo = ReportePDFService.ventas(
            ventas=context["ventas"],
            resumen=context["resumen"],
            sucursal=context["sucursal_reporte"],
            inicio=context["inicio"],
            fin=context["fin"],
        )
        respuesta = HttpResponse(archivo.getvalue(), content_type="application/pdf")
        respuesta["Content-Disposition"] = "attachment; filename=reporte-ventas.pdf"
        return respuesta


class ReporteCajaView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    TemplateView,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "SUPERVISOR",
        "CAJERO",
    ]

    template_name = "sales/caja/reporte.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sucursal = self.get_sucursal()
        perfil = self.request.user.profile
        sucursal_id = self.request.GET.get("sucursal", "")
        if perfil.role == UserProfile.Role.SUPER_ADMIN and sucursal_id:
            sucursal = Sucursal.objects.filter(
                pk=sucursal_id,
                activa=True,
            ).first() or sucursal

        inicio = self.request.GET.get("inicio", "").strip()
        fin = self.request.GET.get("fin", "").strip()
        caja_id = self.request.GET.get("caja", "").strip()
        estado = self.request.GET.get("estado", "").strip()
        medio_pago = self.request.GET.get("medio_pago", "").strip()

        movimientos = (
            CajaMovimiento.objects.select_related(
                "caja",
                "usuario",
                "turno",
                "referencia_venta",
                "referencia_devolucion",
            )
            .filter(sucursal=sucursal)
        )

        turnos = (
            TurnoCaja.objects.select_related(
                "caja",
                "usuario_apertura",
                "usuario_supervisor",
                "cerrado_por",
                "auditado_por",
            )
            .filter(sucursal=sucursal)
        )

        arqueos = (
            ArqueoTurno.objects.select_related(
                "turno",
                "turno__caja",
                "realizado_por",
                "aprobado_por",
            )
            .filter(turno__sucursal=sucursal)
        )

        if inicio:
            movimientos = movimientos.filter(creado_en__date__gte=inicio)
            turnos = turnos.filter(abierto_en__date__gte=inicio)
            arqueos = arqueos.filter(creado_en__date__gte=inicio)

        if fin:
            movimientos = movimientos.filter(creado_en__date__lte=fin)
            turnos = turnos.filter(abierto_en__date__lte=fin)
            arqueos = arqueos.filter(creado_en__date__lte=fin)

        if caja_id:
            movimientos = movimientos.filter(caja_id=caja_id)
            turnos = turnos.filter(caja_id=caja_id)
            arqueos = arqueos.filter(turno__caja_id=caja_id)

        if estado:
            turnos = turnos.filter(estado=estado)

        # Este reporte parte de movimientos de caja. "Combinado" significa
        # que la venta asociada recibió efectivo y transferencia; "Crédito /
        # abonos" reúne el pago inicial de un crédito pendiente y sus cuotas,
        # incluso cuando la factura ya se cerró al terminar de cobrarla.
        if medio_pago == "EFECTIVO":
            movimientos = movimientos.filter(
                medio_pago=CajaMovimiento.MedioPago.EFECTIVO
            )
        elif medio_pago == "TRANSFERENCIA":
            movimientos = movimientos.filter(
                medio_pago=CajaMovimiento.MedioPago.TRANSFERENCIA
            )
        elif medio_pago == "COMBINADO":
            movimientos = movimientos.filter(
                tipo=CajaMovimiento.Tipo.VENTA,
                referencia_venta__monto_efectivo__gt=0,
                referencia_venta__monto_transferencia__gt=0,
            )
        elif medio_pago == "CREDITO":
            movimientos = movimientos.filter(
                Q(tipo=CajaMovimiento.Tipo.ABONO_CREDITO)
                | Q(
                    tipo=CajaMovimiento.Tipo.VENTA,
                    referencia_venta__estado="CREDITO",
                )
                | Q(
                    tipo=CajaMovimiento.Tipo.VENTA,
                    referencia_venta__abonos__isnull=False,
                )
            ).distinct()

        monto_field = DecimalField(max_digits=16, decimal_places=2)
        cero = Value(Decimal("0.00"), output_field=monto_field)

        resumen = movimientos.aggregate(
            ventas_efectivo=Coalesce(
                Sum(
                    "monto",
                    filter=Q(
                        tipo=CajaMovimiento.Tipo.VENTA,
                        medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
                    ),
                ),
                cero,
                output_field=monto_field,
            ),
            ventas_tarjeta=Coalesce(
                Sum(
                    "monto",
                    filter=Q(
                        tipo=CajaMovimiento.Tipo.VENTA,
                        medio_pago=CajaMovimiento.MedioPago.TARJETA,
                    ),
                ),
                cero,
                output_field=monto_field,
            ),
            ventas_transferencia=Coalesce(
                Sum(
                    "monto",
                    filter=Q(
                        tipo=CajaMovimiento.Tipo.VENTA,
                        medio_pago=CajaMovimiento.MedioPago.TRANSFERENCIA,
                    ),
                ),
                cero,
                output_field=monto_field,
            ),
            abonos_efectivo=Coalesce(
                Sum(
                    "monto",
                    filter=Q(
                        tipo=CajaMovimiento.Tipo.ABONO_CREDITO,
                        medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
                    ),
                ),
                cero,
                output_field=monto_field,
            ),
            abonos_tarjeta=Coalesce(
                Sum(
                    "monto",
                    filter=Q(
                        tipo=CajaMovimiento.Tipo.ABONO_CREDITO,
                        medio_pago=CajaMovimiento.MedioPago.TARJETA,
                    ),
                ),
                cero,
                output_field=monto_field,
            ),
            abonos_transferencia=Coalesce(
                Sum(
                    "monto",
                    filter=Q(
                        tipo=CajaMovimiento.Tipo.ABONO_CREDITO,
                        medio_pago=CajaMovimiento.MedioPago.TRANSFERENCIA,
                    ),
                ),
                cero,
                output_field=monto_field,
            ),
            cambios_efectivo=Coalesce(
                Sum(
                    "monto",
                    filter=Q(
                        tipo=CajaMovimiento.Tipo.CAMBIO,
                        medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
                    ),
                ),
                cero,
                output_field=monto_field,
            ),
            ingresos=Coalesce(
                Sum(
                    "monto",
                    filter=Q(tipo=CajaMovimiento.Tipo.INGRESO),
                ),
                cero,
                output_field=monto_field,
            ),
            egresos=Coalesce(
                Sum(
                    "monto",
                    filter=Q(tipo=CajaMovimiento.Tipo.EGRESO),
                ),
                cero,
                output_field=monto_field,
            ),
            retiros_boveda=Coalesce(
                Sum(
                    "monto",
                    filter=Q(tipo=CajaMovimiento.Tipo.RETIRO_BOVEDA),
                ),
                cero,
                output_field=monto_field,
            ),
            cantidad_movimientos=Count("id"),
        )

        # El reporte financiero no reutiliza el resumen de un turno porque
        # puede abarcar varios turnos y fechas. Estas métricas conservan los
        # conceptos separados: una venta no se duplica al recibir cuotas.
        resumen["abonos_total"] = (
            resumen["abonos_efectivo"]
            + resumen["abonos_tarjeta"]
            + resumen["abonos_transferencia"]
        )
        resumen["efectivo_operacion_neto"] = (
            resumen["ventas_efectivo"]
            + resumen["abonos_efectivo"]
            + resumen["cambios_efectivo"]
            + resumen["ingresos"]
            - resumen["egresos"]
            - resumen["retiros_boveda"]
        )

        resumen_turnos = turnos.aggregate(
            cantidad_turnos=Count("id"),
            turnos_auditados=Count(
                "id",
                filter=Q(estado=TurnoCaja.Estado.AUDITADO),
            ),
            diferencias=Coalesce(
                Sum("diferencia"),
                cero,
                output_field=monto_field,
            ),
        )

        boveda = Boveda.objects.filter(sucursal=sucursal).first()

        arqueos = list(
            arqueos.order_by("-creado_en", "-id")[:100]
        )

        for arqueo in arqueos:
            arqueo.puede_aprobar_por_usuario = (
                arqueo.estado == ArqueoTurno.Estado.REGISTRADO
                and arqueo.turno.usuario_supervisor_id == self.request.user.id
            )

        context.update(
            {
                "cajas": Caja.objects.filter(
                    sucursal=sucursal,
                    activa=True,
                ).order_by("codigo"),
                "movimientos": movimientos.order_by("-creado_en", "-id")[:100],
                "movimientos_pdf": movimientos.order_by("-creado_en", "-id"),
                "turnos": turnos.order_by("-abierto_en", "-id")[:100],
                "arqueos": arqueos,
                "resumen": resumen,
                "resumen_turnos": resumen_turnos,
                "saldo_boveda": (
                    boveda.saldo_actual
                    if boveda
                    else Decimal("0.00")
                ),
                "inicio": inicio,
                "fin": fin,
                "caja_id": caja_id,
                "estado": estado,
                "medio_pago": medio_pago,
                "sucursal_reporte": sucursal,
                "sucursal_id": str(sucursal.id),
                "puede_filtrar_sucursales": (
                    perfil.role == UserProfile.Role.SUPER_ADMIN
                ),
                "sucursales": Sucursal.objects.filter(activa=True).order_by("nombre"),
            }
        )

        return context


class ReporteCajaPDFView(ReporteCajaView):
    """Exporta los movimientos financieros usando los filtros actuales."""

    def get(self, request, *args, **kwargs):
        context = self.get_context_data(**kwargs)
        archivo = ReportePDFService.financiero(
            movimientos=context["movimientos_pdf"],
            resumen=context["resumen"],
            resumen_turnos=context["resumen_turnos"],
            saldo_boveda=context["saldo_boveda"],
            sucursal=context["sucursal_reporte"],
            inicio=context["inicio"],
            fin=context["fin"],
        )
        respuesta = HttpResponse(archivo.getvalue(), content_type="application/pdf")
        respuesta["Content-Disposition"] = "attachment; filename=reporte-financiero.pdf"
        return respuesta


class CajaMovimientoDetalleView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    DetailView,
):
    """Detalle de lectura para auditoría; nunca modifica un movimiento."""

    model = CajaMovimiento
    template_name = "sales/caja/movimiento_detalle_modal.html"
    context_object_name = "movimiento"
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "SUPERVISOR", "CAJERO"]

    def get_queryset(self):
        qs = CajaMovimiento.objects.select_related(
            "sucursal", "caja", "turno", "usuario", "referencia_venta", "referencia_devolucion"
        )
        if self.request.user.profile.role != UserProfile.Role.SUPER_ADMIN:
            qs = qs.filter(sucursal=self.get_sucursal())
        return qs
    
