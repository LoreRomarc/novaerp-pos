# apps/sales/views_devoluciones.py
import json
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import ListView

from apps.sales.mixins import SucursalIsolationMixin
from apps.inventory.models import ProductoVariante, Stock
from apps.sales.models import (
    Devolucion,
    ListaPrecio,
    PrecioVariante,
)
from apps.sales.permissions import RolePermissionMixin
from apps.sales.services.caja_service import CajaService
from apps.sales.services.devolucion_service import DevolucionService


logger = logging.getLogger(__name__)


DEVOLUCION_ROLES = [
    "SUPER_ADMIN",
    "ADMIN_SUCURSAL",
    "SUPERVISOR",
    "CAJERO",
]


class DevolucionBaseView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = DEVOLUCION_ROLES

    @staticmethod
    def obtener_json(request):
        try:
            data = json.loads(request.body or "{}")
        except json.JSONDecodeError as error:
            raise ValidationError(
                "La solicitud no contiene JSON válido."
            ) from error

        if not isinstance(data, dict):
            raise ValidationError(
                "La solicitud debe ser un objeto JSON."
            )

        return data

    def obtener_turno_activo(self):
        sucursal = self.get_sucursal()

        turno = CajaService.obtener_turno_activo_usuario(
            sucursal=sucursal,
            usuario=self.request.user,
        )

        if not turno:
            self.request.session.pop("turno_id", None)
            self.request.session.pop("caja_id", None)
            self.request.session.modified = True

            raise ValidationError(
                "Debe abrir una caja antes de procesar un cambio."
            )

        self.request.session["turno_id"] = turno.id
        self.request.session["caja_id"] = turno.caja_id
        self.request.session.modified = True

        return turno


class DevolucionListView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    ListView,
):
    model = Devolucion
    template_name = "sales/devoluciones/lista.html"
    context_object_name = "devoluciones"
    paginate_by = 30
    allowed_roles = DEVOLUCION_ROLES

    def get_queryset(self):
        sucursal = self.get_sucursal()

        qs = (
            Devolucion.objects
            .select_related(
                "venta",
                "usuario",
                "turno",
            )
            .filter(sucursal=sucursal)
            .order_by("-creada", "-id")
        )

        q = self.request.GET.get("q", "").strip()

        if q:
            filtros = (
                Q(referencia_externa__icontains=q)
                | Q(motivo__icontains=q)
                | Q(venta__cliente__icontains=q)
            )

            if q.isdigit():
                filtros |= (
                    Q(id=int(q))
                    | Q(venta_id=int(q))
                )

            qs = qs.filter(filtros)

        return qs


class CambioDirectoView(DevolucionBaseView):
    template_name = "sales/devoluciones/cambio_directo.html"

    def get(self, request):
        try:
            turno = self.obtener_turno_activo()

        except ValidationError as error:
            messages.warning(request, error.messages[0])
            return redirect("sales:abrir_caja")

        return render(
            request,
            self.template_name,
            {
                "turno": turno,
                "sucursal": self.get_sucursal(),
                "puede_modificar_precio": (
                    DevolucionService._usuario_puede_modificar_precio(
                        request.user
                    )
                ),
            },
        )


