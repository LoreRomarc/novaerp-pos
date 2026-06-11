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
            sucursal = BaseInventoryValidator.validar_usuario_y_sucursal(request.user)

            rollos_ids = request.POST.getlist("rollos[]")
            metros = request.POST.getlist("metros_rollo[]")

            productos = request.POST.getlist("producto_base[]")
            telas = request.POST.getlist("tipo_tela[]")
            colores = request.POST.getlist("color[]")
            tallas = request.POST.getlist("talla[]")
            cantidades = request.POST.getlist("cantidad[]")

            rollos_data = []

            for i in range(min(len(rollos_ids), len(metros))):
                if not metros[i]:
                    continue

                rollos_data.append({
                    "rollo_id": rollos_ids[i],
                    "metros": metros[i]
                })

            items = []

            for i in range(
                min(len(productos), len(telas), len(colores), len(tallas), len(cantidades))
            ):
                if not cantidades[i]:
                    continue

                items.append({
                    "producto_base_id": int(productos[i]),
                    "tipo_tela_id": int(telas[i]),
                    "color_id": int(colores[i]),
                    "talla": tallas[i],
                    "cantidad": cantidades[i],
                })

            lote = CorteService.ejecutar_corte(
                rollos=rollos_data,
                items=items,
                sucursal=sucursal,
                usuario=request.user
            )

            messages.success(request, f"Lote generado: {lote.referencia}")

        except Exception as e:
            messages.error(request, str(e))

        return redirect("inventory:corte_produccion")