# accounts/models.py
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Sucursal


class UserProfile(models.Model):
    class Role(models.TextChoices):
        SUPER_ADMIN = "SUPER_ADMIN", "Super Administrador"
        ADMIN_SUCURSAL = "ADMIN_SUCURSAL", "Administrador de sucursal"
        SUPERVISOR = "SUPERVISOR", "Supervisor de caja"
        CAJERO = "CAJERO", "Cajero"
        INVENTARIO = "INVENTARIO", "Inventario"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.CAJERO,
    )
    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="usuarios",
    )

    class Meta:
        indexes = [
            models.Index(fields=["role"]),
            models.Index(fields=["sucursal", "role"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"


@receiver(post_save, sender=User)
def crear_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def guardar_user_profile(sender, instance, **kwargs):
    if hasattr(instance, "profile"):
        instance.profile.save()