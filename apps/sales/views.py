# apps/sales/views.py
import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View

from apps.inventory.models import ProductoVariante
from apps.sales.services.carrito_service import CarritoService
from apps.sales.services.pos_service import POSService
from apps.sales.services.serializers import serializar_carrito
from apps.sales.services.caja_service import CajaService
from apps.sales.mixins import SucursalIsolationMixin
from apps.sales.permissions import RolePermissionMixin


POS_ROLES = [
    "SUPER_ADMIN",
    "ADMIN_SUCURSAL",
    "CAJERO",
]

logger = logging.getLogger(__name__)


def success(data=None, status=200):
    return JsonResponse(
        {
            "success": True,
            "data": {} if data is None else data,
        },
        status=status,
    )


def error(message, status=400):
    return JsonResponse(
        {
            "success": False,
            "error": str(message),
        },
        status=status,
    )


class POSBaseView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = POS_ROLES

    @staticmethod
    def obtener_json(request):
        try:
            data = json.loads(request.body or "{}")
        except json.JSONDecodeError as error_json:
            raise ValidationError(
                "El cuerpo de la solicitud no es JSON válido."
            ) from error_json

        if not isinstance(data, dict):
            raise ValidationError(
                "El cuerpo de la solicitud debe ser un objeto JSON."
            )

        return data


class POSView(POSBaseView):
    def get(self, request):
        sucursal = self.get_sucursal()

        turno = CajaService.obtener_turno_activo_usuario(
            sucursal=sucursal,
            usuario=request.user,
        )

        if not turno:
            request.session.pop("turno_id", None)
            request.session.pop("caja_id", None)
            request.session.modified = True

            return redirect("sales:abrir_caja")

        request.session["turno_id"] = turno.id
        request.session["caja_id"] = turno.caja_id
        request.session.modified = True

        carritos = list(
            POSService.obtener_carritos_abiertos(
                usuario=request.user,
                sucursal=sucursal,
            )
        )

        if carritos:
            carrito_actual = carritos[0]
        else:
            carrito_actual = CarritoService.crear(
                usuario=request.user,
                sucursal=sucursal,
            )
            carritos = [carrito_actual]

        return render(
            request,
            "sales/pos.html",
            {
                "turno": turno,
                "sucursal": sucursal,
                "venta": json.dumps(
                    serializar_carrito(carrito_actual)
                ),
                "carritos": json.dumps(
                    [
                        {
                            "uuid": str(carrito.uuid),
                            "cliente": carrito.cliente,
                            "estado": carrito.estado,
                            "total": str(carrito.total),
                        }
                        for carrito in carritos
                    ]
                ),
            },
        )


class POSAgregarProductoView(POSBaseView):
    def post(self, request):
        try:
            data = self.obtener_json(request)

            venta = POSService.agregar_producto(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                venta_uuid=data.get("venta_uuid"),
                variante_id=data.get("variante_id"),
                cantidad=data.get("cantidad", 1),
            )

            return success(venta)

        except ValidationError as error_validacion:
            return error(error_validacion)

        except Exception:
            return error(
                "No fue posible agregar el producto.",
                status=500,
            )


class POSActualizarCantidadView(POSBaseView):
    def post(self, request):
        try:
            data = self.obtener_json(request)

            venta = POSService.actualizar_cantidad(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                venta_uuid=data.get("venta_uuid"),
                item_id=data.get("item_id"),
                cantidad=data.get("cantidad"),
                precio_unitario=data.get("precio_unitario"),
            )

            return success(venta)

        except ValidationError as error_validacion:
            return error(error_validacion)

        except Exception:
            return error(
                "No fue posible actualizar el producto.",
                status=500,
            )


class POSEliminarItemView(POSBaseView):
    def post(self, request):
        try:
            data = self.obtener_json(request)

            venta = POSService.eliminar_item(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                venta_uuid=data.get("venta_uuid"),
                item_id=data.get("item_id"),
            )

            return success(venta)

        except ValidationError as error_validacion:
            return error(error_validacion)

        except Exception:
            return error(
                "No fue posible eliminar el producto.",
                status=500,
            )


class POSCerrarVentaView(POSBaseView):
    def post(self, request):
        try:
            data = self.obtener_json(request)

            venta = POSService.cerrar_venta(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                turno_id=request.session.get("turno_id"),
                venta_uuid=data.get("venta_uuid"),
                pagos={
                    "EFECTIVO": data.get("efectivo", 0),
                    "TARJETA": data.get("tarjeta", 0),
                    "TRANSFERENCIA": data.get(
                        "transferencia",
                        0,
                    ),
                },
                cliente=data.get("cliente", ""),
                observaciones=data.get("observaciones", ""),
            )

            return success(
                {
                    "reset": True,
                    "venta_id": venta.id,
                    "total": str(venta.total),
                }
            )

        except ValidationError as error_validacion:
            return error(error_validacion)

        except Exception:
            return error(
                "No fue posible finalizar la venta.",
                status=500,
            )