class CambioDirectoProcesarView(DevolucionBaseView):
    """
    Endpoint JSON consumido por cambio_directo.html.
    """

    def post(self, request):
        try:
            data = self.obtener_json(request)
            turno = self.obtener_turno_activo()

            devolucion = DevolucionService.procesar(
                usuario=request.user,
                sucursal=self.get_sucursal(),
                turno_id=turno.id,
                productos_recibidos=data.get(
                    "productos_recibidos",
                    [],
                ),
                productos_entregados=data.get(
                    "productos_entregados",
                    [],
                ),
                permite_reembolso=bool(
                    data.get("permite_reembolso", False)
                ),
                medio_reembolso=data.get(
                    "medio_reembolso",
                    "",
                ),
                pagos_adicionales={
                    "EFECTIVO": data.get("efectivo", 0),
                    "TARJETA": data.get("tarjeta", 0),
                    "TRANSFERENCIA": data.get(
                        "transferencia",
                        0,
                    ),
                },
                motivo=data.get("motivo", ""),
                venta_id=data.get("venta_id") or None,
                referencia_externa=data.get(
                    "referencia_externa",
                    "",
                ),
                tipo_venta=data.get(
                    "tipo_venta",
                    "MAYORISTA",
                ),
            )

            return JsonResponse(
                {
                    "success": True,
                    "data": {
                        "id": devolucion.id,
                        "tipo": devolucion.tipo,
                        "total_devuelto": str(
                            devolucion.total_devuelto
                        ),
                        "total_entregado": str(
                            devolucion.total_entregado
                        ),
                        "diferencia": str(
                            devolucion.diferencia
                        ),
                        "monto_cobrado": str(
                            devolucion.monto_cobrado
                        ),
                        "monto_reembolsado": str(
                            devolucion.monto_reembolsado
                        ),
                        "monto_no_reembolsado": str(
                            devolucion.monto_no_reembolsado
                        ),
                    },
                },
                status=201,
            )

        except ValidationError as error:
            return JsonResponse(
                {
                    "success": False,
                    "error": error.messages[0],
                },
                status=400,
            )

        except Exception:
            logger.exception(
                "Error procesando cambio o devolución directa."
            )

            return JsonResponse(
                {
                    "success": False,
                    "error": (
                        "No fue posible procesar la operación. "
                        "No se realizaron cambios."
                    ),
                },
                status=500,
            )

class CambioProductoBusquedaView(DevolucionBaseView):
    """
    Búsqueda para la pantalla de cambios.
    Busca por SKU, código de barras, nombre, tela, color o talla.
    """

    def get(self, request):
        q = request.GET.get("q", "").strip()
        tipo_venta = request.GET.get("tipo_venta", "MAYORISTA")

        if len(q) < 2:
            return JsonResponse({"results": []})

        if tipo_venta not in {"DETAL", "MAYORISTA"}:
            return JsonResponse(
                {
                    "results": [],
                    "error": "Tipo de venta inválido.",
                },
                status=400,
            )

        sucursal = self.get_sucursal()

        lista = (
            ListaPrecio.objects
            .filter(
                sucursal=sucursal,
                tipo_venta=tipo_venta,
                activa=True,
            )
            .order_by("id")
            .first()
        )

        if not lista:
            return JsonResponse(
                {
                    "results": [],
                    "error": (
                        "No existe lista de precios activa "
                        "para este tipo de venta."
                    ),
                },
                status=400,
            )

        variantes = list(
            ProductoVariante.objects
            .select_related(
                "producto_base",
                "tipo_tela",
                "color",
                "talla",
            )
            .filter(
                Q(sku__icontains=q)
                | Q(codigo_barras__icontains=q)
                | Q(producto_base__nombre__icontains=q)
                | Q(tipo_tela__nombre__icontains=q)
                | Q(color__nombre__icontains=q)
                | Q(talla__nombre__icontains=q)
            )
            .order_by(
                "producto_base__nombre",
                "sku",
            )[:25]
        )

        precios = {
            precio.variante_id: precio.precio
            for precio in PrecioVariante.objects.filter(
                lista=lista,
                variante_id__in=[
                    variante.id
                    for variante in variantes
                ],
            )
        }

        stocks = {
            stock.variante_id: stock.cantidad
            for stock in Stock.objects.filter(
                sucursal=sucursal,
                variante_id__in=[
                    variante.id
                    for variante in variantes
                ],
            )
        }

        resultados = []

        for variante in variantes:

            nombre = " - ".join(
                parte
                for parte in [
                    variante.producto_base.nombre,
                    variante.tipo_tela.nombre,
                    variante.color.nombre,
                    variante.talla.nombre,
                ]
                if parte
            )

            precio = precios.get(variante.id)

            resultados.append(
                {
                    "id": variante.id,
                    "nombre": nombre,
                    "sku": variante.sku,
                    "precio": (
                        str(precio)
                        if precio is not None
                        else None
                    ),
                    "sin_precio": precio is None,
                    "stock": str(stocks.get(variante.id, 0)),
                    "activo": variante.activo,
                }
            )

        return JsonResponse({"results": resultados})