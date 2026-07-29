# apps/administration/urls.py
from django.urls import path

from apps.administration.api.user_search_api import UserSearchAPI
from apps.administration.views.dashboard import AdminDashboardView
from apps.administration.views.empresa_views import EmpresaListView
from apps.administration.views.sucursal_views import (
    SucursalListView,
    SucursalCreateView
)

from apps.administration.views.user_views import (
    UserDeleteView,
    UserListView,
    UserCreateView,
    UserUpdateView,
)

from apps.administration.views.customer_views import (
    ClienteListView,
    ClienteCreateView
)

from apps.administration.views.catalog_views import (
    ColorListView,
    TipoTelaListView,
    TallaListView,
    TallaCreateView,
    ColorCreateView,
    TipoTelaCreateView,
)

from apps.administration.views.precio_views import (
    ListaPrecioListView,
    ListaPrecioCreateView,
    PrecioVarianteListView,
    PrecioVarianteCreateView,
)

app_name = "administration"

urlpatterns = [

    path("", AdminDashboardView.as_view(), name="dashboard"),
    path("api/users/search/", UserSearchAPI.as_view(), name="user_search_api"),

    path("empresas/", EmpresaListView.as_view(), name="empresa_list"),

    # ======================
    # SUCURSALES
    # ======================
    path("sucursales/", SucursalListView.as_view(), name="sucursal_list"),
    path("sucursales/create/", SucursalCreateView.as_view(), name="sucursal_create"),

    # ======================
    # USUARIOS
    # ======================
    path("usuarios/", UserListView.as_view(), name="user_list"),
    path("usuarios/create/", UserCreateView.as_view(), name="user_create"),
    path("usuarios/<int:pk>/edit/", UserUpdateView.as_view(), name="user_update"),
    path("usuarios/<int:pk>/delete/", UserDeleteView.as_view(), name="user_delete"),

    # ======================
    # CLIENTES
    # ======================
    path("clientes/", ClienteListView.as_view(), name="cliente_list"),
    path("clientes/create/", ClienteCreateView.as_view(), name="cliente_create"),

    # ======================
    # CATALOGOS
    # ======================
    path("colores/", ColorListView.as_view(), name="color_list"),
    path("colores/create/", ColorCreateView.as_view(), name="color_create"),

    path("tipos-tela/", TipoTelaListView.as_view(), name="tipo_tela_list"),
    path("tipos-tela/create/", TipoTelaCreateView.as_view(), name="tipo_tela_create"),

    path("tallas/", TallaListView.as_view(), name="talla_list"),
    path("tallas/create/", TallaCreateView.as_view(), name="talla_create"),

    # =====================
    # LISTAS DE PRECIOS
    # =====================

    path(
        "listas-precios/",
        ListaPrecioListView.as_view(),
        name="lista_precio_list"
    ),

    path(
        "listas-precios/create/",
        ListaPrecioCreateView.as_view(),
        name="lista_precio_create"
    ),

    path(
        "precios-variantes/",
        PrecioVarianteListView.as_view(),
        name="precio_variante_list"
    ),

    path(
        "precios-variantes/create/",
        PrecioVarianteCreateView.as_view(),
        name="precio_variante_create"
    ),


]