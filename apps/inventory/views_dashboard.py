# apps/inventory/views_dashboard.py
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count
from datetime import timedelta
from django.utils.timezone import now

from apps.inventory.mixins import InventoryAccessMixin, SucursalScopedMixin
from apps.inventory.models import Stock, MovimientoStock
from apps.inventory.models_produccion import ProduccionLote


class InventoryDashboardView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    SucursalScopedMixin,
    TemplateView
):
    template_name = "inventory/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        sucursal = self.get_sucursal()
        hoy = now()
        hace_7 = hoy - timedelta(days=7)

        stock_qs = Stock.objects.select_related(
            "variante__producto_base", "sucursal"
        )

        movimientos_qs = MovimientoStock.objects.select_related(
            "variante__producto_base", "usuario"
        )

        produccion_qs = ProduccionLote.objects.all()

        if self.request.user.profile.role != "SUPER_ADMIN":
            stock_qs = stock_qs.filter(sucursal=sucursal)
            movimientos_qs = movimientos_qs.filter(sucursal=sucursal)
            produccion_qs = produccion_qs.filter(sucursal=sucursal)

        # =========================
        # KPIs REALES
        # =========================
        context["total_unidades"] = stock_qs.aggregate(
            total=Sum("cantidad")
        )["total"] or 0

        context["productos_unicos"] = stock_qs.count()

        context["movimientos_hoy"] = movimientos_qs.filter(
            creado__date=hoy.date()
        ).count()

        context["produccion_semana"] = produccion_qs.filter(
            creado__gte=hace_7
        ).count()

        # =========================
        # ALERTAS
        # =========================
        context["stock_bajo"] = stock_qs.filter(cantidad__lt=5)[:10]

        # =========================
        # ACTIVIDAD RECIENTE
        # =========================
        context["movimientos"] = movimientos_qs.order_by("-creado")[:15]

        # =========================
        # TOP PRODUCTOS
        # =========================
        context["top_productos"] = (
            movimientos_qs
            .values("variante__producto_base__nombre")
            .annotate(total=Sum("cantidad"))
            .order_by("-total")[:5]
        )

        return context