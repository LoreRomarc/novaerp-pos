# apps/administration/views/precio_views.py

from django.core.exceptions import ValidationError
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, View

from apps.inventory.models import ProductoVariante
from apps.sales.models import (
    ListaPrecio,
    PrecioVariante
)

from apps.administration.forms import (
    ListaPrecioMasivaForm,
    PrecioMasivoForm,
)
from apps.administration.mixins import SuperAdminRequiredMixin
from apps.administration.services.precios_service import PrecioMasivoService


class ListaPrecioListView(SuperAdminRequiredMixin, ListView):
    model = ListaPrecio
    template_name = "administration/precios/listas.html"
    context_object_name = "listas"
    paginate_by = 100

    def get_queryset(self):
        return ListaPrecio.objects.select_related("sucursal").order_by(
            "tipo_venta", "nombre", "sucursal__nombre"
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        grupos = {}

        for lista in context["listas"]:
            clave = (lista.tipo_venta, lista.nombre)
            grupo = grupos.setdefault(clave, {
                "lista": lista,
                "sucursales": [],
                "activas": 0,
                "total": 0,
            })
            grupo["sucursales"].append(lista.sucursal.nombre)
            grupo["total"] += 1
            grupo["activas"] += int(lista.activa)

        context["grupos"] = list(grupos.values())
        return context


class ListaPrecioCreateView(SuperAdminRequiredMixin, View):
    template_name = "administration/precios/lista_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ListaPrecioMasivaForm()})

    def post(self, request):
        form = ListaPrecioMasivaForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)

        try:
            PrecioMasivoService.crear_listas(
                nombre=form.cleaned_data["nombre"],
                tipo_venta=form.cleaned_data["tipo_venta"],
                sucursales=form.cleaned_data["sucursales"],
                activa=form.cleaned_data["activa"],
            )
        except ValidationError as error:
            form.add_error(None, error)
            return render(request, self.template_name, {"form": form}, status=400)

        return redirect("administration:lista_precio_list")


class ListaPrecioUpdateView(SuperAdminRequiredMixin, View):
    template_name = "administration/precios/lista_form.html"

    def _obtener_lista(self, pk):
        return get_object_or_404(
            ListaPrecio.objects.select_related("sucursal"), pk=pk
        )

    def get(self, request, pk):
        lista = self._obtener_lista(pk)
        sucursales = ListaPrecio.objects.filter(
            tipo_venta=lista.tipo_venta,
            nombre=lista.nombre,
            activa=True,
        ).values_list("sucursal_id", flat=True)
        form = ListaPrecioMasivaForm(initial={
            "nombre": lista.nombre,
            "tipo_venta": lista.tipo_venta,
            "sucursales": list(sucursales),
            "activa": lista.activa,
        })
        return render(request, self.template_name, {
            "form": form, "lista": lista, "modo_edicion": True,
        })

    def post(self, request, pk):
        lista = self._obtener_lista(pk)
        form = ListaPrecioMasivaForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {
                "form": form, "lista": lista, "modo_edicion": True,
            }, status=400)

        try:
            PrecioMasivoService.actualizar_listas(
                nombre=form.cleaned_data["nombre"],
                tipo_venta=lista.tipo_venta,
                sucursales=form.cleaned_data["sucursales"],
                activa=form.cleaned_data["activa"],
            )
        except ValidationError as error:
            form.add_error(None, error)
            return render(request, self.template_name, {
                "form": form, "lista": lista, "modo_edicion": True,
            }, status=400)

        return redirect("administration:lista_precio_list")


