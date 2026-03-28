# apps/inventory/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.inventory.models_produccion import IngresoProduccionDetalle
from apps.inventory.services.stock_domain_service import StockDomainService


@receiver(post_save, sender=IngresoProduccionDetalle)
def ingreso_produccion_stock(sender, instance, created, **kwargs):
    if not created:
        return

    StockDomainService.ingresar_produccion(instance)