# apps/inventory/views_kardex.py
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin

from apps.inventory.models import MovimientoStock
from apps.sales.mixins import SucursalIsolationMixin


class KardexListView(LoginRequiredMixin, ListView):

    model = MovimientoStock
    template_name = "inventory/kardex.html"
    context_object_name = "movimientos"
    paginate_by = 50

    def get_queryset(self):

        qs = (
            MovimientoStock.objects
            .select_related(
                "variante",
                "variante__producto_base",
                "sucursal",
                "usuario"
            )
            .order_by("-creado")
        )

        # 👇 filtro correcto por sucursal
        user = self.request.user

        if hasattr(user, "profile") and user.profile:
            if user.profile.role != "SUPER_ADMIN":
                if user.profile.sucursal:
                    qs = qs.filter(sucursal=user.profile.sucursal)

        variante_id = self.request.GET.get("variante")
        if variante_id:
            qs = qs.filter(variante_id=variante_id)

        return qs