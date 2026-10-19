# apps/sales/views.py
import json
import logging
import sys

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.inventory.models import ProductoVariante, Stock, normalizar_busqueda
from apps.customers.models import Cliente
from apps.sales.models import (
    ConfiguracionImpresionVenta,
    Venta,
    Vendedor,
    VendedorPreferenciaPOS,
)
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

    def dispatch(self, request, *args, **kwargs):
        """No permite vender con un turno de un día anterior sin decisión."""
        if request.user.is_authenticated:
            perfil = getattr(request.user, "profile", None)
            if perfil:
                try:
                    sucursal = self.get_sucursal()
                except ValidationError:
                    sucursal = None

                if sucursal:
                    turno = CajaService.obtener_turno_operable(
                        sucursal=sucursal,
                        usuario=request.user,
                    )

                    confirmado = str(
                        request.session.get("turno_diario_confirmado_id", "")
                    ) == str(getattr(turno, "id", ""))
                    continuar = (
                        request.session.get("turno_diario_modo")
                        == "CONTINUAR"
                    )

                    if (
                        CajaService.turno_requiere_confirmacion_diaria(turno)
                        and not (confirmado and continuar)
                    ):
                        request.session["turno_diario_pendiente_id"] = turno.id
                        request.session["turno_diario_siguiente"] = request.get_full_path()
                        request.session.modified = True
                        if request.method == "GET":
                            return redirect("sales:turno_diario")
                        return error(
                            "Debe decidir si continúa o cierra el turno del día anterior."
                        )

        return super().dispatch(request, *args, **kwargs)

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

        turno = CajaService.obtener_turno_operable(
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

        vendedores_todos = list(
            Vendedor.objects.filter(activo=True).annotate(
                es_vendedora_fija=Case(
                    When(sucursal=sucursal, then=Value(0)),
                    default=Value(1),
                    output_field=IntegerField(),
                )
            ).select_related("sucursal").order_by("es_vendedora_fija", "nombre", "id")
        )
        preferencias = {
            preferencia.vendedor_id: preferencia.visible
            for preferencia in VendedorPreferenciaPOS.objects.filter(
                usuario=request.user,
                sucursal=sucursal,
                vendedor__in=vendedores_todos,
            )
        }
        vendedores_visibles = [
            vendedor for vendedor in vendedores_todos
            if preferencias.get(vendedor.id, True)
        ]
        configuracion_impresion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
            sucursal=sucursal,
        )
        # El navegador es quien conoce las impresoras del PC del cajero. En
        # Render/Linux no existe acceso a la impresora Windows del usuario,
        # por lo que siempre se abre el comprobante para imprimir o guardar.
        usar_impresion_directa = (
            configuracion_impresion.impresion_automatica
            and sys.platform == "win32"
        )

        return render(
            request,
            "sales/pos.html",
            {
                "turno": turno,
                "sucursal": sucursal,
                # Todas las vendedoras activas pueden vender en cualquier
                # sede. Se priorizan visualmente las fijas de esta sucursal.
                "vendedores": vendedores_visibles,
                "vendedores_configuracion": vendedores_todos,
                "vendedores_visibles_ids": [vendedor.id for vendedor in vendedores_visibles],
                "clientes_pos": Cliente.objects.filter(activo=True).order_by("nombre")[:500],
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
                "impresion_ticket_navegador": not usar_impresion_directa,
                "impresion_automatica": configuracion_impresion.impresion_automatica,
            },
        )


