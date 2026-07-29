# apps/inventory/views_produccion.py
from django.contrib import messages
from django.views import View
from django.shortcuts import redirect, render

from apps.inventory.models_produccion import RolloTela
from apps.inventory.services.base_validators import BaseInventoryValidator
from apps.inventory.services.corte_service import CorteService
from apps.sales.mixins import SucursalIsolationMixin

from apps.inventory.models import (
    ProductoBase,
    TipoTela,
    Color,
    Talla,
)


class CorteProduccionView(SucursalIsolationMixin, View):

    template_name = "inventory/corte_produccion.html"

    def get(self, request):
        return render(request, self.template_name, {
            "rollos": RolloTela.objects.filter(estado="DISPONIBLE"),
            "productos": ProductoBase.objects.filter(activo=True),
            "telas": TipoTela.objects.filter(activo=True),
            "colores": Color.objects.all(),
            "tallas": Talla.objects.filter(activo=True),
        })

    def post(self, request):

        try:

            print("DEBUG USUARIO CORTE")
            print(request.user)
            print(request.user.is_authenticated)

            sucursal = BaseInventoryValidator.validar_usuario_y_sucursal(
                request.user
            )



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


                items=[]


                for i in range(len(productos)):


                    if not cantidades[i]:
                        continue


                    items.append({

                        "producto_base_id":
                            int(productos[i]),

                        "tipo_tela_id":
                            int(telas[i]),

                        "color_id":
                            int(colores[i]),

                        "talla":
                            tallas[i],

                        "cantidad":
                            int(cantidades[i])

                    })


                rollos_data.append({

                    "rollo_id":
                        rollo_id,

                    "metros":
                        metros,

                    "items":
                        items

                })


            lote = CorteService.ejecutar_corte(
                rollos=rollos_data,
                sucursal=sucursal,
                usuario=request.user
            )


            messages.success(
                request,
                f"Lote generado {lote.referencia}"
            )


        except Exception as e:

            messages.error(
                request,
                str(e)
            )


        return redirect(
            "inventory:corte_produccion"
        )
