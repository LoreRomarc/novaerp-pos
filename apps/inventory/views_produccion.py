# apps/inventory/views_produccion.py
from django.contrib import messages
from django.views import View

from apps.inventory.models import ProductoBase
from apps.inventory.models_produccion import RolloTela
from apps.inventory.services.base_validators import BaseInventoryValidator
from apps.inventory.services.corte_service import CorteService
from apps.sales.mixins import SucursalIsolationMixin
from django.shortcuts import redirect, render


class CorteProduccionView(SucursalIsolationMixin, View):

    template_name = "inventory/corte_produccion.html"

    def get(self, request):
        return render(request, self.template_name, {
            "rollos": RolloTela.objects.filter(estado="DISPONIBLE"),
            "productos": ProductoBase.objects.filter(activo=True)
        })

    def post(self, request):

        try:
            sucursal = BaseInventoryValidator.validar_usuario_y_sucursal(request.user)

            rollos_ids = request.POST.getlist("rollos[]")
            metros = request.POST.getlist("metros_rollo[]")

            productos = request.POST.getlist("producto_base")
            tallas = request.POST.getlist("talla")
            cantidades = request.POST.getlist("cantidad")

            rollos_data = []

            for i in range(len(rollos_ids)):
                if not metros[i]:
                    continue

                rollos_data.append({
                    "rollo_id": rollos_ids[i],
                    "metros": metros[i]
                })

            items = []
            for i in range(len(productos)):
                if not cantidades[i]:
                    continue

                items.append({
                    "producto_base_id": int(productos[i]),
                    "talla": tallas[i],
                    "cantidad": cantidades[i]
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