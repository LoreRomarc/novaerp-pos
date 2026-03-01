# apps/customers/models.py

from django.db import models

class Cliente(models.Model):

    TIPO_CLIENTE = (
        ("DETAL", "Detal"),
        ("MAYORISTA", "Mayorista"),
    )

    nombre = models.CharField(max_length=200)
    identificacion = models.CharField(max_length=50, blank=True, null=True)

    tipo_cliente = models.CharField(
        max_length=20,
        choices=TIPO_CLIENTE,
        default="DETAL"
    )

    activo = models.BooleanField(default=True)

    def __str__(self):
        return self.nombre