# apps/sales/views.py
import json
from decimal import Decimal
from django.views import View
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q

from apps.inventory.models import Producto
from apps.sales.models import Caja, Venta
from apps.sales.services.pos_service import POSService
from apps.sales.services.serializers import serializar_venta


from .services.caja_service import CajaService
from .mixins import SucursalIsolationMixin
from .permissions import RolePermissionMixin


def success(data=None):
    return JsonResponse({"success": True, "data": data or {}})


def error(message):
    return JsonResponse({"success": False, "error": str(message)})


class POSView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    """
    Vista principal del POS estilo enterprise.

    COMPORTAMIENTO:
    - Si hay venta ABIERTA → la carga y la envía al frontend.
    - Si no hay venta → envía estructura vacía.
    - Refrescar la página NO pierde los ítems.
    """

    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def get(self, request):

        # ===============================
        # 1️  Obtener sucursal del usuario
        # ===============================
        sucursal = self.get_sucursal()

        # ===============================
        # 2️ Validar turno abierto
        # ===============================
        turno = CajaService.obtener_turno_abierto(sucursal)

        if not turno:
            return redirect("sales:abrir_caja")

        # ===============================
        # 3️ Obtener venta ABIERTA
        # ===============================
        venta = POSService.obtener_venta_abierta(
            usuario=request.user,
            sucursal=sucursal
        )

        # ===============================
        # 4️ Siempre enviar estructura válida
        # ===============================
        if venta:
            venta_data = serializar_venta(venta)
        else:
            venta_data = {
                "id": None,
                "subtotal": 0,
                "iva": 0,
                "total": 0,
                "items": []
            }

        # ===============================
        # 5️ Render
        # ===============================
        return render(
            request,
            "sales/pos.html",
            {
                "turno": turno,
                "venta": venta_data,
                "sucursal": sucursal,
            }
        )


class POSAgregarProductoView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            data = json.loads(request.body)

            venta = POSService.agregar_producto(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                producto_id=data.get("producto_id"),
                termino=data.get("termino"),
                cantidad=Decimal(str(data.get("cantidad", 1)))
            )

            return success(venta) 

        except Exception as e:
            return error(e)

class POSActualizarCantidadView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):

    def post(self, request):
        data = json.loads(request.body)
        venta_data = POSService.actualizar_cantidad(
            request.user,
            self.get_sucursal(),
            data.get("item_id"),
            Decimal(str(data.get("cantidad", 0)))
        )
        return success(venta_data)

class POSEliminarItemView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):

    def post(self, request):
        data = json.loads(request.body)
        venta_data = POSService.eliminar_item(
            request.user,
            self.get_sucursal(),
            data.get("item_id"),
        )
        return success(venta_data)
    
class POSCerrarVentaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            data = json.loads(request.body)

            venta = POSService.cerrar_venta(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                pagos={
                    "EFECTIVO": data.get("efectivo", 0),
                    "TRANSFERENCIA": data.get("transferencia", 0),
                    "TARJETA": data.get("tarjeta", 0),
                }
            )

            return success({"reset": True, "total": str(venta.total)})

        except Exception as e:
            return error(e)

class POSCancelarVentaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):

    def post(self, request):
        POSService.cancelar_venta(request.user, self.get_sucursal())
        return success()
    
class POSAnularVentaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL"]

    def post(self, request, venta_id):
        try:
            POSService.anular_venta(
                sucursal=self.get_sucursal(),
                venta_id=venta_id
            )
            return success()
        except Exception as e:
            return error(e)

class AbrirCajaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["CAJERO", "SUPER_ADMIN", "ADMIN_SUCURSAL"]

    def get(self, request):
        sucursal = self.get_sucursal()
        cajas = Caja.objects.filter(sucursal=sucursal)

        if not cajas.exists():
            return render(
                request,
                "sales/abrir_caja.html",
                {"error": "No hay cajas registradas en esta sucursal."}
            )

        return render(
            request,
            "sales/abrir_caja.html",
            {"cajas": cajas}
        )

    def post(self, request):
        sucursal = self.get_sucursal()
        caja_id = request.POST.get("caja_id")
        monto = Decimal(request.POST.get("monto_inicial", "0"))

        try:
            CajaService.abrir_caja(
                sucursal=sucursal,
                usuario=request.user,
                monto_inicial=monto,
                caja_id=caja_id
            )
            messages.success(request, "Caja abierta correctamente.")
            return redirect("sales:pos")

        except Exception as e:
            return render(
                request,
                "sales/abrir_caja.html",
                {
                    "error": str(e),
                    "cajas": Caja.objects.filter(sucursal=sucursal)
                }
            )
        
class CerrarCajaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            CajaService.cerrar_caja(
                self.get_sucursal(),
                request.user,
                Decimal(request.POST.get("monto_real", "0"))
            )
            messages.success(request, "Caja cerrada correctamente.")
            return redirect("dashboard")
        except Exception as e:
            messages.error(request, e)
            return redirect("sales:pos")
        

class ProductoAutocompleteView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):

    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def get(self, request):
        q = request.GET.get("q", "").strip()

        if len(q) < 2:
            return success({"results": []})

        productos = (
            Producto.objects
            .filter(
                Q(nombre__icontains=q) |
                Q(codigo_barras__icontains=q),
                activo=True
            )
            .order_by("nombre")[:15]
        )

        resultados = [
            {
                "id": p.id,
                "nombre": p.nombre,
                "codigo": p.codigo_barras,
            }
            for p in productos
        ]

        return success({"results": resultados})
    

class POSCambiarTipoVentaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):

    def post(self, request):
        data = json.loads(request.body)

        venta_data = POSService.cambiar_tipo_venta(
            request.user,
            self.get_sucursal(),
            data.get("tipo")
        )

        return success(venta_data)