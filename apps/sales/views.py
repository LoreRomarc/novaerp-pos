# apps/sales/views.py
import json
from decimal import Decimal
from django.shortcuts import get_object_or_404

from django.views import View
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import Q

from apps.core.models import Sucursal
from apps.core.models import Sucursal
from apps.inventory.models import ProductoVariante
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

        venta_uuid = request.GET.get("venta")

        venta = POSService.obtener_venta_abierta(
            usuario=request.user,
            sucursal=sucursal,
            venta_uuid=venta_uuid
        )

        venta_data = serializar_venta(venta) if venta else {
            "uuid": None,
            "id": None,
            "subtotal": 0,
            "iva": 0,
            "total": 0,
            "items": []
        }

        return render(request, "sales/pos.html", {
            "turno": turno,
            "venta": json.dumps(venta_data),
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
            venta_uuid = data.get("venta_uuid")

            try:
                cantidad = Decimal(str(data.get("cantidad") or "1"))
            except:
                cantidad = Decimal("1")

            termino = data.get("termino")

            venta = POSService.agregar_producto(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                venta_uuid=venta_uuid,
                variante_id=variante_id,
                termino=termino,
                cantidad=cantidad
            )

            return success(venta)

        except Exception as e:
            return error(str(e))

# =========================
# ACTUALIZAR CANTIDAD
# =========================
class POSActualizarCantidadView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):

    def post(self, request):
        try:
            data = json.loads(request.body)

            cantidad = data.get("cantidad")
            precio = data.get("precio_unitario")

            venta_data = POSService.actualizar_cantidad(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                venta_uuid=data.get("venta_uuid"),
                item_id=data.get("item_id"),
                cantidad=Decimal(str(cantidad)) if cantidad is not None else None,
                precio_unitario=Decimal(str(precio)) if precio is not None else None,
            )

            return success(venta_data)

        except Exception as e:
            return error(str(e))


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
                venta_uuid=data.get("venta_uuid"),
                item_id=data.get("item_id")
            )
            return success(venta_data)

        except Exception as e:
            return error(str(e))


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
                venta_uuid=data.get("venta_uuid"),
                pagos=pagos,
                cliente=data.get("cliente", ""),
                observaciones=data.get("observaciones", "")
            )

            return success({"reset": True, "total": str(venta.total)})

        except Exception as e:
            return error(str(e))


# =========================
# CANCELAR VENTA
# =========================
class POSCancelarVentaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO"]

    def post(self, request):
        try:
            data = json.loads(request.body)

            POSService.cancelar_venta(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                venta_uuid=data.get("venta_uuid")
            )

            return success()

        except Exception as e:
            return error(str(e))

# =========================
# AUTOCOMPLETE DE PRODUCTO
# =========================
class ProductoAutocompleteView(LoginRequiredMixin, SucursalIsolationMixin, View):
    def get(self, request):
        try:
            q = request.GET.get("q", "").strip()

            if len(q) < 2:
                return JsonResponse({"results": []})

            sucursal = self.get_sucursal()

            variantes = (
                ProductoVariante.objects
                .select_related(
                    "producto_base",
                    "color",
                    "tipo_tela",
                    "talla",
                )
                .prefetch_related(
                    "stocks__sucursal"
                )
                .filter(
                    Q(sku__icontains=q) |
                    Q(codigo_barras__icontains=q) |
                    Q(producto_base__nombre__icontains=q) |
                    Q(color__nombre__icontains=q) |
                    Q(tipo_tela__nombre__icontains=q) |
                    Q(talla__nombre__icontains=q)
                )
                .distinct()[:25]
            )

            results = []

            for v in variantes:
                stock_actual = (
                    v.stocks
                    .filter(
                        sucursal=sucursal
                    )
                    .first()
                )


                stock_sucursal_actual = (
                    stock_actual.cantidad
                    if stock_actual
                    else 0
                )


                stocks_otras_sucursales = []

                for stock in v.stocks.all():

                    if stock.sucursal_id != sucursal.id:

                        stocks_otras_sucursales.append({
                            "sucursal": stock.sucursal.nombre,
                            "cantidad": float(stock.cantidad)
                        })


                results.append({

                    "id": v.id,

                    "nombre": (
                        f"{v.producto_base.nombre} - "
                        f"{v.tipo_tela.nombre} - "
                        f"{v.color.nombre} - "
                        f"{v.talla.nombre}"
                    ),

                    "sku": v.sku,

                    "stock": float(stock_sucursal_actual),

                    "sin_stock": (
                        stock_sucursal_actual <= 0
                    ),

                    "otras_sucursales": stocks_otras_sucursales
                })


            return JsonResponse({"results": results})

        except Exception as e:
            import traceback
            return JsonResponse({
                "error": str(e),
                "trace": traceback.format_exc()
            }, status=500)


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
                venta_uuid=data.get("venta_uuid"),
                tipo=data.get("tipo")
            )
            return success(venta_data)
        except Exception as e:
            return error(str(e))


# =========================
# CARGAR VENTA POR UUID
# =========================

class POSCargarVentaView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View
):

    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO"
    ]


    def get(self, request):

        venta_uuid = request.GET.get(
            "uuid"
        )


        if not venta_uuid:
            return error(
                "UUID requerido"
            )


        venta = POSService.obtener_venta_abierta(
            usuario=request.user,
            sucursal=self.get_sucursal(),
            venta_uuid=venta_uuid
        )


        if not venta:
            return error(
                "La venta ya no está disponible."
            )


        return success(
            serializar_venta(venta)
        )

class POSGuardarEstadoView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View
):

    allowed_roles=[
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO"
    ]

    def post(self,request):

        data=json.loads(request.body)

        venta=POSService.guardar_estado(

            usuario=request.user,

            sucursal=self.get_sucursal(),

            venta_uuid=data["venta_uuid"],

            cliente=data.get("cliente",""),

            observaciones=data.get("observaciones",""),

            efectivo=data.get("efectivo",0),

            transferencia=data.get("transferencia",0),

            tarjeta=data.get("tarjeta",0)

        )

        return success(venta)
    
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