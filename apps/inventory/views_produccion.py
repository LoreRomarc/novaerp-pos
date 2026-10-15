# apps/inventory/views_produccion.py
from django.core.exceptions import ValidationError
from django.db.models import Case, IntegerField, Value, When
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views import View

from apps.inventory.models import (
    Color,
    ProductoBase,
    Talla,
    TipoTela,
)
from apps.inventory.models_produccion import (
    OperarioProduccion,
    RolloTela,
)
from apps.inventory.services.corte_service import CorteService
from apps.inventory.mixins import InventoryAccessMixin
from apps.sales.mixins import SucursalIsolationMixin


class CorteProduccionView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    SucursalIsolationMixin,
    View,
):
    template_name = "inventory/corte_produccion.html"

    def get_context_data(self):
        sucursal = self.get_sucursal()

        return {
            "rollos": (
                RolloTela.objects
                .select_related("tipo_tela", "color")
                .filter(estado="DISPONIBLE")
                .order_by("codigo")
            ),
            "productos": ProductoBase.objects.filter(
                activo=True
            ).order_by("nombre"),
            "telas": TipoTela.objects.filter(
                activo=True
            ).order_by("nombre"),
            "colores": (
                Color.objects.filter(activo=True)
                .annotate(
                    es_sin_definir=Case(
                        When(nombre__iexact="Sin Definir", then=Value(0)),
                        default=Value(1),
                        output_field=IntegerField(),
                    )
                )
                .order_by("es_sin_definir", "nombre")
            ),
            "tallas": Talla.objects.filter(
                activo=True
            ).order_by("orden", "nombre"),
            "cortadores": (
                OperarioProduccion.objects
                .filter(
                    sucursal=sucursal,
                    activo=True,
                    especialidad__in=[
                        OperarioProduccion.Especialidad.CORTADOR,
                        OperarioProduccion.Especialidad.AMBOS,
                    ],
                )
                .order_by("nombre")
            ),
        }

    def get(self, request):
        return render(
            request,
            self.template_name,
            self.get_context_data(),
        )

    def post(self, request):
        try:
            sucursal = self.get_sucursal()
            rollos_data = []

            rollos_ids = request.POST.getlist("rollo_id[]")

            for rollo_id in rollos_ids:
                if not rollo_id:
                    continue

                metros = request.POST.get(
                    f"metros_{rollo_id}"
                )

                productos = request.POST.getlist(
                    f"producto_{rollo_id}[]"
                )
                tallas = request.POST.getlist(
                    f"talla_{rollo_id}[]"
                )
                cantidades = request.POST.getlist(
                    f"cantidad_{rollo_id}[]"
                )
                cortadores = request.POST.getlist(
                    f"cortadores_{rollo_id}[]"
                )

                longitudes = {
                    len(productos),
                    len(tallas),
                    len(cantidades),
                    len(cortadores),
                }

                if len(longitudes) != 1:
                    raise ValidationError(
                        "Las líneas de producción están incompletas."
                    )

                items = []

                for (
                    producto_id,
                    talla,
                    cantidad,
                    cortadores_csv,
                ) in zip(
                    productos,
                    tallas,
                    cantidades,
                    cortadores,
                ):
                    if not cantidad:
                        continue

                    operario_ids = [
                        int(operario_id)
                        for operario_id in cortadores_csv.split(",")
                        if operario_id.strip()
                    ]
                    if not operario_ids:
                        raise ValidationError(
                            "Debe seleccionar al menos un cortador "
                            "de cada prenda."
                        )

                    items.append(
                        {
                            "producto_base_id": int(producto_id),
                            "talla": talla,
                            "cantidad": int(cantidad),
                            "operario_ids": operario_ids,
                        }
                    )

                if not items:
                    raise ValidationError(
                        "Cada rollo debe tener al menos "
                        "una prenda."
                    )

                rollos_data.append(
                    {
                        "rollo_id": rollo_id,
                        "metros": metros,
                        "items": items,
                    }
                )

            lote = CorteService.ejecutar_corte(
                rollos=rollos_data,
                sucursal=sucursal,
                usuario=request.user,
            )

            return redirect("inventory:corte_produccion")

        except ValidationError as error:
            context = self.get_context_data()
            context["error_message"] = error.messages[0]

            return render(
                request,
                self.template_name,
                context,
            )

        except Exception:
            context = self.get_context_data()
            context["error_message"] = (
                "No fue posible registrar el corte. "
                "Revise los datos e intente nuevamente."
            )

            return render(
                request,
                self.template_name,
                context,
            )

        return render(
            request,
            self.template_name,
            self.get_context_data(),
        )
