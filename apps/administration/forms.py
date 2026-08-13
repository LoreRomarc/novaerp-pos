# apps/administration/forms.py
from django import forms
from django.contrib.auth.models import User

from apps.accounts.models import UserProfile
from apps.core.models import Sucursal
from apps.customers.models import Cliente
from apps.inventory.models import Color, Talla, TipoTela
from apps.sales.models import ListaPrecio, PrecioVariante


class UserCompleteForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "new-password",
            }
        )
    )
    role = forms.ChoiceField(
        choices=UserProfile.Role.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sucursal = forms.ModelChoiceField(
        queryset=Sucursal.objects.all().order_by("nombre"),
        required=False,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = User
        fields = ["username", "email", "password"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        sucursal = cleaned_data.get("sucursal")

        roles_con_sucursal = {
            UserProfile.Role.ADMIN_SUCURSAL,
            UserProfile.Role.SUPERVISOR,
            UserProfile.Role.CAJERO,
            UserProfile.Role.INVENTARIO,
        }

        if role in roles_con_sucursal and not sucursal:
            self.add_error(
                "sucursal",
                "Debe asignar una sucursal para este rol.",
            )

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password"])

        if not commit:
            return user

        user.save()

        profile, _ = UserProfile.objects.get_or_create(user=user)
        profile.role = self.cleaned_data["role"]
        profile.sucursal = self.cleaned_data["sucursal"]
        profile.save(update_fields=["role", "sucursal"])

        return user


class SucursalForm(forms.ModelForm):
    class Meta:
        model = Sucursal
        fields = "__all__"


class UserForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "new-password",
            }
        )
    )

    class Meta:
        model = User
        fields = ["username", "email", "password"]
        widgets = {
            "username": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
        }


class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = "__all__"


class ColorForm(forms.ModelForm):
    class Meta:
        model = Color
        fields = "__all__"
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "codigo_hex": forms.TextInput(attrs={"class": "form-control"}),
        }


class TipoTelaForm(forms.ModelForm):
    class Meta:
        model = TipoTela
        fields = "__all__"
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(attrs={"class": "form-control"}),
        }


class TallaForm(forms.ModelForm):
    class Meta:
        model = Talla
        fields = "__all__"
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "orden": forms.NumberInput(attrs={"class": "form-control"}),
        }


class ListaPrecioForm(forms.ModelForm):
    class Meta:
        model = ListaPrecio
        fields = "__all__"
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "tipo_venta": forms.Select(attrs={"class": "form-select"}),
            "sucursal": forms.Select(attrs={"class": "form-select"}),
            "activa": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class PrecioVarianteForm(forms.ModelForm):
    class Meta:
        model = PrecioVariante
        fields = "__all__"
        widgets = {
            "variante": forms.Select(attrs={"class": "form-select"}),
            "lista": forms.Select(attrs={"class": "form-select"}),
            "precio": forms.NumberInput(attrs={"class": "form-control"}),
        }