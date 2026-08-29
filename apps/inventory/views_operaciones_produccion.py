# apps/inventory/views_operaciones_produccion.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.views.generic import ListView

from apps.inventory.mixins import InventoryAccessMixin
from apps.inventory.models_produccion import (
    OperacionProduccion,
    OperarioProduccion,
)
from apps.sales.mixins import SucursalIsolationMixin


class OperacionProduccionListView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    SucursalIsolationMixin,
    ListView,
):
    model = OperacionProduccion
    template_name = "inventory/operaciones_produccion.html"
    context_object_name = "operaciones"
    paginate_by = 50

    def get_queryset(self):
        sucursal = self.get_sucursal()

        qs = (
            OperacionProduccion.objects
            .select_related(
                "operario",
                "registrado_por",
                "detalle",
                "detalle__lote",
                "detalle__variante",
                "detalle__variante__producto_base",
                "detalle__variante__tipo_tela",
                "detalle__variante__color",
                "detalle__variante__talla",
            )
            .filter(detalle__lote__sucursal=sucursal)
            .order_by("-creado", "-id")
        )

        q = self.request.GET.get("q", "").strip()
        tipo = self.request.GET.get("tipo", "").strip()
        operario_id = self.request.GET.get(
            "operario",
            "",
        ).strip()

        if q:
            qs = qs.filter(
                Q(detalle__lote__referencia__icontains=q)
                | Q(operario__nombre__icontains=q)
                | Q(
                    detalle__variante__producto_base__nombre__icontains=q
                )
                | Q(detalle__variante__sku__icontains=q)
            )

        if tipo in {
            OperacionProduccion.Tipo.CORTE,
            OperacionProduccion.Tipo.CONFECCION,
        }:
            qs = qs.filter(tipo=tipo)

        if operario_id.isdigit():
            qs = qs.filter(operario_id=int(operario_id))

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["operarios"] = (
            OperarioProduccion.objects
            .filter(
                sucursal=self.get_sucursal(),
            )
            .order_by("nombre")
        )

        context["tipos"] = OperacionProduccion.Tipo.choices

        return context