class POSCancelarVentaView(POSBaseView):
    def post(self, request):
        try:
            data = self.obtener_json(request)

            carritos = POSService.cancelar_venta(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                venta_uuid=data.get("venta_uuid"),
            )

            return success(carritos)

        except ValidationError as error_validacion:
            return error(error_validacion)

        except Exception:
            return error(
                "No fue posible cancelar la venta.",
                status=500,
            )


class POSAnularVentaView(POSBaseView):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "SUPERVISOR",
    ]

    def post(self, request):
        try:
            data = self.obtener_json(request)

            venta_id = data.get("venta_id")
            observacion = data.get("observacion", "")

            if not venta_id:
                raise ValidationError(
                    "Debe indicar la venta a anular."
                )

            venta = POSService.anular_venta(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                turno_id=request.session.get("turno_id"),
                venta_id=venta_id,
                observacion=observacion,
            )

            return success(
                {
                    "venta_id": venta.id,
                    "estado": venta.estado,
                    "mensaje": (
                        "Venta anulada y devolución registrada."
                    ),
                }
            )

        except ValidationError as error_validacion:
            return error(error_validacion)

        except Exception:
            logger.exception("Error al anular una venta desde el POS.")
            return error(
                "No fue posible anular la venta.",
                status=500,
            )


class ProductoAutocompleteView(POSBaseView):
    @staticmethod
    def _nombre_producto(variante):
        partes = [
            variante.producto_base.nombre,
            (
                variante.tipo_tela.nombre
                if variante.tipo_tela
                else ""
            ),
            (
                variante.color.nombre
                if variante.color
                else ""
            ),
            (
                variante.talla.nombre
                if variante.talla
                else ""
            ),
        ]

        return " - ".join(
            parte
            for parte in partes
            if parte
        )

    def get(self, request):
        q = request.GET.get("q", "").strip()

        if len(q) < 2:
            return JsonResponse({"results": []})

        try:
            sucursal = self.get_sucursal()

            variantes = (
                ProductoVariante.objects
                .select_related(
                    "producto_base",
                    "color",
                    "tipo_tela",
                    "talla",
                )
                .prefetch_related("stocks__sucursal")
                .filter(
                    Q(sku__icontains=q)
                    | Q(codigo_barras__icontains=q)
                    | Q(producto_base__nombre__icontains=q)
                    | Q(color__nombre__icontains=q)
                    | Q(tipo_tela__nombre__icontains=q)
                    | Q(talla__nombre__icontains=q)
                )
                .distinct()[:25]
            )

            resultados = []

            for variante in variantes:
                stocks = list(variante.stocks.all())

                stock_actual = next(
                    (
                        stock
                        for stock in stocks
                        if stock.sucursal_id == sucursal.id
                    ),
                    None,
                )

                cantidad_actual = (
                    stock_actual.cantidad
                    if stock_actual
                    else 0
                )

                resultados.append(
                    {
                        "id": variante.id,
                        "nombre": self._nombre_producto(variante),
                        "sku": variante.sku,
                        "stock": float(cantidad_actual),
                        "sin_stock": cantidad_actual <= 0,
                        "otras_sucursales": [
                            {
                                "sucursal": stock.sucursal.nombre,
                                "cantidad": float(stock.cantidad),
                            }
                            for stock in stocks
                            if stock.sucursal_id != sucursal.id
                        ],
                    }
                )

            return JsonResponse(
                {
                    "results": resultados,
                }
            )

        except Exception:
            return JsonResponse(
                {
                    "results": [],
                    "error": (
                        "No fue posible consultar los productos."
                    ),
                },
                status=500,
            )


class POSCambiarTipoVentaView(POSBaseView):
    def post(self, request):
        try:
            data = self.obtener_json(request)

            venta = POSService.cambiar_tipo_venta(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                venta_uuid=data.get("venta_uuid"),
                tipo=data.get("tipo"),
            )

            return success(venta)

        except ValidationError as error_validacion:
            return error(error_validacion)

        except Exception:
            return error(
                "No fue posible cambiar el tipo de venta.",
                status=500,
            )


class POSCargarVentaView(POSBaseView):
    def get(self, request):
        carrito_uuid = request.GET.get("uuid")

        if not carrito_uuid:
            return error("UUID requerido.")

        carrito = POSService.obtener_carrito_por_uuid(
            usuario=request.user,
            sucursal=self.get_sucursal(),
            carrito_uuid=carrito_uuid,
        )

        if not carrito:
            return error(
                "El carrito ya no está disponible.",
                status=404,
            )

        return success(serializar_carrito(carrito))


class POSGuardarEstadoView(POSBaseView):
    def post(self, request):
        try:
            data = self.obtener_json(request)

            venta = POSService.guardar_estado(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                venta_uuid=data.get("venta_uuid"),
                cliente=data.get("cliente", ""),
                observaciones=data.get("observaciones", ""),
                efectivo=data.get("efectivo", 0),
                transferencia=data.get("transferencia", 0),
                tarjeta=data.get("tarjeta", 0),
            )

            return success(venta)

        except ValidationError as error_validacion:
            return error(error_validacion)

        except Exception:
            return error(
                "No fue posible guardar la venta.",
                status=500,
            )
