# config/urls.py
from django.contrib import admin
from django.urls import include, path
from django.contrib.auth import views as auth_views


urlpatterns = [
    path('admin/', admin.site.urls),
    path("sales/", include("apps.sales.urls", namespace="sales")),

    
    path('accounts/login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(), name='logout'),

    path("inventory/", include("apps.inventory.urls")),

    path('admin-panel/', include('apps.administration.urls')),

    path("setup/", include("apps.setup.urls")),

]
