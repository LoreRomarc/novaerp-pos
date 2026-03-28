# apps/inventory/views_corte.py
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.db import transaction

from apps.inventory.models import RolloTela, ProductoBase
from apps.inventory.services.corte_service import CorteService


@login_required
@permission_required("inventory.add_produccionlote", raise_exception=True)
def crear_corte(request):

    rollos = RolloTela.objects.filter(estado="DISPONIBLE", cantidad_disponible__gt=0)
    productos = ProductoBase.objects.filter(activo=True)

    if request.method == "POST":

        try:
            with transaction.atomic():

                rollo_id = request.POST.get("rollo")
                tipo_corte = request.POST.get("tipo_corte")

                es_completo = tipo_corte == "COMPLETO"
                metros = request.POST.get("metros_usados") or 0

                items = []

                productos_ids = request.POST.getlist("producto")
                tallas = request.POST.getlist("talla")
                cantidades = request.POST.getlist("cantidad")

                for i in range(len(productos_ids)):
                    if not productos_ids[i] or not cantidades[i]:
                        continue

                    items.append({
                        "producto_base_id": int(productos_ids[i]),
                        "talla": tallas[i],
                        "cantidad": int(cantidades[i])
                    })

                if not items:
                    raise Exception("Debe agregar al menos un item")

                CorteService.ejecutar_corte(
                    rollo_id=rollo_id,
                    es_completo=es_completo,
                    metros_usados=metros,
                    items=items
                )

                messages.success(request, "Corte ejecutado correctamente")
                return redirect("inventory:crear_corte")

        except Exception as e:
            messages.error(request, str(e))

    return render(request, "inventory/corte_form.html", {
        "rollos": rollos,
        "productos": productos
    })