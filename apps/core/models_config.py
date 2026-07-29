# apps/core/models_config.py
from django.db import models
from django.contrib.auth.models import User


class SistemaConfiguracion(models.Model):

    instalado = models.BooleanField(
        default=False
    )


    fecha_instalacion = models.DateTimeField(
        auto_now_add=True
    )


    usuario_inicial = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )


    version_instalacion = models.CharField(
        max_length=20,
        default="1.0"
    )


    actualizado = models.DateTimeField(
        auto_now=True
    )


    class Meta:

        verbose_name = "Configuración del sistema"

        verbose_name_plural = "Configuración del sistema"



    def __str__(self):

        return (
            "Sistema instalado"
            if self.instalado
            else
            "Sistema pendiente"
        )
