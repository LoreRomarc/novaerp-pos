# apps/sales/report_views.py
from decimal import Decimal

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import (
    Sum,
    Count,
    Avg,
    Q,
    F,
    Value,
    Case,
    When,
    DecimalField,
)
from django.db.models.functions import Coalesce
from django.views.generic import DetailView, TemplateView

from apps.sales.models import Venta
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
            Venta.objects
            .select_related(
                "usuario",
                "sucursal",
                "turno",
            )
            .prefetch_related(
                "items",
            )
            .filter(
                sucursal=sucursal
            )
            .exclude(
                estado="ANULADA"
            )
        )

        inicio = self.request.GET.get("inicio")
        fin = self.request.GET.get("fin")
        estado = self.request.GET.get("estado")
        usuario = self.request.GET.get("usuario")
        tipo_pago = self.request.GET.get("tipo_pago")
        buscar = self.request.GET.get("buscar")

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
                |
                Q(observaciones__icontains=buscar)

                # usuario que realizó la venta
                |
                Q(usuario__first_name__icontains=buscar)
                |
                Q(usuario__last_name__icontains=buscar)
                |
                Q(usuario__username__icontains=buscar)

                # productos vendidos
                |
                Q(items__variante__sku__icontains=buscar)
                |
                Q(items__variante__codigo_barras__icontains=buscar)
                |
                Q(items__variante__producto_base__nombre__icontains=buscar)

                # características del producto
                |
                Q(items__variante__color__nombre__icontains=buscar)
                |
                Q(items__variante__tipo_tela__nombre__icontains=buscar)
                |
                Q(items__variante__talla__nombre__icontains=buscar)
            )

            # buscar por número de venta
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
                    &
                    (
                        Q(monto_tarjeta__gt=0)
                        |
                        Q(monto_transferencia__gt=0)
                    )
                )
                |
                (
                    Q(monto_tarjeta__gt=0)
                    &
                    Q(monto_transferencia__gt=0)
                )
            )

        resumen = ventas.aggregate(

            total_general=Coalesce(
                Sum("total"),
                Decimal("0")
            ),

            total_efectivo=Coalesce(
                Sum("monto_efectivo"),
                Decimal("0")
            ),

            total_transferencia=Coalesce(
                Sum("monto_transferencia"),
                Decimal("0")
            ),

            total_tarjeta=Coalesce(
                Sum("monto_tarjeta"),
                Decimal("0")
            ),

            cantidad_ventas=Count("id"),

            promedio=Coalesce(
                Avg("total"),
                Decimal("0")
            ),

        )

        context["ventas"] = ventas.order_by("-creada")

        context["resumen"] = resumen

        context["estado"] = estado or ""

        context["tipo_pago"] = tipo_pago or ""

        context["inicio"] = inicio or ""

        context["fin"] = fin or ""

        context["buscar"] = buscar or ""

        context["usuario_id"] = usuario or ""

        context["usuarios"] = (
            Venta.objects
            .filter(
                sucursal=sucursal
            )
            .values(
                "usuario__id",
                "usuario__username",
                "usuario__first_name",
                "usuario__last_name",
            )
            .distinct()
            .order_by("usuario__first_name")
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
