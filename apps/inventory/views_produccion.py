# apps/inventory/views_corte.py
from django.shortcuts import render, redirect
from django.core.exceptions import ValidationError
from django.contrib import messages
from django.views import View

from apps.inventory.models_produccion import RolloTela
from apps.inventory.models import ProductoBase
from apps.inventory.services.corte_service import CorteService


class CorteProduccionView(View):

    template_name = "inventory/corte_produccion.html"

    def get(self, request):
        rollos = RolloTela.objects.filter(estado="DISPONIBLE")
        productos = ProductoBase.objects.filter(activo=True)

        return render(request, self.template_name, {
            "rollos": rollos,
            "productos": productos
        })

    def post(self, request):

        try:
            rollo_id = request.POST.get("rollo")
            es_completo = request.POST.get("es_completo") == "on"
            metros = request.POST.get("metros")

            items = []

            productos = request.POST.getlist("producto_base")
            tallas = request.POST.getlist("talla")
            cantidades = request.POST.getlist("cantidad")

            for p, t, c in zip(productos, tallas, cantidades):
                if c and int(c) > 0:
                    items.append({
                        "producto_base_id": int(p),
                        "talla": t,
                        "cantidad": int(c)
                    })

            CorteService.ejecutar_corte(
                rollo_id=rollo_id,
                es_completo=es_completo,
                metros_usados=metros,
                items=items
            )

            messages.success(request, "✅ Corte ejecutado correctamente.")
            return redirect("inventory:corte_produccion")

        # ✅ CAPTURA CORRECTA
        except ValidationError as e:

            if hasattr(e, "messages"):
                for msg in e.messages:
                    messages.error(request, f"❌ {msg}")
            else:
                messages.error(request, f"❌ {str(e)}")

            return redirect("inventory:corte_produccion")

        except Exception as e:
            messages.error(request, f"❌ Error inesperado: {str(e)}")
            return redirect("inventory:corte_produccion")