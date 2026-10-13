# apps/sales/views_devoluciones.py
import json
import logging

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView

from apps.sales.mixins import SucursalIsolationMixin
from apps.inventory.models import ProductoVariante, Stock
from apps.sales.models import (
    ConfiguracionImpresionVenta,
    Devolucion,
    ListaPrecio,
    PrecioVariante,
)
from apps.sales.permissions import RolePermissionMixin
from apps.sales.services.caja_service import CajaService
from apps.sales.services.devolucion_service import DevolucionService
from apps.sales.services.impresion_termica_service import ImpresionTermicaService


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

        turno = CajaService.obtener_turno_operable(
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
        medio_pago = self.request.GET.get("medio_pago", "").strip()

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

        # El medio de la devolución corresponde al movimiento de caja. Para
        # crédito también permitimos encontrar devoluciones ligadas a la venta
        # original, aun cuando esta ya se haya saldado posteriormente.
        if medio_pago in {"EFECTIVO", "TRANSFERENCIA"}:
            qs = qs.filter(movimientos_caja__medio_pago=medio_pago).distinct()
        elif medio_pago == "COMBINADO":
            qs = (
                qs.filter(movimientos_caja__medio_pago="EFECTIVO")
                .filter(movimientos_caja__medio_pago="TRANSFERENCIA")
                .distinct()
            )
        elif medio_pago == "CREDITO":
            qs = qs.filter(
                Q(venta__estado="CREDITO")
                | Q(venta__abonos__isnull=False)
            ).distinct()

        return qs


class DevolucionDetalleView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    """Fragmento JSON para consultar el comprobante sin abandonar el historial."""
    allowed_roles = DEVOLUCION_ROLES

    def get(self, request, pk):
        devolucion = get_object_or_404(
            Devolucion.objects.select_related("usuario", "venta", "turno")
            .prefetch_related(
                "items_devueltos__variante__producto_base",
                "items_entregados__variante__producto_base",
            ), pk=pk, sucursal=self.get_sucursal(),
        )
        return render(request, "sales/devoluciones/detalle_modal.html", {
            "devolucion": devolucion,
        })


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
                efectivo_recibido=data.get("efectivo_recibido", 0),
                vuelto_efectivo=data.get("vuelto_efectivo", 0),
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
                tipo_venta_recibido=data.get("tipo_venta_recibido"),
                tipo_venta_entregado=data.get("tipo_venta_entregado"),
            )

            configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
                sucursal=devolucion.sucursal,
            )
            error_impresion = ""
            impresion_directa = False
            if configuracion.impresion_automatica:
                try:
                    ImpresionTermicaService.imprimir_devolucion(
                        devolucion, configuracion
                    )
                    impresion_directa = True
                except ValidationError as error_impresion_directa:
                    error_impresion = error_impresion_directa.messages[0]
                except Exception:
                    logger.exception("Error al imprimir devolución %s.", devolucion.id)
                    error_impresion = "La devolución se registró, pero no fue posible enviarla a la impresora."

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
                        "ticket_url": reverse(
                            "sales:ticket_devolucion", kwargs={"pk": devolucion.id}
                        ) + ("" if impresion_directa else "?autoprint=1"),
                        "impresion_directa": impresion_directa,
                        "error_impresion": error_impresion,
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
                    "codigo_barras": variante.codigo_barras or "",
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
