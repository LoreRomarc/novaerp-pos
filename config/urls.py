# config/urls.py
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path
from django.shortcuts import redirect


def inicio(request):
    """
    Punto de entrada principal del sistema.

    - Usuario no autenticado -> login.
    - Usuario autenticado -> dashboard de caja.
    """
    if not request.user.is_authenticated:
        return redirect("login")

    return redirect("sales:caja_dashboard")


urlpatterns = [
    path("admin/", admin.site.urls),

    # ==========================================
    # AUTENTICACIÓN
    # ==========================================

    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="login.html"
        ),
        name="login",
    ),

    path(
        "accounts/logout/",
        auth_views.LogoutView.as_view(),
        name="logout",
    ),

    # ==========================================
    # INICIO
    # ==========================================

    path(
        "",
        inicio,
        name="inicio",
    ),

    # ==========================================
    # SALES / POS / CAJA
    # ==========================================

    path(
        "",
        include(
            "apps.sales.urls",
            namespace="sales",
        ),
    ),

    # ==========================================
    # INVENTARIO
    # ==========================================

    path(
        "inventory/",
        include("apps.inventory.urls"),
    ),

    # ==========================================
    # ADMINISTRACIÓN
    # ==========================================

    path(
        "admin-panel/",
        include("apps.administration.urls"),
    ),

    # ==========================================
    # CONFIGURACIÓN
    # ==========================================

    path(
        "setup/",
        include("apps.setup.urls"),
    ),
]