# apps/inventory/views.py
import logging
from decimal import Decimal

from django import forms
from django.db.models import Sum
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import ListView, FormView
from django.shortcuts import redirect
from django.http import JsonResponse
from django.db import transaction
from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib import messages
from apps.sales.mixins import SucursalIsolationMixin
from django.db.models import ExpressionWrapper, Sum, Q, F, DecimalField

from apps.accounts.models import UserProfile
from apps.core.models import Sucursal
from apps.inventory.mixins import InventoryAccessMixin, SucursalScopedMixin
from apps.inventory.movimientos import (
    TIPOS_MOVIMIENTO_FILTRO,
    codigos_para_tipo,
)
from apps.inventory.models import (
    Stock,
    Traslado,
    TrasladoDetalle,
    ProductoVariante
)
from apps.inventory.models_produccion import ProduccionLote, RolloTela
from apps.inventory.services.stock_service import InventoryService
from apps.inventory.services.traslado_service import TrasladoService


logger = logging.getLogger(__name__)


# ======================================================
# PRODUCCION
# ======================================================

class ProduccionListView( LoginRequiredMixin, InventoryAccessMixin, SucursalIsolationMixin, ListView):
    model = ProduccionLote
    template_name = "inventory/produccion.html"
    context_object_name = "lotes"
    paginate_by = 50

    def get_queryset(self):

        qs = (
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
                "detalles__rollo",
                "detalles__variante",
                "detalles__variante__producto_base",
                "detalles__variante__tipo_tela",
                "detalles__variante__color",
                "detalles__variante__talla",
            )
            .order_by("-creado")
        )

        qs = qs.filter(sucursal=self.get_sucursal())
        request = self.request


        q = request.GET.get("q")

        fecha_desde = request.GET.get("fecha_desde")

        fecha_hasta = request.GET.get("fecha_hasta")


        if q:

            qs = qs.filter(

                Q(referencia__icontains=q) |

                Q(rollos__rollo__codigo__icontains=q) |

                Q(detalles__variante__producto_base__nombre__icontains=q) |

                Q(detalles__variante__tipo_tela__nombre__icontains=q) |

                Q(detalles__variante__color__nombre__icontains=q) |

                Q(detalles__variante__talla__nombre__icontains=q)

            ).distinct()


        if fecha_desde:

            qs = qs.filter(
                creado__date__gte=fecha_desde
            )


        if fecha_hasta:

            qs = qs.filter(
                creado__date__lte=fecha_hasta
            )


        return qs

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

        for lote in context["lotes"]:

            lote.consumos_rollos = lote.rollos.all()


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
    paginate_by = 50

    def get_queryset(self):
        qs = Stock.objects.select_related(
            "variante",
            "variante__producto_base",
            "variante__color",
            "variante__tipo_tela",
            "sucursal"
        )

        perfil = self.request.user.profile
        sucursal_id = self.request.GET.get("sucursal", "")

        if perfil.role != UserProfile.Role.SUPER_ADMIN:
            qs = self.filter_by_sucursal(qs)
        elif sucursal_id:
            qs = qs.filter(sucursal_id=sucursal_id)

        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                Q(variante__producto_base__nombre__icontains=q) |
                Q(variante__sku__icontains=q) |
                Q(variante__color__nombre__icontains=q) |
                Q(variante__tipo_tela__nombre__icontains=q) |
                Q(variante__talla__nombre__icontains=q) |
                Q(sucursal__nombre__icontains=q)
            )

        return qs.order_by(
            "variante__producto_base__nombre",
            "variante__tipo_tela__nombre",
            "variante__color__nombre",
            "variante__talla__orden",
            "sucursal__nombre",
        )

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

        context["puede_filtrar_sucursales"] = (
            self.request.user.profile.role == UserProfile.Role.SUPER_ADMIN
        )
        context["sucursales"] = Sucursal.objects.filter(activa=True).order_by("nombre")
        context["sucursal_id"] = self.request.GET.get("sucursal", "")
        return context


class TrasladoRecibirView(
    LoginRequiredMixin, InventoryAccessMixin, SucursalScopedMixin, View
):
    """Confirma la recepción física desde la sucursal destino."""

    def post(self, request, pk):
        traslado = Traslado.objects.select_related("destino").filter(pk=pk).first()
        if not traslado:
            messages.error(request, "El traslado no existe.")
            return redirect("inventory:traslado_list")

        if traslado.destino_id != self.get_sucursal().id:
            raise PermissionDenied("Solo la sucursal destino puede confirmar la recepción.")

        try:
            TrasladoService.recibir_traslado(
                pk, request.user, sucursal=self.get_sucursal()
            )
        except ValidationError as error:
            messages.error(request, error.messages[0])
        else:
            messages.success(request, f"Recepción de {traslado.numero} confirmada y stock actualizado.")
        return redirect("inventory:traslado_list")

