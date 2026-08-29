# apps/inventory/views_kardex.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import ListView

from apps.inventory.models import MovimientoStock, Traslado
from apps.sales.mixins import SucursalIsolationMixin


class KardexListView(LoginRequiredMixin, SucursalIsolationMixin, ListView):

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

        qs = qs.filter(sucursal=self.get_sucursal())

        variante_id = self.request.GET.get("variante")
        if variante_id:
            qs = qs.filter(variante_id=variante_id)

        return qs


class KardexDetalleView(LoginRequiredMixin, SucursalIsolationMixin, View):
    """Detalle auditable de un movimiento, incluido el traslado relacionado."""

    def get(self, request, pk):
        movimiento = get_object_or_404(
            MovimientoStock.objects.select_related(
                "variante", "variante__producto_base", "sucursal", "usuario"
            ), pk=pk, sucursal=self.get_sucursal(),
        )
        traslado = None
        if movimiento.tipo in {"COMPLETO", "SALIDA", "ENTRADA"}:
            traslado = (
                Traslado.objects.select_related("origen", "destino")
                .prefetch_related("detalles__variante__producto_base")
                .filter(numero=movimiento.referencia).first()
            )

        return JsonResponse({
            "success": True,
            "movimiento": {
                "id": movimiento.id, "tipo": movimiento.tipo_legible,
                "referencia": movimiento.referencia or "Sin referencia",
                "producto": str(movimiento.variante),
                "sucursal": movimiento.sucursal.nombre,
                "cantidad": str(movimiento.cantidad),
                "saldo": str(movimiento.saldo_post_movimiento or 0),
                "usuario": str(movimiento.usuario or "Sistema"),
                "creado": movimiento.creado.strftime("%d/%m/%Y %H:%M"),
            },
            "traslado": None if not traslado else {
                "numero": traslado.numero, "tipo": traslado.get_tipo_display(),
                "estado": traslado.get_estado_display(),
                "origen": traslado.origen.nombre if traslado.origen else "—",
                "destino": traslado.destino.nombre if traslado.destino else "—",
                "motivo": traslado.motivo or "Sin motivo registrado",
                "observaciones": traslado.observaciones or "Sin observaciones",
                "items": [{"producto": str(d.variante), "cantidad": str(d.cantidad), "observacion": d.observacion or ""} for d in traslado.detalles.all()],
            },
        })
