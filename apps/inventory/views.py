# apps/inventory/views.py
from django.db.models import Sum
from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import View
from django.views.generic import ListView, FormView
from django.shortcuts import redirect
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib import messages

from django.db.models import ExpressionWrapper, Sum, Q, F, DecimalField

from apps.core.models import Sucursal
from apps.inventory.mixins import InventoryAccessMixin, SucursalScopedMixin
from apps.inventory.models import (
    Stock,
    Traslado,
    TrasladoDetalle,
    ProductoVariante
)
from apps.inventory.models_produccion import ProduccionLote, RolloTela
from apps.inventory.services.stock_service import InventoryService
from apps.inventory.services.traslado_service import TrasladoService


# ======================================================
# PRODUCCION
# ======================================================

class ProduccionListView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    ListView
):
    model = ProduccionLote
    template_name = "inventory/produccion.html"
    context_object_name = "lotes"
    paginate_by = 50

    def get_queryset(self):

        return (
            ProduccionLote.objects
            .select_related(
                "sucursal",
                "operario",
            )
            .prefetch_related(
                "rollos",
                "rollos__rollo",
                "rollos__rollo__tipo_tela",
                "rollos__rollo__color",

                "detalles",
                "detalles__variante",
                "detalles__variante__producto_base",
                "detalles__variante__tipo_tela",
                "detalles__variante__color",
                "detalles__variante__talla",
            )
            .order_by("-creado")
        )

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        qs = self.get_queryset()

        context["total_lotes"] = qs.count()

        context["total_prendas"] = (
            qs.aggregate(
                total=Sum("total_prendas")
            )["total"] or 0
        )

        context["consumo_total"] = (
            qs.aggregate(
                total=Sum("consumo_total")
            )["total"] or 0
        )

        context["rollos"] = (
            RolloTela.objects
            .filter(
                estado="DISPONIBLE"
            )
            .select_related(
                "tipo_tela",
                "color"
            )
            .order_by("-creado")[:10]
        )

        context["stock_producido"] = (
            Stock.objects
            .select_related(
                "variante",
                "variante__producto_base",
                "variante__color",
                "variante__tipo_tela",
                "variante__talla",
            )
            .order_by("-cantidad")[:10]
        )

        return context


# ======================================================
# STOCK
# ======================================================

class StockListView(LoginRequiredMixin, InventoryAccessMixin, SucursalScopedMixin, ListView):

    model = Stock
    template_name = "inventory/stock_list.html"
    context_object_name = "stocks"

    def get_queryset(self):
        qs = Stock.objects.select_related(
            "variante",
            "variante__producto_base",
            "variante__color",
            "variante__tipo_tela",
            "sucursal"
        )

        if self.request.user.profile.role != "SUPER_ADMIN":
            qs = self.filter_by_sucursal(qs)

        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                Q(variante__producto_base__nombre__icontains=q) |
                Q(variante__talla__icontains=q)
            )

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        qs = self.get_queryset()

        context["total_unidades"] = qs.aggregate(
            total=Sum("cantidad")
        )["total"] or 0

        context["total_productos"] = qs.count()

        context["stock_bajo"] = qs.filter(cantidad__lt=5).count()

        context["valor_total"] = qs.aggregate(
            total=Sum(
                ExpressionWrapper(
                    F("cantidad") * F("costo_promedio"),
                    output_field=DecimalField()
                )
            )
        )["total"] or 0

        return context

class AjusteStockView(View):

    def post(self, request):

        try:
            variante_id = request.POST.get("variante_id")
            cantidad = float(request.POST.get("cantidad", 0))

            if not variante_id:
                raise Exception("Debes seleccionar un producto válido")

            variante = ProductoVariante.objects.get(id=variante_id)

            if cantidad > 0:
                InventoryService.agregar_stock(
                    variante=variante,
                    cantidad=cantidad,
                    user=request.user,
                    tipo="AJUSTE"
                )
            else:
                InventoryService.descontar_stock(
                    variante=variante,
                    cantidad=abs(cantidad),
                    user=request.user,
                    tipo="AJUSTE"
                )

            messages.success(request, f"Ajuste aplicado a {variante}")

        except Exception as e:
            messages.error(request, str(e))

        return redirect("inventory:dashboard")
     
