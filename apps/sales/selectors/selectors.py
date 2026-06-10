# apps/sales/selectors/selectors.py
from django.db.models import Prefetch
from apps.sales.models import Venta, VentaItem


class VentaSelector:

    @staticmethod
    def venta_con_items(venta_id, sucursal):
        return (
            Venta.objects
            .select_related("usuario", "turno")
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=VentaItem.objects.select_related(
                        "variante",
                        "variante__producto_base",
                        "variante__color",
                        "variante__tipo_tela",
                    )
                )
            )
            .filter(id=venta_id, sucursal=sucursal)
            .first()
        )

    @staticmethod
    def venta_abierta_usuario(usuario, sucursal):
        return (
            Venta.objects
            .prefetch_related(
                Prefetch(
                    "items",
                    queryset=VentaItem.objects.select_related("producto")
                )
            )
            .filter(usuario=usuario, sucursal=sucursal, estado="ABIERTA")
            .first()
        )