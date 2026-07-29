# apps/core/models.py
from django.db import models
from .models_config import SistemaConfiguracion

class Empresa(models.Model):

    nombre = models.CharField(
        max_length=200
    )

    razon_social = models.CharField(
        max_length=250,
        blank=True
    )

    nit = models.CharField(
        max_length=50,
        blank=True
    )

    direccion = models.CharField(
        max_length=250,
        blank=True
    )

    ciudad = models.CharField(
        max_length=120,
        blank=True
    )

    telefono = models.CharField(
        max_length=50,
        blank=True
    )

    email = models.EmailField(
        blank=True
    )

    sitio_web = models.CharField(
        max_length=150,
        blank=True
    )

    logo = models.ImageField(
        upload_to="empresa/",
        blank=True,
        null=True
    )

    activa = models.BooleanField(
        default=True
    )

    creada = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:

        verbose_name = "Empresa"

        verbose_name_plural = "Empresas"

    def __str__(self):

        return self.nombre

    
class Sucursal(models.Model):

    empresa = models.ForeignKey(
        Empresa,
        on_delete=models.CASCADE,
        related_name="sucursales",
        null=True,
        blank=True,
    )

    nombre = models.CharField(max_length=150)
    direccion = models.TextField()

    lista_precio_default = models.ForeignKey(
        "sales.ListaPrecio",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sucursales_default"
    )

    activa = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre