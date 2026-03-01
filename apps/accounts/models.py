# apps/accounts/models.py
from django.db import models
from django.contrib.auth.models import User
from apps.core.models import Sucursal


class UserProfile(models.Model):

    ROLE_CHOICES = (
        ('SUPER_ADMIN', 'Super Administrador'),
        ('ADMIN_SUCURSAL', 'Administrador de Sucursal'),
        ('CAJERO', 'Cajero'),
        ('INVENTARIO', 'Inventario'),
    )

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios"
    )

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.role}"