# apps/setup/forms.py
from django import forms

class SetupForm(forms.Form):

    # ============================================
    # EMPRESA
    # ============================================

    nombre_empresa = forms.CharField(

        label="Nombre de la empresa",

        max_length=200,

        widget=forms.TextInput(

            attrs={

                "class": "form-control",

                "placeholder": "Mi empresa"

            }

        )

    )


    # ============================================
    # SUCURSAL
    # ============================================

    nombre_sucursal = forms.CharField(
        label="Nombre de la sucursal",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Sucursal Principal"
            }
        )
    )

    direccion = forms.CharField(
        label="Dirección",
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3
            }
        )
    )

    # ============================================
    # CAJA
    # ============================================

    codigo_caja = forms.CharField(
        label="Código de la caja",
        initial="CAJA-01",
        max_length=20,
        widget=forms.TextInput(
            attrs={
                "class": "form-control"
            }
        )
    )

    nombre_caja = forms.CharField(
        label="Nombre de la caja",
        initial="Caja Principal",
        max_length=100,
        widget=forms.TextInput(
            attrs={
                "class": "form-control"
            }
        )
    )

    # ============================================
    # ADMINISTRADOR
    # ============================================

    username = forms.CharField(
        label="Usuario administrador",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control"
            }
        )
    )

    first_name = forms.CharField(
        label="Nombre",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control"
            }
        )
    )

    last_name = forms.CharField(
        label="Apellido",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "class": "form-control"
            }
        )
    )

    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(
            attrs={
                "class": "form-control"
            }
        )
    )

    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control"
            }
        )
    )

    confirmar_password = forms.CharField(
        label="Confirmar contraseña",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control"
            }
        )
    )

    def clean(self):

        cleaned = super().clean()

        if (
            cleaned.get("password")
            != cleaned.get("confirmar_password")
        ):
            raise forms.ValidationError(
                "Las contraseñas no coinciden."
            )

        return cleaned
