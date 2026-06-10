# accounts/models.py
from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.core.models import Sucursal


class UserProfile(models.Model):

    ROLE_CHOICES = (
        ('SUPER_ADMIN', 'Super Administrador'),
        ('ADMIN_SUCURSAL', 'Administrador de Sucursal'),
        ('CAJERO', 'Cajero'),
        ('INVENTARIO', 'Inventario'),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile"
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default='CAJERO' 
    )

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


# ======================================================
# AUTO CREACIÓN DE PROFILE (CLAVE)
# ======================================================

# @receiver(post_save, sender=User)
# def crear_user_profile(sender, instance, created, **kwargs):
#     if created:
#         UserProfile.objects.create(user=instance)


# @receiver(post_save, sender=User)
# def guardar_user_profile(sender, instance, **kwargs):
#     if hasattr(instance, "profile"):
#         instance.profile.save()