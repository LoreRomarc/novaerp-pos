# apps/sales/views_facturacion.py
"""Vistas de comprobantes térmicos de venta."""

import logging

from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from apps.sales.mixins import SucursalIsolationMixin
from apps.sales.models import ConfiguracionImpresionVenta, Devolucion, Venta
from apps.sales.permissions import RolePermissionMixin
from apps.sales.services.impresion_termica_service import ImpresionTermicaService


logger = logging.getLogger(__name__)


class TicketVentaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    """Muestra el comprobante de una venta finalizada, normal o a crédito."""

    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO", "SUPERVISOR"]
    template_name = "sales/ticket_venta.html"

    def get(self, request, pk):
        try:
            venta = (
                Venta.objects.select_related(
                    "sucursal", "sucursal__empresa", "turno", "turno__caja", "usuario", "vendedor"
                )
                .prefetch_related("items")
                .get(pk=pk, estado__in=["CERRADA", "CREDITO"])
            )
        except Venta.DoesNotExist as error:
            raise Http404("La venta solicitada no existe o no está finalizada.") from error

        perfil = request.user.profile
        if (
            perfil.role != "SUPER_ADMIN"
            and venta.sucursal_id != self.get_sucursal().id
        ):
            raise PermissionDenied("No puede consultar una venta de otra sucursal.")

        configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
            sucursal=venta.sucursal,
        )
        return render(
            request,
            self.template_name,
            {
                "venta": venta,
                "configuracion": configuracion,
                "auto_imprimir": request.GET.get("autoprint") == "1",
                "payload_impresion_url": reverse(
                    "sales:ticket_venta_payload", kwargs={"pk": venta.pk}
                ),
            },
        )


class TicketVentaPayloadImpresionView(
    LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View
):
    """Entrega un ticket autenticado para QZ Tray en el PC del usuario."""

    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO", "SUPERVISOR"]

    def get(self, request, pk):
        try:
            venta = Venta.objects.select_related(
                "sucursal", "sucursal__empresa", "turno", "turno__caja",
                "usuario", "vendedor",
            ).prefetch_related("items").get(pk=pk, estado__in=["CERRADA", "CREDITO"])
        except Venta.DoesNotExist as error:
            raise Http404("La venta solicitada no existe o no está finalizada.") from error

        perfil = request.user.profile
        if perfil.role != "SUPER_ADMIN" and venta.sucursal_id != self.get_sucursal().id:
            raise PermissionDenied("No puede imprimir una venta de otra sucursal.")

        configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
            sucursal=venta.sucursal,
        )
        if not configuracion.impresion_automatica:
            raise PermissionDenied("La impresión automática está desactivada.")
        return JsonResponse(ImpresionTermicaService.payload_venta_qz(venta, configuracion))


class TicketDevolucionView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    """Comprobante independiente: una devolución nunca reutiliza una venta."""

    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO", "SUPERVISOR"]
    template_name = "sales/ticket_devolucion.html"

    def get(self, request, pk):
        try:
            devolucion = (
                Devolucion.objects.select_related(
                    "sucursal", "sucursal__empresa", "turno", "turno__caja", "usuario", "venta"
                )
                .prefetch_related("items_devueltos__variante", "items_entregados__variante")
                .get(pk=pk)
            )
        except Devolucion.DoesNotExist as error:
            raise Http404("El comprobante de devolución no existe.") from error

        perfil = request.user.profile
        if perfil.role != "SUPER_ADMIN" and devolucion.sucursal_id != self.get_sucursal().id:
            raise PermissionDenied("No puede consultar una devolución de otra sucursal.")

        configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
            sucursal=devolucion.sucursal,
        )
        return render(request, self.template_name, {
            "devolucion": devolucion,
            "configuracion": configuracion,
            "auto_imprimir": request.GET.get("autoprint") == "1",
            "payload_impresion_url": reverse(
                "sales:ticket_devolucion_payload", kwargs={"pk": devolucion.pk}
            ),
        })


class TicketDevolucionPayloadImpresionView(
    LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View
):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL", "CAJERO", "SUPERVISOR"]

    def get(self, request, pk):
        try:
            devolucion = Devolucion.objects.select_related(
                "sucursal", "sucursal__empresa", "turno", "turno__caja", "usuario", "venta"
            ).prefetch_related("items_devueltos__variante", "items_entregados__variante").get(pk=pk)
        except Devolucion.DoesNotExist as error:
            raise Http404("El comprobante de devolución no existe.") from error
        perfil = request.user.profile
        if perfil.role != "SUPER_ADMIN" and devolucion.sucursal_id != self.get_sucursal().id:
            raise PermissionDenied("No puede imprimir una devolución de otra sucursal.")
        configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
            sucursal=devolucion.sucursal,
        )
        if not configuracion.impresion_automatica:
            raise PermissionDenied("La impresión automática está desactivada.")
        return JsonResponse(
            ImpresionTermicaService.payload_devolucion_qz(devolucion, configuracion)
        )


