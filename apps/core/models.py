# apps/core/models.py
from django.db import models


class Sucursal(models.Model):

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