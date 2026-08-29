# apps/inventory/views_confeccion.py
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q, Sum, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView

from apps.inventory.mixins import InventoryAccessMixin
from apps.inventory.models_produccion import (
    OperacionProduccion,
    OperarioProduccion,
    ProduccionDetalle,
    ProduccionLote,
)
from apps.inventory.services.confeccion_service import (
    ConfeccionService,
)
from apps.sales.mixins import SucursalIsolationMixin


class ConfeccionLotesView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    SucursalIsolationMixin,
    ListView,
):
    template_name = "inventory/confeccion_lotes.html"
    context_object_name = "lotes"
    paginate_by = 30

    def get_queryset(self):
        sucursal = self.get_sucursal()

        return (
            ProduccionLote.objects
            .filter(
                sucursal=sucursal,
                estado__in=[
                    ProduccionLote.Estado.PENDIENTE_CONFECCION,
                    ProduccionLote.Estado.EN_CONFECCION,
                ],
            )
            .select_related("operario")
            .prefetch_related(
                "detalles",
                "detalles__variante",
                "detalles__variante__producto_base",
                "detalles__variante__talla",
            )
            .order_by("creado", "id")
        )


class ConfeccionRegistroView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    SucursalIsolationMixin,
    View,
):
    template_name = "inventory/confeccion_registrar.html"

    def get_lote(self, lote_id):
        return get_object_or_404(
            ProduccionLote.objects.select_related("sucursal"),
            pk=lote_id,
            sucursal=self.get_sucursal(),
            estado__in=[
                ProduccionLote.Estado.PENDIENTE_CONFECCION,
                ProduccionLote.Estado.EN_CONFECCION,
            ],
        )

    def get_context_data(self, lote):
        detalles = list(
            ProduccionDetalle.objects
            .filter(lote=lote)
            .select_related(
                "variante",
                "variante__producto_base",
                "variante__tipo_tela",
                "variante__color",
                "variante__talla",
            )
            .annotate(
                confeccionadas=Coalesce(
                    Sum(
                        "operaciones__cantidad",
                        filter=Q(
                            operaciones__tipo=(
                                OperacionProduccion.Tipo.CONFECCION
                            )
                        ),
                    ),
                    Value(0),
                )
            )
            .order_by("orden", "id")
        )

        detalles_pendientes = []

        for detalle in detalles:
            detalle.pendientes = (
                detalle.cantidad - detalle.confeccionadas
            )

            if detalle.pendientes > 0:
                detalles_pendientes.append(detalle)

        costureras = (
            OperarioProduccion.objects
            .filter(
                sucursal=lote.sucursal,
                activo=True,
                especialidad__in=[
                    OperarioProduccion.Especialidad.COSTURERA,
                    OperarioProduccion.Especialidad.AMBOS,
                ],
            )
            .order_by("nombre")
        )

        return {
            "lote": lote,
            "detalles": detalles_pendientes,
            "costureras": costureras,
        }

    def get(self, request, lote_id):
        lote = self.get_lote(lote_id)

        return render(
            request,
            self.template_name,
            self.get_context_data(lote),
        )

    def post(self, request, lote_id):
        lote = self.get_lote(lote_id)
        items = []

        try:
            for detalle in lote.detalles.all():
                cantidad = request.POST.get(
                    f"cantidad_{detalle.id}",
                    "",
                ).strip()

                # Una línea vacía significa que todavía
                # no se ha confeccionado esa variante.
                if not cantidad or cantidad == "0":
                    continue

                costurera_id = request.POST.get(
                    f"costurera_{detalle.id}",
                    "",
                ).strip()

                if not costurera_id:
                    raise ValidationError(
                        f"Seleccione la costurera para "
                        f"{detalle.variante}."
                    )

                items.append(
                    {
                        "detalle_id": detalle.id,
                        "operario_id": int(costurera_id),
                        "cantidad": int(cantidad),
                    }
                )

            lote = ConfeccionService.registrar_confeccion(
                lote_id=lote.id,
                sucursal=self.get_sucursal(),
                usuario=request.user,
                items=items,
            )

            messages.success(
                request,
                (
                    f"Confección registrada para "
                    f"{lote.referencia}. "
                    f"Las prendas terminadas ya ingresaron "
                    f"a inventario."
                ),
            )

            if lote.estado == ProduccionLote.Estado.FINALIZADO:
                return redirect("inventory:confeccion_lotes")

            return redirect(
                "inventory:confeccion_registrar",
                lote_id=lote.id,
            )

        except ValidationError as error:
            messages.error(request, error.messages[0])

        except ValueError as error:
            messages.error(request, str(error))

        return render(
            request,
            self.template_name,
            self.get_context_data(lote),
        )