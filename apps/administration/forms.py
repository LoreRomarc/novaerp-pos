# apps/administration/forms.py
from decimal import Decimal

from django import forms
from django.contrib.auth.models import User

from apps.accounts.models import UserProfile
from apps.core.models import Empresa, Sucursal
from apps.customers.models import Cliente
from apps.inventory.models import Color, ProductoVariante, Talla, TipoTela
from apps.sales.models import ListaPrecio, PrecioVariante, Venta


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance or not self.instance.pk:
            return

        # Al editar, la contraseña es opcional. Si se deja vacía,
        # se conserva la existente.
        self.fields["password"].required = False
        self.fields["password"].help_text = (
            "Déjela vacía para conservar la contraseña actual."
        )

        profile = getattr(self.instance, "profile", None)
        if profile:
            self.initial["role"] = profile.role
            self.initial["sucursal"] = profile.sucursal_id

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
        password = self.cleaned_data.get("password")

        if password:
            user.set_password(password)

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
        fields = [
            "empresa",
            "nombre",
            "direccion",
            "lista_precio_default",
            "activa",
        ]
        widgets = {
            "empresa": forms.Select(attrs={"class": "form-select"}),
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "direccion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "lista_precio_default": forms.Select(
                attrs={"class": "form-select"}
            ),
            "activa": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


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
        fields = ["nombre", "identificacion", "tipo_cliente", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "identificacion": forms.TextInput(
                attrs={"class": "form-control"}
            ),
            "tipo_cliente": forms.Select(attrs={"class": "form-select"}),
            "activo": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class ColorForm(forms.ModelForm):
    class Meta:
        model = Color
        fields = ["nombre", "codigo_hex"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "codigo_hex": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "#000000"}
            ),
        }


class TipoTelaForm(forms.ModelForm):
    class Meta:
        model = TipoTela
        fields = ["nombre", "descripcion", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "descripcion": forms.Textarea(
                attrs={"class": "form-control", "rows": 3}
            ),
            "activo": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class TallaForm(forms.ModelForm):
    class Meta:
        model = Talla
        fields = ["nombre", "orden", "activo"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "orden": forms.NumberInput(attrs={"class": "form-control"}),
            "activo": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
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
            "precio": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "step": "0.01"}
            ),
        }

class EmpresaForm(forms.ModelForm):
    class Meta:
        model = Empresa
        fields = [
            "nombre",
            "razon_social",
            "nit",
            "direccion",
            "ciudad",
            "telefono",
            "email",
            "sitio_web",
            "logo",
            "activa",
        ]

        widgets = {
            "nombre": forms.TextInput(attrs={"class": "form-control"}),
            "razon_social": forms.TextInput(attrs={"class": "form-control"}),
            "nit": forms.TextInput(attrs={"class": "form-control"}),
            "direccion": forms.TextInput(attrs={"class": "form-control"}),
            "ciudad": forms.TextInput(attrs={"class": "form-control"}),
            "telefono": forms.TextInput(attrs={"class": "form-control"}),
            "email": forms.EmailInput(attrs={"class": "form-control"}),
            "sitio_web": forms.URLInput(attrs={"class": "form-control"}),
            "logo": forms.ClearableFileInput(
                attrs={"class": "form-control"}
            ),
            "activa": forms.CheckboxInput(
                attrs={"class": "form-check-input"}
            ),
        }


class ListaPrecioMasivaForm(forms.Form):
    nombre = forms.CharField(
        label="Nombre de la lista",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Ejemplo: Precio Mayorista",
            }
        ),
    )
    tipo_venta = forms.ChoiceField(
        label="Tipo de venta",
        choices=Venta.TIPO_VENTA,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sucursales = forms.ModelMultipleChoiceField(
        label="Sucursales",
        queryset=Sucursal.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )
    activa = forms.BooleanField(
        label="Lista activa",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["sucursales"].queryset = Sucursal.objects.filter(
            activa=True
        ).order_by("nombre")


class PrecioMasivoForm(forms.Form):
    variante = forms.ModelChoiceField(
        label="Producto / variante",
        queryset=ProductoVariante.objects.none(),
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sucursales = forms.ModelMultipleChoiceField(
        label="Aplicar en sucursales",
        queryset=Sucursal.objects.none(),
        widget=forms.CheckboxSelectMultiple,
    )
    precio_mayorista = forms.DecimalField(
        label="Precio mayorista",
        required=False,
        min_value=Decimal("0.01"),
        decimal_places=2,
        max_digits=14,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
                "placeholder": "0",
            }
        ),
    )
    precio_detal = forms.DecimalField(
        label="Precio detal",
        required=False,
        min_value=Decimal("0.01"),
        decimal_places=2,
        max_digits=14,
        widget=forms.NumberInput(
            attrs={
                "class": "form-control",
                "min": "0",
                "step": "0.01",
                "placeholder": "Opcional",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["variante"].queryset = (
            ProductoVariante.objects.select_related(
                "producto_base", "tipo_tela", "color", "talla"
            ).order_by("producto_base__nombre", "sku")
        )
        self.fields["sucursales"].queryset = Sucursal.objects.filter(
            activa=True
        ).order_by("nombre")

    def clean(self):
        cleaned_data = super().clean()

        if not (
            cleaned_data.get("precio_mayorista")
            or cleaned_data.get("precio_detal")
        ):
            raise forms.ValidationError(
                "Indique al menos un precio: mayorista o detal."
            )

        return cleaned_data
