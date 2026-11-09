from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.accounts.models import UserProfile
from apps.inventory.forms_etiquetas import ConfiguracionEtiquetaProductoForm
from apps.inventory.mixins import InventoryAccessMixin, SucursalScopedMixin
from apps.inventory.models import ConfiguracionEtiquetaProducto, ProductoVariante, Stock, normalizar_busqueda
from apps.inventory.services.etiquetas_service import generar_pdf_etiquetas


class EtiquetasAccessMixin(InventoryAccessMixin):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "INVENTARIO", "CAJERO"]


class EtiquetasProductoView(LoginRequiredMixin, EtiquetasAccessMixin, SucursalScopedMixin, View):
    template_name = "inventory/etiquetas_producto.html"

    def get(self, request):
        return render(request, self.template_name, {"sucursal": self.get_sucursal()})

    def post(self, request):
        sucursal = self.get_sucursal()
        ids = request.POST.getlist("variante_id")
        if not ids:
            messages.error(request, "Selecciona al menos una variante.")
            return redirect("inventory:etiquetas_producto")
        stocks = Stock.objects.select_related(
            "variante__producto_base", "variante__tipo_tela", "variante__color", "variante__talla"
        ).filter(sucursal=sucursal, cantidad__gt=0, variante_id__in=ids, variante__activo=True)
        por_id = {str(stock.variante_id): stock.variante for stock in stocks}
        items = []
        for variante_id in ids:
            variante = por_id.get(str(variante_id))
            if not variante:
                continue
            copias = min(max(int(request.POST.get(f"copias_{variante_id}") or 1), 1), 100)
            items.append((variante, copias))
        if not items:
            messages.error(request, "Las variantes seleccionadas no tienen stock en la sucursal activa.")
            return redirect("inventory:etiquetas_producto")
        configuracion = ConfiguracionEtiquetaProducto.obtener()
        respuesta = HttpResponse(generar_pdf_etiquetas(items, configuracion), content_type="application/pdf")
        respuesta["Content-Disposition"] = 'inline; filename="etiquetas-producto.pdf"'
        return respuesta


class EtiquetasBuscarAPIView(LoginRequiredMixin, EtiquetasAccessMixin, SucursalScopedMixin, View):
    def get(self, request):
        termino = request.GET.get("q", "").strip()
        if not termino:
            return JsonResponse([], safe=False)
        sucursal = self.get_sucursal()
        stocks = Stock.objects.select_related(
            "variante__producto_base", "variante__tipo_tela", "variante__color", "variante__talla"
        ).filter(sucursal=sucursal, cantidad__gt=0, variante__activo=True)
        directos = list(stocks.filter(
            Q(variante__codigo_barras__icontains=termino) | Q(variante__sku__icontains=termino) |
            Q(variante__producto_base__nombre__icontains=termino) | Q(variante__tipo_tela__nombre__icontains=termino) |
            Q(variante__color__nombre__icontains=termino) | Q(variante__talla__nombre__icontains=termino)
        ).order_by("variante__producto_base__nombre"))
        termino_normalizado = normalizar_busqueda(termino)
        resultado = list(directos)
        vistos = {stock.variante_id for stock in resultado}
        # Respaldo para instalaciones sin extensión unaccent: "sueter"
        # encuentra "SUÉTER" aun cuando PostgreSQL no ignore la tilde.
        for stock in stocks.order_by("variante__producto_base__nombre"):
            if stock.variante_id in vistos:
                continue
            texto = " ".join([stock.variante.nombre_completo, stock.variante.sku or "", stock.variante.codigo_barras or ""])
            if termino_normalizado in normalizar_busqueda(texto):
                resultado.append(stock)
                vistos.add(stock.variante_id)
            if len(resultado) >= 20:
                break
        return JsonResponse([{
            "id": stock.variante_id, "nombre": stock.variante.nombre_completo,
            "codigo": stock.variante.codigo_barras, "codigo_barras": stock.variante.codigo_barras,
            "sku": stock.variante.sku,
            "stock": str(stock.cantidad),
        } for stock in resultado], safe=False)


class EtiquetasConfiguracionView(LoginRequiredMixin, EtiquetasAccessMixin, View):
    template_name = "inventory/etiquetas_configuracion.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.profile.role != UserProfile.Role.SUPER_ADMIN:
            raise PermissionDenied("Solo Super Admin puede cambiar el diseño de etiquetas.")
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {"form": ConfiguracionEtiquetaProductoForm(instance=ConfiguracionEtiquetaProducto.obtener())})

    def post(self, request):
        form = ConfiguracionEtiquetaProductoForm(request.POST, instance=ConfiguracionEtiquetaProducto.obtener())
        if form.is_valid():
            form.save()
            messages.success(request, "Diseño de etiquetas actualizado.")
            return redirect("inventory:etiquetas_producto")
        return render(request, self.template_name, {"form": form})
