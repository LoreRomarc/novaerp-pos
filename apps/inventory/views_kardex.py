# apps/inventory/views_kardex.py

from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from apps.inventory.models import MovimientoStock
from apps.sales.mixins import SucursalIsolationMixin


class KardexListView(LoginRequiredMixin, SucursalIsolationMixin, ListView):

    model = MovimientoStock
    template_name = "inventory/kardex.html"
    context_object_name = "movimientos"
    paginate_by = 50

    def get_queryset(self):

        user = self.request.user
        variante_id = self.request.GET.get("variante")

        qs = (
            MovimientoStock.objects
            .select_related("variante", "sucursal", "usuario")
            .order_by("-creado")
        )

        # ==========================
        # FILTRO POR SUCURSAL
        # ==========================
        if hasattr(user, "profile") and user.profile.role != "SUPER_ADMIN":
            sucursal = self.get_sucursal()
            qs = qs.filter(sucursal=sucursal)

        # ==========================
        # FILTRO OPCIONAL POR VARIANTE
        # ==========================
        if variante_id:
            qs = qs.filter(variante_id=variante_id)

        return qs