class PrecioVarianteListView(SuperAdminRequiredMixin, ListView):
    model = ProductoVariante
    template_name = "administration/precios/precios.html"
    context_object_name = "variantes"
    paginate_by = 100

    def get_queryset(self):
        precios = PrecioVariante.objects.select_related(
            "lista",
            "lista__sucursal",
        ).order_by("lista__tipo_venta", "lista__sucursal__nombre")

        return (
            ProductoVariante.objects
            .filter(precios__isnull=False)
            .select_related("producto_base", "tipo_tela", "color", "talla")
            .prefetch_related(
                Prefetch("precios", queryset=precios, to_attr="precios_admin")
            )
            .distinct()
            .order_by("producto_base__nombre", "sku")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        resumenes = []

        for variante in context["variantes"]:
            por_tipo_y_precio = {}

            for precio in variante.precios_admin:
                clave = (precio.lista.tipo_venta, precio.precio)
                por_tipo_y_precio.setdefault(clave, []).append(
                    precio.lista.sucursal.nombre
                )

            resumen = {
                "variante": variante,
                "MAYORISTA": [],
                "DETAL": [],
            }

            for (tipo, valor), sucursales in por_tipo_y_precio.items():
                resumen[tipo].append(
                    {
                        "precio": valor,
                        "sucursales": sucursales,
                    }
                )

            resumenes.append(resumen)

        context["resumenes"] = resumenes
        return context


class PrecioVarianteCreateView(SuperAdminRequiredMixin, View):
    template_name = "administration/precios/precio_form.html"

    def get(self, request):
        return render(request, self.template_name, {"form": PrecioMasivoForm()})

    def post(self, request):
        form = PrecioMasivoForm(request.POST)

        if not form.is_valid():
            return render(request, self.template_name, {"form": form}, status=400)

        try:
            PrecioMasivoService.asignar_precios(
                variante=form.cleaned_data["variante"],
                sucursales=form.cleaned_data["sucursales"],
                precios_por_tipo={
                    "MAYORISTA": form.cleaned_data["precio_mayorista"],
                    "DETAL": form.cleaned_data["precio_detal"],
                },
            )
        except ValidationError as error:
            form.add_error(None, error)
            return render(request, self.template_name, {"form": form}, status=400)

        return redirect("administration:precio_variante_list")


class PrecioVarianteUpdateView(SuperAdminRequiredMixin, View):
    template_name = "administration/precios/precio_form.html"

    def _obtener_variante(self, pk):
        return get_object_or_404(
            ProductoVariante.objects.select_related(
                "producto_base", "color", "tipo_tela", "talla"
            ), pk=pk
        )

    def _iniciales(self, variante):
        precios = list(
            PrecioVariante.objects.filter(variante=variante).select_related(
                "lista", "lista__sucursal"
            )
        )
        iniciales = {
            "variante": variante,
            "sucursales": sorted({precio.lista.sucursal_id for precio in precios}),
        }

        for tipo, campo in (("MAYORISTA", "precio_mayorista"), ("DETAL", "precio_detal")):
            valores = {
                precio.precio for precio in precios
                if precio.lista.tipo_venta == tipo
            }
            if len(valores) == 1:
                iniciales[campo] = valores.pop()

        return iniciales

    def _contexto(self, form, variante):
        return {
            "form": form,
            "variante_actual": variante,
            "modo_edicion": True,
        }

    def get(self, request, pk):
        variante = self._obtener_variante(pk)
        form = PrecioMasivoForm(initial=self._iniciales(variante))
        return render(request, self.template_name, self._contexto(form, variante))

    def post(self, request, pk):
        variante = self._obtener_variante(pk)
        datos = request.POST.copy()
        datos["variante"] = str(variante.pk)
        form = PrecioMasivoForm(datos)

        if not form.is_valid():
            return render(request, self.template_name, self._contexto(form, variante), status=400)

        try:
            PrecioMasivoService.asignar_precios(
                variante=variante,
                sucursales=form.cleaned_data["sucursales"],
                precios_por_tipo={
                    "MAYORISTA": form.cleaned_data["precio_mayorista"],
                    "DETAL": form.cleaned_data["precio_detal"],
                },
            )
        except ValidationError as error:
            form.add_error(None, error)
            return render(request, self.template_name, self._contexto(form, variante), status=400)

        return redirect("administration:precio_variante_list")


class PrecioVarianteBusquedaView(SuperAdminRequiredMixin, View):
    def get(self, request):
        query = request.GET.get("q", "").strip()

        if len(query) < 2:
            return JsonResponse({"results": []})

        variantes = (
            ProductoVariante.objects.select_related(
                "producto_base", "color", "tipo_tela", "talla"
            )
            .filter(
                Q(sku__icontains=query)
                | Q(producto_base__nombre__icontains=query)
                | Q(color__nombre__icontains=query)
                | Q(tipo_tela__nombre__icontains=query)
                | Q(talla__nombre__icontains=query)
            )
            .order_by("producto_base__nombre", "sku")[:20]
        )

        return JsonResponse(
            {
                "results": [
                    {
                        "id": variante.id,
                        "text": (
                            f"{variante.producto_base.nombre} · "
                            f"{variante.color.nombre} · "
                            f"{variante.talla.nombre} · "
                            f"{variante.tipo_tela.nombre}"
                        ),
                        "sku": variante.sku,
                    }
                    for variante in variantes
                ]
            }
        )