class POSVendedoresVisiblesView(POSBaseView):
    """Guarda el filtro personal de vendedores mostrado por el POS."""

    def post(self, request):
        try:
            data = self.obtener_json(request)
            ids = data.get("vendedor_ids", [])
            if not isinstance(ids, list):
                raise ValidationError("La selección de vendedores es inválida.")
            ids = {int(vendedor_id) for vendedor_id in ids}
            sucursal = self.get_sucursal()
            vendedores = list(Vendedor.objects.filter(activo=True))
            ids_validos = {vendedor.id for vendedor in vendedores}
            if not ids.issubset(ids_validos):
                raise ValidationError("La selección contiene un vendedor no disponible.")

            preferencias = [
                VendedorPreferenciaPOS(
                    usuario=request.user,
                    sucursal=sucursal,
                    vendedor=vendedor,
                    visible=vendedor.id in ids,
                )
                for vendedor in vendedores
            ]
            VendedorPreferenciaPOS.objects.filter(
                usuario=request.user,
                sucursal=sucursal,
            ).delete()
            VendedorPreferenciaPOS.objects.bulk_create(preferencias)
            return success({"vendedor_ids": sorted(ids)})
        except (ValidationError, ValueError) as error_validacion:
            return error(error_validacion)


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
            permitir_credito = bool(data.get("credito", False))

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
                vendedor_id=data.get("vendedor_id"),
                permitir_credito=permitir_credito,
            )

            venta = (
                Venta.objects.select_related(
                    "sucursal",
                    "sucursal__empresa",
                    "turno",
                    "turno__caja",
                    "usuario",
                    "vendedor",
                )
                .prefetch_related("items")
                .get(pk=venta.pk)
            )
            nuevo_carrito = CarritoService.crear(
                usuario=request.user,
                sucursal=venta.sucursal,
            )
            configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
                sucursal=venta.sucursal,
            )
            error_impresion = ""
            impresion_directa = False
            if configuracion.impresion_automatica and sys.platform == "win32":
                try:
                    from apps.sales.services.impresion_termica_service import ImpresionTermicaService

                    ImpresionTermicaService.imprimir_venta(venta, configuracion)
                    impresion_directa = True
                except ValidationError as error_impresion_directa:
                    error_impresion = error_impresion_directa.messages[0]
                except Exception:
                    logger.exception("Error al imprimir comprobante de venta %s.", venta.id)
                    error_impresion = "La venta se registró, pero no fue posible enviarla a la impresora."

            return success(
                {
                    "reset": True,
                    "venta_id": venta.id,
                    "total": str(venta.total),
                    "estado": venta.estado,
                    "saldo_pendiente": str(venta.saldo_pendiente),
                    "ticket_url": (
                        reverse("sales:ticket_venta", kwargs={"pk": venta.id})
                        + "?autoprint=1"
                    ),
                    "payload_impresion_url": reverse(
                        "sales:ticket_venta_payload", kwargs={"pk": venta.id}
                    ),
                    "imprimir_ticket": not (
                        configuracion.impresion_automatica
                        and sys.platform == "win32"
                    ),
                    "impresion_directa": impresion_directa,
                    "error_impresion": error_impresion,
                    "nuevo_carrito": serializar_carrito(nuevo_carrito),
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
        return variante.nombre_completo

    def get(self, request):
        q = request.GET.get("q", "").strip()

        if len(q) < 2:
            return JsonResponse({"results": []})

        try:
            sucursal = self.get_sucursal()

            base_variantes = (
                ProductoVariante.objects
                .select_related(
                    "producto_base",
                    "color",
                    "tipo_tela",
                    "talla",
                )
                .filter(activo=True)
            )
            # El lector HID escribe el código y termina con Enter. Dar
            # prioridad al código exacto evita que una coincidencia por nombre
            # agregue una variante diferente.
            coincidencia_codigo = list(
                base_variantes.filter(codigo_barras__iexact=q)[:1]
            )
            if coincidencia_codigo:
                variantes = coincidencia_codigo
            else:
                # Búsqueda portable sin tildes: funciona igual en SQLite,
                # PostgreSQL local y Render sin requerir extensiones del motor.
                termino = normalizar_busqueda(q)
                variantes = []
                for variante in base_variantes.order_by("producto_base__nombre", "sku"):
                    texto = " ".join((
                        variante.nombre_completo,
                        variante.sku or "",
                        variante.codigo_barras or "",
                    ))
                    if termino in normalizar_busqueda(texto):
                        variantes.append(variante)
                        if len(variantes) == 25:
                            break

            # Se consulta el stock de la sucursal activa directamente. Así un
            # producto devuelto en esta sede aparece aunque existan registros
            # de stock en otras sucursales o el prefetch cambie de orden.
            stocks_actuales = {
                stock.variante_id: stock.cantidad
                for stock in Stock.objects.filter(
                    sucursal=sucursal,
                    variante_id__in=[variante.id for variante in variantes],
                )
            }
            stocks_otras = {}
            for stock in Stock.objects.select_related("sucursal").filter(
                variante_id__in=[variante.id for variante in variantes],
            ).exclude(sucursal=sucursal):
                stocks_otras.setdefault(stock.variante_id, []).append({
                    "sucursal": stock.sucursal.nombre,
                    "cantidad": float(stock.cantidad),
                })

            resultados = []

            for variante in variantes:
                cantidad_actual = stocks_actuales.get(variante.id, 0)

                resultados.append(
                    {
                        "id": variante.id,
                        "nombre": self._nombre_producto(variante),
                        "sku": variante.sku,
                        "codigo_barras": variante.codigo_barras or "",
                        "coincidencia_codigo": bool(coincidencia_codigo),
                        "stock": float(cantidad_actual),
                        "sin_stock": cantidad_actual <= 0,
                        "otras_sucursales": stocks_otras.get(variante.id, []),
                    }
                )

            return JsonResponse(
                {
                    "results": resultados,
                    "coincidencia_codigo": bool(coincidencia_codigo),
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
                vendedor_id=data.get("vendedor_id"),
            )

            return success(venta)

        except ValidationError as error_validacion:
            return error(error_validacion)

        except Exception:
            return error(
                "No fue posible guardar la venta.",
                status=500,
            )
