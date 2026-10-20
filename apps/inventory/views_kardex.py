# apps/inventory/views_kardex.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View
from django.views.generic import ListView

from apps.accounts.models import UserProfile
from apps.core.models import Sucursal
from apps.inventory.mixins import InventoryAccessMixin
from apps.inventory.models import MovimientoStock, Traslado
from apps.inventory.movimientos import (
    TIPOS_MOVIMIENTO_FILTRO,
    codigos_para_tipo,
)
from apps.sales.mixins import SucursalIsolationMixin


class KardexListView(LoginRequiredMixin, InventoryAccessMixin, SucursalIsolationMixin, ListView):

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

        perfil = self.request.user.profile
        sucursal_id = self.request.GET.get("sucursal", "")
        if perfil.role != UserProfile.Role.SUPER_ADMIN:
            qs = qs.filter(sucursal=self.get_sucursal())
        elif sucursal_id:
            qs = qs.filter(sucursal_id=sucursal_id)

        variante_id = self.request.GET.get("variante")
        if variante_id:
            qs = qs.filter(variante_id=variante_id)

        tipo_movimiento = self.request.GET.get("tipo_movimiento", "")
        if tipo_movimiento:
            qs = qs.filter(tipo__in=codigos_para_tipo(tipo_movimiento))

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(variante__producto_base__nombre__icontains=q)
                | Q(variante__sku__icontains=q)
                | Q(referencia__icontains=q)
                | Q(tipo__icontains=q)
            )

        fecha_desde = self.request.GET.get("fecha_desde", "")
        fecha_hasta = self.request.GET.get("fecha_hasta", "")
        if fecha_desde:
            qs = qs.filter(creado__date__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(creado__date__lte=fecha_hasta)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["puede_filtrar_sucursales"] = (
            self.request.user.profile.role == UserProfile.Role.SUPER_ADMIN
        )
        context["sucursales"] = Sucursal.objects.filter(activa=True).order_by("nombre")
        context["sucursal_id"] = self.request.GET.get("sucursal", "")
        context["tipos_movimiento"] = TIPOS_MOVIMIENTO_FILTRO
        return context


class KardexDetalleView(LoginRequiredMixin, InventoryAccessMixin, SucursalIsolationMixin, View):
    """Detalle auditable de un movimiento, incluido el traslado relacionado."""

    def get(self, request, pk):
        movimientos = MovimientoStock.objects.select_related(
            "variante", "variante__producto_base", "sucursal", "usuario"
        )
        if self.request.user.profile.role != UserProfile.Role.SUPER_ADMIN:
            movimientos = movimientos.filter(sucursal=self.get_sucursal())
        movimiento = get_object_or_404(movimientos, pk=pk)
        traslado = None
        if movimiento.referencia:
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
                "observacion": movimiento.observacion or "Sin observaciones registradas",
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
