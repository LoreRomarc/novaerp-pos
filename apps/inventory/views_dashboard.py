# apps/inventory/views_dashboard.py
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import DecimalField, ExpressionWrapper, F, Sum
from datetime import timedelta
from django.utils.timezone import now

from apps.inventory.mixins import InventoryAccessMixin, SucursalScopedMixin
from apps.inventory.models import Stock, MovimientoStock
from apps.inventory.models_produccion import ProduccionLote
from apps.accounts.models import UserProfile
from apps.core.models import Sucursal


class InventoryDashboardView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    SucursalScopedMixin,
    TemplateView
):
    template_name = "inventory/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        sucursal_activa = self.get_sucursal()
        perfil = self.request.user.profile
        sucursal_id = self.request.GET.get("sucursal", "")
        sucursal = sucursal_activa

        if perfil.role == UserProfile.Role.SUPER_ADMIN and sucursal_id:
            sucursal = Sucursal.objects.filter(pk=sucursal_id, activa=True).first()
            if not sucursal:
                sucursal = sucursal_activa
        hoy = now()
        hace_7 = hoy - timedelta(days=7)

        stock_qs = Stock.objects.select_related(
            "variante__producto_base", "sucursal"
        )

        movimientos_qs = MovimientoStock.objects.select_related(
            "variante__producto_base", "usuario"
        )

        produccion_qs = ProduccionLote.objects.all()

        if sucursal:
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

        context["valor_inventario"] = stock_qs.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("cantidad") * F("costo_promedio"),
                    output_field=DecimalField(max_digits=18, decimal_places=2),
                )
            )
        )["total"] or 0

        context["agotados"] = stock_qs.filter(cantidad=0).count()

        context["movimientos_hoy"] = movimientos_qs.filter(
            creado__date=hoy.date()
        ).count()

        movimientos_hoy_qs = movimientos_qs.filter(creado__date=hoy.date())
        context["entradas_hoy"] = movimientos_hoy_qs.filter(
            cantidad__gt=0
        ).aggregate(total=Sum("cantidad"))["total"] or 0
        context["salidas_hoy"] = movimientos_hoy_qs.filter(
            cantidad__lt=0
        ).aggregate(total=Sum("cantidad"))["total"] or 0

        context["produccion_semana"] = produccion_qs.filter(
            creado__gte=hace_7
        ).aggregate(total=Sum("total_prendas"))["total"] or 0

        context["sucursal"] = sucursal
        context["sucursal_id"] = str(sucursal.id) if sucursal else ""
        context["puede_filtrar_sucursales"] = (
            perfil.role == UserProfile.Role.SUPER_ADMIN
        )
        context["sucursales"] = Sucursal.objects.filter(activa=True).order_by("nombre")
        context["actualizado_en"] = hoy

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
