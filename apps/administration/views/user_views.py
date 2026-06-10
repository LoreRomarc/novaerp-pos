# apps/administration/views/user_views.py
from django.contrib.auth.models import User
from django.views.generic import DeleteView, ListView, CreateView, UpdateView
from django.urls import reverse_lazy

from apps.administration.forms import UserCompleteForm


class UserListView(ListView):
    model = User
    template_name = "administration/users/list.html"
    context_object_name = "users"


class UserCreateView(CreateView):
    model = User
    form_class = UserCompleteForm
    template_name = "administration/users/form.html"
    success_url = reverse_lazy("administration:user_list")

class UserUpdateView(UpdateView):
    model = User
    form_class = UserCompleteForm
    template_name = "administration/users/form.html"
    success_url = reverse_lazy("administration:user_list")


class UserDeleteView(DeleteView):
    model = User
    template_name = "administration/users/confirm_delete.html"
    success_url = reverse_lazy("administration:user_list")