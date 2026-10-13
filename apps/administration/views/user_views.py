# apps/administration/views/user_views.py
from django.contrib.auth.models import User
from django.db.models.deletion import ProtectedError
from django.shortcuts import redirect, render
from django.views.generic import DeleteView, ListView, CreateView, UpdateView
from django.urls import reverse_lazy

from apps.administration.forms import UserCompleteForm
from apps.administration.mixins import SuperAdminRequiredMixin


class UserListView(SuperAdminRequiredMixin, ListView):
    model = User
    template_name = "administration/users/list.html"
    context_object_name = "users"


class UserCreateView(SuperAdminRequiredMixin, CreateView):
    model = User
    form_class = UserCompleteForm
    template_name = "administration/users/form.html"
    success_url = reverse_lazy("administration:user_list")

class UserUpdateView(SuperAdminRequiredMixin, UpdateView):
    model = User
    form_class = UserCompleteForm
    template_name = "administration/users/form.html"
    success_url = reverse_lazy("administration:user_list")


class UserDeleteView(SuperAdminRequiredMixin, DeleteView):
    model = User
    template_name = "administration/users/confirm_delete.html"
    success_url = reverse_lazy("administration:user_list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.pk == request.user.pk:
            return render(
                request,
                self.template_name,
                {"object": self.object, "error": "No puede eliminar el usuario con el que tiene la sesión iniciada."},
                status=400,
            )
        if self.object.is_superuser:
            return render(
                request,
                self.template_name,
                {"object": self.object, "error": "No elimine un superusuario desde el ERP. Desactívelo o cree primero otro administrador."},
                status=400,
            )
        try:
            self.object.delete()
        except ProtectedError:
            return render(
                request,
                self.template_name,
                {
                    "object": self.object,
                    "error": (
                        "Este usuario tiene ventas, movimientos o auditorías asociadas. "
                        "Por seguridad no se borra el historial; desactive el acceso en su lugar."
                    ),
                },
                status=409,
            )
        return redirect(self.success_url)