class AjusteStockForm(forms.Form):

    variante = forms.ModelChoiceField(
        queryset=ProductoVariante.objects.select_related(
            "producto_base",
            "color"
        )
    )

    cantidad = forms.DecimalField(
        min_value=0.01
    )

    tipo = forms.ChoiceField(
        choices=[
            ("AJUSTE_ENTRADA", "➕ Entrada"),
            ("AJUSTE_SALIDA", "➖ Salida"),
        ]
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["variante"].label_from_instance = (
            lambda obj: f"{obj.producto_base.nombre} - {obj.color} - {obj.talla}"
        )

class AjusteStockCreateView( LoginRequiredMixin,InventoryAccessMixin,FormView):

    template_name = "inventory/ajuste_stock.html"

    form_class = AjusteStockForm

    def form_valid(self, form):

        try:

            variante = form.cleaned_data["variante"]
            cantidad = form.cleaned_data["cantidad"]
            tipo = form.cleaned_data["tipo"]

            if tipo == "AJUSTE_ENTRADA":

                InventoryService.agregar_stock(
                    variante=variante,
                    cantidad=cantidad,
                    user=self.request.user,
                    tipo="AJUSTE_ENTRADA"
                )

            else:

                InventoryService.descontar_stock(
                    variante=variante,
                    cantidad=cantidad,
                    user=self.request.user,
                    tipo="AJUSTE_SALIDA"
                )

            messages.success(
                self.request,
                "Stock actualizado correctamente."
            )

        except Exception as e:

            messages.error(
                self.request,
                str(e)
            )

            return redirect(
                "inventory:ajuste_stock_form"
            )

        return redirect(
            "inventory:stock_list"
        )
    
# ======================================================
# TRASLADOS ENTRE SUCURSALES (ENTRADAS/SALIDAS)
# ======================================================

class TrasladoForm(forms.Form):

    tipo = forms.ChoiceField(
        choices=Traslado.TIPOS
    )

    origen = forms.ModelChoiceField(
        queryset=Sucursal.objects.all(),
        required=False
    )

    destino = forms.ModelChoiceField(
        queryset=Sucursal.objects.all(),
        required=False
    )

    variante = forms.ModelChoiceField(
        queryset=ProductoVariante.objects.select_related(
            "producto_base",
            "color"
        )
    )

    cantidad = forms.DecimalField(
        min_value=1
    )

    motivo = forms.CharField(
        required=False
    )

    observaciones = forms.CharField(
        widget=forms.Textarea,
        required=False
    )

    # ==================================================
    # VALIDACIONES DINÁMICAS
    # ==================================================

    def clean(self):

        cleaned = super().clean()

        tipo = cleaned.get("tipo")

        origen = cleaned.get("origen")

        destino = cleaned.get("destino")

        # ==============================================
        # TRASLADO COMPLETO
        # ==============================================

        if tipo == "COMPLETO":

            if not origen:
                raise ValidationError(
                    "Sucursal origen requerida."
                )

            if not destino:
                raise ValidationError(
                    "Sucursal destino requerida."
                )

            if origen == destino:
                raise ValidationError(
                    "Origen y destino no pueden ser iguales."
                )

        # ==============================================
        # SOLO SALIDA
        # ==============================================

        elif tipo in [
            "SALIDA",
        ]:

            if not origen:
                raise ValidationError(
                    "Sucursal origen requerida."
                )

            if not destino:
                raise ValidationError(
                    "Sucursal destino requerida."
                )

        # ==============================================
        # SOLO ENTRADA
        # ==============================================

        elif tipo in [
            "ENTRADA",
            "AJUSTE_ENTRADA",
            "DEVOLUCION_CLIENTE",
            "INICIAL",
        ]:

            if not destino:
                raise ValidationError(
                    "Sucursal destino requerida."
                )

        # ==============================================
        # SALIDAS INVENTARIO
        # ==============================================

        elif tipo in [
            "AJUSTE_SALIDA",
            "DANADO",
            "MERMA",
            "CONSUMO_INTERNO",
            "DEVOLUCION_PROVEEDOR",
        ]:

            if not origen:
                raise ValidationError(
                    "Sucursal origen requerida."
                )

        return cleaned


class TrasladoCreateView( LoginRequiredMixin,InventoryAccessMixin,FormView):

    template_name = "inventory/traslado.html"

    form_class = TrasladoForm

    permission_required = "inventory.add_traslado"

    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return self.handle_no_permission()

        profile = getattr(request.user, "profile", None)

        if not profile:
            raise PermissionDenied("Usuario sin perfil ERP")

        if profile.role not in [
            "SUPER_ADMIN",
            "ADMIN_SUCURSAL"
        ]:
            raise PermissionDenied(
                "No tienes permisos"
            )

        return super().dispatch(
            request,
            *args,
            **kwargs
        )

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["tipos"] = Traslado.TIPOS

        return context

    def form_valid(self, form):

        try:

            with transaction.atomic():

                traslado = Traslado.objects.create(

                    tipo=form.cleaned_data["tipo"],

                    origen=form.cleaned_data.get("origen"),

                    destino=form.cleaned_data.get("destino"),

                    motivo=form.cleaned_data.get("motivo"),

                    observaciones=form.cleaned_data.get(
                        "observaciones"
                    ),
                )

                TrasladoDetalle.objects.create(

                    traslado=traslado,

                    variante=form.cleaned_data["variante"],

                    cantidad=form.cleaned_data["cantidad"],
                )

                TrasladoService.enviar_traslado(
                    traslado.id,
                    usuario=self.request.user
                )

                messages.success(
                    self.request,
                    "Movimiento procesado correctamente."
                )

        except Exception as e:

            messages.error(
                self.request,
                str(e)
            )

            return redirect(
                "inventory:traslado_create"
            )

        return redirect(
            "inventory:traslado_list"
        )


class TrasladoListView( LoginRequiredMixin, InventoryAccessMixin, ListView):

    model = Traslado

    template_name = "inventory/traslado_list.html"

    context_object_name = "traslados"

    paginate_by = 50

    def get_queryset(self):

        qs = (
            Traslado.objects
            .select_related(
                "origen",
                "destino",
                "enviado_por",
                "recibido_por"
            )
            .order_by("-id")
        )

        q = self.request.GET.get("q")

        estado = self.request.GET.get("estado")

        tipo = self.request.GET.get("tipo")

        if q:

            qs = qs.filter(
                Q(numero__icontains=q) |
                Q(observaciones__icontains=q) |
                Q(motivo__icontains=q)
            )

        if estado:
            qs = qs.filter(estado=estado)

        if tipo:
            qs = qs.filter(tipo=tipo)

        return qs

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["tipos"] = Traslado.TIPOS

        context["estados"] = Traslado.ESTADOS

        return context

