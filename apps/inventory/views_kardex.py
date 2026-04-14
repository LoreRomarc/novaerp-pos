from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q

from apps.inventory.models import MovimientoStock
from apps.sales.mixins import SucursalIsolationMixin


class KardexListView(LoginRequiredMixin, SucursalIsolationMixin, ListView):

    model = MovimientoStock
    template_name = "inventory/kardex.html"
    context_object_name = "movimientos"
    paginate_by = 50

    def get_queryset(self):

        sucursal = self.get_sucursal()
        variante_id = self.request.GET.get("variante")

        qs = (
            MovimientoStock.objects
            .select_related("variante", "sucursal", "usuario")
            .filter(sucursal=sucursal)
            .order_by("-creado")
        )

        if variante_id:
            qs = qs.filter(variante_id=variante_id)

        return qs