class AjusteStockView(LoginRequiredMixin, InventoryAccessMixin, SucursalScopedMixin, View):

    def post(self, request):
        try:
            variante_id = request.POST.get("variante_id")
            cantidad = Decimal(request.POST.get("cantidad", "0"))

            if not variante_id:
                raise ValidationError("Debes seleccionar un producto válido.")

            if cantidad == 0:
                raise ValidationError("La cantidad no puede ser cero.")

            variante = ProductoVariante.objects.get(id=variante_id)
            sucursal = self._obtener_sucursal_ajuste(request)

            # La cantidad positiva es entrada; la negativa es salida.
            tipo = (
                "AJUSTE_ENTRADA"
                if cantidad > 0
                else "AJUSTE_SALIDA"
            )

            InventoryService.ajustar_stock(
                variante=variante,
                cantidad=abs(cantidad),
                tipo=tipo,
                user=request.user,
                sucursal_id=sucursal.id,
                referencia="AJUSTE MANUAL",
            )

            messages.success(
                request,
                f"Ajuste aplicado a {variante} y registrado en kardex."
            )

        except ProductoVariante.DoesNotExist:
            messages.error(request, "La variante seleccionada no existe.")

        except ValidationError as error:
            messages.error(request, error.messages[0])

        return redirect("inventory:dashboard")

    def _obtener_sucursal_ajuste(self, request):
        perfil = request.user.profile
        if perfil.role != UserProfile.Role.SUPER_ADMIN:
            return self.get_sucursal()

        sucursal = Sucursal.objects.filter(
            pk=request.POST.get("sucursal"),
            activa=True,
        ).first()
        if not sucursal:
            raise ValidationError("Seleccione una sucursal activa para el ajuste.")
        return sucursal


class AjusteStockForm(forms.Form):
    sucursal = forms.ModelChoiceField(
        label="Sucursal",
        queryset=Sucursal.objects.none(),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    variante = forms.ModelChoiceField(
        label="Producto",
        queryset=ProductoVariante.objects.filter(activo=True),
        widget=forms.Select(attrs={"class": "form-select"})
    )

    cantidad = forms.DecimalField(
        label="Cantidad",
        min_value=Decimal("0.01"),
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={
            "class": "form-control",
            "min": "0.01",
            "step": "0.01",
        })
    )

    tipo = forms.ChoiceField(
        label="Movimiento",
        choices=[
            ("AJUSTE_ENTRADA", "Entrada de inventario"),
            ("AJUSTE_SALIDA", "Salida por conteo / corrección"),
            ("DANADO", "Baja por producto dañado"),
            ("MERMA", "Baja por merma o pérdida"),
            ("CONSUMO_INTERNO", "Salida por consumo interno"),
        ],
        widget=forms.Select(attrs={"class": "form-select"})
    )

    motivo = forms.CharField(
        label="Motivo",
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ej.: conteo físico, avería, vencimiento",
        }),
    )

    observacion = forms.CharField(
        label="Observación",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control", "rows": 3,
            "placeholder": "Detalle que quedará registrado en el Kardex",
        }),
    )

    def __init__(self, *args, usuario=None, **kwargs):
        super().__init__(*args, **kwargs)
        perfil = getattr(usuario, "profile", None)
        if perfil and perfil.role == UserProfile.Role.SUPER_ADMIN:
            self.fields["sucursal"].queryset = Sucursal.objects.filter(
                activa=True
            ).order_by("nombre")
            self.fields["sucursal"].required = True
            return

        sucursal = getattr(perfil, "sucursal", None)
        self.fields["sucursal"].queryset = Sucursal.objects.filter(pk=getattr(sucursal, "pk", None))
        self.fields["sucursal"].initial = sucursal
        self.fields["sucursal"].widget = forms.HiddenInput()

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get("tipo")
        if tipo in {"DANADO", "MERMA", "CONSUMO_INTERNO"} and not cleaned.get("motivo"):
            self.add_error("motivo", "Indique el motivo de esta salida.")
        return cleaned

