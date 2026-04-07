# apps/sales/views.py
import json
from decimal import Decimal

from django.views import View
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q, Prefetch

from apps.core.models import Sucursal
from apps.core.models import Sucursal
from apps.inventory.models import ProductoVariante, Stock
from apps.sales.models import Caja
from apps.sales.services.pos_service import POSService
from apps.sales.services.serializers import serializar_venta
from .services.caja_service import CajaService
from .mixins import SucursalIsolationMixin
from .permissions import RolePermissionMixin


# =========================
# Helper JSON Responses
# =========================
def success(data=None):
    """Respuesta JSON estandarizada para éxito"""
    return JsonResponse({"success": True, "data": data or {}})


def error(message):
    """Respuesta JSON estandarizada para error"""
    return JsonResponse({"success": False, "error": str(message)})


# =========================
# POS PRINCIPAL
# =========================
class POSView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def get(self, request):
        sucursal = self.get_sucursal()
        turno = CajaService.obtener_turno_abierto(sucursal)

        if not turno:
            # Redirigir a abrir caja si no hay turno activo
            return redirect("sales:abrir_caja")

        venta = POSService.obtener_venta_abierta(usuario=request.user, sucursal=sucursal)
        venta_data = serializar_venta(venta) if venta else {
            "id": None,
            "subtotal": 0,
            "iva": 0,
            "total": 0,
            "items": []
        }

        return render(request, "sales/pos.html", {
            "turno": turno,
            "venta": venta_data,
            "sucursal": sucursal
        })


# =========================
# AGREGAR PRODUCTO
# =========================
class POSAgregarProductoView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            data = json.loads(request.body)
            variante_id = data.get("variante_id")
            cantidad = Decimal(str(data.get("cantidad", 1)))
            termino = data.get("termino")

            venta = POSService.agregar_producto(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                variante_id=variante_id,
                termino=termino,
                cantidad=cantidad
            )

            return success(venta)

        except Exception as e:
            return error(e)


# =========================
# ACTUALIZAR CANTIDAD
# =========================
class POSActualizarCantidadView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            data = json.loads(request.body)
            cantidad = Decimal(str(data.get("cantidad", 0)))
            venta_data = POSService.actualizar_cantidad(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                item_id=data.get("item_id"),
                cantidad=cantidad
            )
            return success(venta_data)

        except Exception as e:
            return error(e)


# =========================
# ELIMINAR ITEM
# =========================
class POSEliminarItemView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            data = json.loads(request.body)
            venta_data = POSService.eliminar_item(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                item_id=data.get("item_id")
            )
            return success(venta_data)

        except Exception as e:
            return error(e)


# =========================
# CERRAR VENTA
# =========================
class POSCerrarVentaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            data = json.loads(request.body)
            pagos = {
                "EFECTIVO": Decimal(str(data.get("efectivo", 0))),
                "TARJETA": Decimal(str(data.get("tarjeta", 0))),
                "TRANSFERENCIA": Decimal(str(data.get("transferencia", 0))),
            }

            venta = POSService.cerrar_venta(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                pagos=pagos
            )

            return success({"reset": True, "total": str(venta.total)})

        except Exception as e:
            return error(e)


# =========================
# CANCELAR VENTA
# =========================
class POSCancelarVentaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            POSService.cancelar_venta(
                usuario=request.user,
                sucursal=self.get_sucursal()
            )
            return success()
        except Exception as e:
            return error(e)


# =========================
# AUTOCOMPLETE DE PRODUCTO
# =========================
class ProductoAutocompleteView(LoginRequiredMixin, SucursalIsolationMixin, View):
    def get(self, request):
        q = request.GET.get("q", "").strip()
        if len(q) < 2:
            return JsonResponse({"results": []})

        sucursal = self.get_sucursal()

        variantes = ProductoVariante.objects.select_related(
            "producto_base", "color", "tipo_tela"
        ).filter(
            Q(producto_base__nombre__icontains=q) |
            Q(sku__icontains=q) |
            Q(talla__icontains=q) |
            Q(color__nombre__icontains=q) |
            Q(tipo_tela__nombre__icontains=q)
        ).order_by("producto_base__nombre")[:25]

        resultados = []
        for v in variantes:
            stock = v.stocks.filter(sucursal=sucursal).first()
            cantidad = stock.cantidad if stock else 0
            if cantidad > 0:
                resultados.append({
                    "id": v.id,
                    "nombre": f"{v.producto_base.nombre} - {v.color.nombre} - {v.tipo_tela.nombre} - {v.talla}",
                    "sku": v.sku,
                    "stock": float(cantidad),
                })

        return JsonResponse({"results": resultados})


# =========================
# CAMBIAR TIPO DE VENTA
# =========================
class POSCambiarTipoVentaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            data = json.loads(request.body)
            venta_data = POSService.cambiar_tipo_venta(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                tipo=data.get("tipo")
            )
            return success(venta_data)
        except Exception as e:
            return error(e)


# =========================
# ABRIR CAJA
# =========================
class AbrirCajaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def get(self, request):
        sucursal = self.get_sucursal()
        cajas = Caja.objects.filter(sucursal=sucursal)
        if not cajas.exists():
            return render(request, "sales/abrir_caja.html", {"error": "No hay cajas registradas en esta sucursal."})
        return render(request, "sales/abrir_caja.html", {"cajas": cajas})

    def post(self, request):
        sucursal = self.get_sucursal()
        caja_id = request.POST.get("caja_id")
        monto = Decimal(request.POST.get("monto_inicial", "0"))

        try:
            CajaService.abrir_caja(sucursal=sucursal, usuario=request.user, monto_inicial=monto, caja_id=caja_id)
            messages.success(request, "Caja abierta correctamente.")
            return redirect("sales:pos")
        except Exception as e:
            return render(request, "sales/abrir_caja.html", {"error": str(e), "cajas": Caja.objects.filter(sucursal=sucursal)})


# =========================
# CERRAR CAJA
# =========================
class CerrarCajaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            CajaService.cerrar_caja(
                sucursal=self.get_sucursal(),
                usuario=request.user,
                monto_real=Decimal(request.POST.get("monto_real", "0"))
            )
            messages.success(request, "Caja cerrada correctamente.")
            return redirect("dashboard")
        except Exception as e:
            messages.error(request, str(e))
            return redirect("sales:pos")

        
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def seleccionar_sucursal(request):
    if request.method == "POST":
        sucursal_id = request.POST.get("sucursal_id")
        request.session['sucursal_id'] = sucursal_id
        return redirect("sales:pos")  # Ir al POS

    # Mostrar solo las sucursales activas
    sucursales = Sucursal.objects.all()
    return render(request, "sales/seleccionar_sucursal.html", {"sucursales": sucursales})