class ConfiguracionImpresionVentaView(
    LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View
):
    """Configura el ticket de la sucursal activa."""

    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL"]
    template_name = "sales/configuracion_impresion.html"

    def _contexto(self, sucursal, configuracion, error=None):
        return {
            "sucursal": sucursal,
            "configuracion": configuracion,
            "error": error,
            "url_ticket_prueba": reverse("sales:ticket_prueba"),
            "url_impresion_prueba_directa": reverse("sales:impresion_prueba_directa"),
            "url_ticket_prueba_payload": reverse("sales:ticket_prueba_payload"),
        }

    def get(self, request):
        sucursal = self.get_sucursal()
        configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
            sucursal=sucursal,
        )
        # Esta pantalla no debe arrastrar notificaciones de otros módulos.
        # Se consumen para que el ticket no se convierta en una bandeja global.
        list(get_messages(request))
        if configuracion.modo_impresion != "QZ_PIXEL":
            configuracion.modo_impresion = "QZ_PIXEL"
            configuracion.save(update_fields=["modo_impresion", "actualizado"])
        return render(request, self.template_name, self._contexto(sucursal, configuracion))

    def post(self, request):
        sucursal = self.get_sucursal()
        configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
            sucursal=sucursal,
        )
        configuracion.impresion_automatica = (
            request.POST.get("impresion_automatica") == "on"
        )
        try:
            ancho_papel_mm = int(request.POST.get("ancho_papel_mm", ""))
        except (TypeError, ValueError):
            ancho_papel_mm = 0
        if not 20 <= ancho_papel_mm <= 120:
            return render(
                request,
                self.template_name,
                self._contexto(
                    sucursal, configuracion,
                    "El ancho debe estar entre 20 y 120 mm.",
                ),
                status=400,
            )
        configuracion.ancho_papel_mm = ancho_papel_mm
        configuracion.modo_impresion = "QZ_PIXEL"
        configuracion.nombre_impresora = (request.POST.get("nombre_impresora") or "").strip()
        configuracion.cortar_papel = request.POST.get("cortar_papel") == "on"
        configuracion.mensaje_pie = (request.POST.get("mensaje_pie") or "").strip()
        try:
            configuracion.full_clean()
            configuracion.save()
        except ValidationError as error:
            return render(
                request,
                self.template_name,
                self._contexto(sucursal, configuracion, " ".join(error.messages)),
                status=400,
            )
        return redirect("sales:configuracion_impresion")


class ImpresionPruebaDirectaView(
    LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View
):
    """Compatibilidad: abre la prueba para impresión desde el navegador."""

    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL"]

    def post(self, request):
        sucursal = self.get_sucursal()
        configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
            sucursal=sucursal,
        )
        return redirect(f"{reverse('sales:ticket_prueba')}?autoprint=1")


class TicketPruebaView(LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View):
    """Emite un ticket sin transacción para probar tamaño, margen y driver."""

    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL"]
    template_name = "sales/ticket_prueba.html"

    def get(self, request):
        sucursal = self.get_sucursal()
        configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
            sucursal=sucursal,
        )
        return render(
            request,
            self.template_name,
            {
                "sucursal": sucursal,
                "configuracion": configuracion,
                "auto_imprimir": request.GET.get("autoprint") == "1",
                "payload_impresion_url": reverse("sales:ticket_prueba_payload"),
            },
        )


class TicketPruebaPayloadImpresionView(
    LoginRequiredMixin, RolePermissionMixin, SucursalIsolationMixin, View
):
    allowed_roles = ["SUPER_ADMIN", "ADMIN_SUCURSAL"]

    def get(self, request):
        sucursal = self.get_sucursal()
        configuracion, _ = ConfiguracionImpresionVenta.objects.get_or_create(
            sucursal=sucursal,
        )
        if not configuracion.impresion_automatica:
            raise PermissionDenied("Active la impresión automática para usar la prueba directa.")
        return JsonResponse(
            ImpresionTermicaService.payload_prueba_qz(sucursal, configuracion)
        )