class AjusteStockCreateView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    SucursalScopedMixin,
    FormView
):
    template_name = "inventory/ajuste_stock.html"
    form_class = AjusteStockForm
    success_url = reverse_lazy("inventory:stock_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["usuario"] = self.request.user
        return kwargs

    def form_valid(self, form):
        try:
            InventoryService.ajustar_stock(
                variante=form.cleaned_data["variante"],
                cantidad=form.cleaned_data["cantidad"],
                tipo=form.cleaned_data["tipo"],
                user=self.request.user,
                sucursal_id=form.cleaned_data["sucursal"].id,
                referencia=(form.cleaned_data.get("motivo") or "AJUSTE MANUAL"),
                observacion=form.cleaned_data.get("observacion"),
            )
        except ValidationError as error:
            form.add_error(None, error.messages[0])
            return self.form_invalid(form)

        messages.success(
            self.request,
            "Stock ajustado y movimiento registrado en kardex."
        )
        return super().form_valid(form)
    
# ======================================================
# TRASLADOS ENTRE SUCURSALES (ENTRADAS/SALIDAS)
# ======================================================

class TrasladoForm(forms.Form):

    tipo = forms.ChoiceField(
        choices=[
            *TIPOS_MOVIMIENTO_FILTRO,
        ],
        initial="COMPLETO",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    origen = forms.ModelChoiceField(
        queryset=Sucursal.objects.filter(activa=True),
        label="Sucursal de origen",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    destino = forms.ModelChoiceField(
        queryset=Sucursal.objects.filter(activa=True),
        label="Sucursal de destino",
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    variante = forms.ModelChoiceField(
        queryset=ProductoVariante.objects.select_related(
            "producto_base",
            "color"
        ),
        label="Prenda",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    cantidad = forms.DecimalField(
        label="Cantidad",
        min_value=1,
        decimal_places=2,
        max_digits=12,
        widget=forms.NumberInput(attrs={
            "class": "form-control", "min": "1", "step": "1",
        }),
    )

    motivo = forms.CharField(
        label="Motivo",
        max_length=120,
        required=True,
        widget=forms.TextInput(attrs={
            "class": "form-control",
            "placeholder": "Ej.: reposición para vitrina",
        }),
    )

    observaciones = forms.CharField(
        label="Observación",
        required=False,
        widget=forms.Textarea(attrs={
            "class": "form-control", "rows": 2,
            "placeholder": "Opcional: empaque, responsable o novedad física",
        }),
    )

    # ==================================================
    # VALIDACIONES DINÁMICAS
    # ==================================================

    def clean(self):

        cleaned = super().clean()

        tipo = cleaned.get("tipo")

        origen = cleaned.get("origen")

        destino = cleaned.get("destino")

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

        elif tipo in TrasladoService.TIPOS_DIRECTOS_SALIDA:
            if not origen:
                self.add_error("origen", "Seleccione la sucursal de la que sale el inventario.")

        elif tipo in TrasladoService.TIPOS_DIRECTOS_ENTRADA:
            if not destino:
                self.add_error("destino", "Seleccione la sucursal a la que ingresa el inventario.")

        return cleaned


class TrasladoCreateView(LoginRequiredMixin, InventoryAccessMixin, SucursalScopedMixin, FormView):

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

        context["tipos"] = TrasladoForm.base_fields["tipo"].choices

        return context

    def form_valid(self, form):

        try:

            with transaction.atomic():

                sucursal_activa = self.get_sucursal()
                tipo = form.cleaned_data["tipo"]
                origen = form.cleaned_data.get("origen")
                destino = form.cleaned_data.get("destino")

                if tipo in TrasladoService.TIPOS_DIRECTOS_SALIDA:
                    sucursales_involucradas = [origen]
                elif tipo in TrasladoService.TIPOS_DIRECTOS_ENTRADA:
                    sucursales_involucradas = [destino]
                else:
                    sucursales_involucradas = [origen, destino]

                if (
                    self.request.user.profile.role != UserProfile.Role.SUPER_ADMIN
                    and any(
                        sucursal and sucursal.id != sucursal_activa.id
                        for sucursal in sucursales_involucradas
                    )
                ):
                    raise ValidationError(
                        "Solo puede registrar movimientos en su sucursal asignada."
                    )

                traslado = Traslado.objects.create(

                    tipo=tipo,

                    origen=origen,

                    destino=destino,

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
                    "Movimiento registrado y enviado al Kardex."
                )

        except ValidationError as error:
            form.add_error(None, error.messages[0])
            return self.form_invalid(form)
        except Exception:
            logger.exception("Error al crear un traslado de inventario.")
            form.add_error(
                None,
                "No fue posible registrar el traslado. Intente nuevamente.",
            )
            return self.form_invalid(form)

        return redirect(
            "inventory:traslado_list"
        )


class TrasladoListView(LoginRequiredMixin, InventoryAccessMixin, SucursalScopedMixin, ListView):

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

        tipo_movimiento = self.request.GET.get("tipo_movimiento", "")
        sucursal_id = self.request.GET.get("sucursal", "")
        fecha_desde = self.request.GET.get("fecha_desde", "")
        fecha_hasta = self.request.GET.get("fecha_hasta", "")

        if self.request.user.profile.role != UserProfile.Role.SUPER_ADMIN:
            sucursal = self.get_sucursal()
            qs = qs.filter(Q(origen=sucursal) | Q(destino=sucursal))
        elif sucursal_id:
            qs = qs.filter(Q(origen_id=sucursal_id) | Q(destino_id=sucursal_id))

        if q:

            qs = qs.filter(
                Q(numero__icontains=q) |
                Q(observaciones__icontains=q) |
                Q(motivo__icontains=q)
            )

        if estado:
            qs = qs.filter(estado=estado)

        if tipo_movimiento:
            qs = qs.filter(tipo__in=codigos_para_tipo(tipo_movimiento))

        if fecha_desde:
            qs = qs.filter(creado__date__gte=fecha_desde)

        if fecha_hasta:
            qs = qs.filter(creado__date__lte=fecha_hasta)

        return qs

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["tipos_movimiento"] = TIPOS_MOVIMIENTO_FILTRO
        context["puede_filtrar_sucursales"] = (
            self.request.user.profile.role == UserProfile.Role.SUPER_ADMIN
        )
        context["sucursales"] = Sucursal.objects.filter(activa=True).order_by("nombre")
        context["sucursal_id"] = self.request.GET.get("sucursal", "")
        sucursal_activa = self.get_sucursal()
        context["sucursal_activa_traslado"] = sucursal_activa
        context["pendientes_recepcion"] = Traslado.objects.filter(
            destino=sucursal_activa,
            estado="ENVIADO",
            tipo__in=["COMPLETO", "SALIDA", "ENTRADA"],
        ).select_related("origen", "enviado_por").exclude(enviado_por=self.request.user)
        context["pendientes_confirmacion_destino"] = Traslado.objects.filter(
            origen=sucursal_activa,
            estado="ENVIADO",
            tipo__in=["COMPLETO", "SALIDA"],
        ).select_related("destino", "enviado_por")

        return context


class TrasladoDetalleView(
    LoginRequiredMixin,
    InventoryAccessMixin,
    SucursalScopedMixin,
    View,
):
    """Detalle de traslado con el mismo alcance de sucursal de la lista."""

    def get(self, request, pk):
        traslados = Traslado.objects.select_related(
            "origen", "destino", "enviado_por", "recibido_por"
        ).prefetch_related(
            "detalles__variante__producto_base",
            "detalles__variante__tipo_tela",
            "detalles__variante__color",
            "detalles__variante__talla",
        )

        if request.user.profile.role != UserProfile.Role.SUPER_ADMIN:
            sucursal = self.get_sucursal()
            traslados = traslados.filter(Q(origen=sucursal) | Q(destino=sucursal))

        traslado = traslados.filter(pk=pk).first()
        if not traslado:
            return JsonResponse(
                {"success": False, "error": "Movimiento no encontrado."},
                status=404,
            )

        return JsonResponse({
            "success": True,
            "traslado": {
                "numero": traslado.numero,
                "tipo": traslado.get_tipo_display(),
                "estado": traslado.get_estado_display(),
                "origen": traslado.origen.nombre if traslado.origen else "—",
                "destino": traslado.destino.nombre if traslado.destino else "—",
                "motivo": traslado.motivo or "Sin motivo registrado",
                "observaciones": traslado.observaciones or "Sin observaciones",
                "creado": traslado.creado.strftime("%d/%m/%Y %H:%M"),
                "enviado_por": str(traslado.enviado_por or "—"),
                "recibido_por": str(traslado.recibido_por or "—"),
                "items": [
                    {
                        "producto": str(detalle.variante),
                        "cantidad": str(detalle.cantidad),
                        "observacion": detalle.observacion or "",
                    }
                    for detalle in traslado.detalles.all()
                ],
            },
        })

