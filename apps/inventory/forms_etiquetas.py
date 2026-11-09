from django import forms

from apps.inventory.models import ConfiguracionEtiquetaProducto


class ConfiguracionEtiquetaProductoForm(forms.ModelForm):
    class Meta:
        model = ConfiguracionEtiquetaProducto
        fields = [
            "ancho_mm", "alto_mm", "margen_lateral_mm", "margen_superior_mm",
            "margen_inferior_mm", "alto_barra_mm", "ancho_modulo_mm",
            "tamano_nombre_pt", "tamano_codigo_pt", "espacio_nombre_codigo_mm",
            "espacio_codigo_texto_mm",
        ]
        widgets = {
            campo: forms.NumberInput(attrs={"class": "form-control", "step": "0.1", "min": "0"})
            for campo in fields
        }
