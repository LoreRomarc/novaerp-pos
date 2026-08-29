# apps/inventory/views_produccion.py
from django.core.exceptions import ValidationError
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
from apps.sales.mixins import SucursalIsolationMixin


class CorteProduccionView(SucursalIsolationMixin, View):
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
            "colores": Color.objects.all().order_by("nombre"),
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
                telas = request.POST.getlist(
                    f"tela_{rollo_id}[]"
                )
                colores = request.POST.getlist(
                    f"color_{rollo_id}[]"
                )
                tallas = request.POST.getlist(
                    f"talla_{rollo_id}[]"
                )
                cantidades = request.POST.getlist(
                    f"cantidad_{rollo_id}[]"
                )
                cortadores = request.POST.getlist(
                    f"cortador_{rollo_id}[]"
                )

                longitudes = {
                    len(productos),
                    len(telas),
                    len(colores),
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
                    tela_id,
                    color_id,
                    talla,
                    cantidad,
                    cortador_id,
                ) in zip(
                    productos,
                    telas,
                    colores,
                    tallas,
                    cantidades,
                    cortadores,
                ):
                    if not cantidad:
                        continue

                    if not cortador_id:
                        raise ValidationError(
                            "Debe seleccionar el cortador "
                            "de cada prenda."
                        )

                    items.append(
                        {
                            "producto_base_id": int(producto_id),
                            "tipo_tela_id": int(tela_id),
                            "color_id": int(color_id),
                            "talla": talla,
                            "cantidad": int(cantidad),
                            "operario_id": int(cortador_id),
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