# apps/sales/report_views.py
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import ( DecimalField, OuterRef, Subquery, Sum,Count,Avg,Q, Value,)
from django.db.models.functions import Coalesce
from django.views.generic import DetailView, TemplateView

from apps.sales.models import Caja, Venta
from apps.sales.models_caja_enterprise import (
    ArqueoTurno,
    Boveda,
    CajaMovimiento,
    TurnoCaja,
)
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
    ]

    template_name = "sales/reportes.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sucursal = self.get_sucursal()

        ventas = (
            Venta.objects.select_related(
                "usuario",
                "sucursal",
                "turno",
            )
            .prefetch_related("items")
            .filter(sucursal=sucursal)
            .exclude(estado="ANULADA")
        )

        inicio = self.request.GET.get("inicio", "").strip()
        fin = self.request.GET.get("fin", "").strip()
        estado = self.request.GET.get("estado", "").strip()
        usuario = self.request.GET.get("usuario", "").strip()
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

        if buscar:
            filtros = (
                Q(cliente__icontains=buscar)
                | Q(observaciones__icontains=buscar)
                | Q(usuario__first_name__icontains=buscar)
                | Q(usuario__last_name__icontains=buscar)
                | Q(usuario__username__icontains=buscar)
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

        monto_field = DecimalField(max_digits=16, decimal_places=2)
        cero = Value(Decimal("0.00"), output_field=monto_field)

        efectivo_caja = (
            CajaMovimiento.objects.filter(
                referencia_venta_id=OuterRef("pk"),
                tipo=CajaMovimiento.Tipo.VENTA,
                medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
            )
            .values("referencia_venta_id")
            .annotate(total=Sum("monto"))
            .values("total")[:1]
        )

        tarjeta_caja = (
            CajaMovimiento.objects.filter(
                referencia_venta_id=OuterRef("pk"),
                tipo=CajaMovimiento.Tipo.VENTA,
                medio_pago=CajaMovimiento.MedioPago.TARJETA,
            )
            .values("referencia_venta_id")
            .annotate(total=Sum("monto"))
            .values("total")[:1]
        )

        transferencia_caja = (
            CajaMovimiento.objects.filter(
                referencia_venta_id=OuterRef("pk"),
                tipo=CajaMovimiento.Tipo.VENTA,
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

        resumen = ventas.aggregate(
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
    ]

    def get_queryset(self):

        return (
            Venta.objects
            .select_related(
                "usuario",
                "sucursal",
                "turno",
            )
            .prefetch_related(
                "items",
                "items__variante",
                "items__variante__producto_base",
                "items__variante__color",
                "items__variante__tipo_tela",
                "items__variante__talla",
            )
            .filter(
                sucursal=self.get_sucursal()
            )
        )

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
    ]

    template_name = "sales/caja/reporte.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sucursal = self.get_sucursal()

        inicio = self.request.GET.get("inicio", "").strip()
        fin = self.request.GET.get("fin", "").strip()
        caja_id = self.request.GET.get("caja", "").strip()
        estado = self.request.GET.get("estado", "").strip()

        movimientos = (
            CajaMovimiento.objects.select_related(
                "caja",
                "usuario",
                "turno",
                "referencia_venta",
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

        monto_field = DecimalField(max_digits=16, decimal_places=2)
        cero = Value(Decimal("0.00"), output_field=monto_field)

        resumen = movimientos.aggregate(
            ventas_efectivo=Coalesce(
                Sum(
                    "monto",
                    filter=Q(
                        tipo__in=[
                            CajaMovimiento.Tipo.VENTA,
                            CajaMovimiento.Tipo.CAMBIO,
                        ],
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
                        tipo__in=[
                            CajaMovimiento.Tipo.VENTA,
                            CajaMovimiento.Tipo.CAMBIO,
                        ],
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
                       tipo__in=[
                            CajaMovimiento.Tipo.VENTA,
                            CajaMovimiento.Tipo.CAMBIO,
                        ],
                        medio_pago=CajaMovimiento.MedioPago.TRANSFERENCIA,
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
            }
        )

        return context
    