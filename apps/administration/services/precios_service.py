# apps/administration/services/precios_services.py
from django.core.exceptions import ValidationError
from django.db import transaction

from apps.sales.models import ListaPrecio, PrecioVariante


class PrecioMasivoService:
    """Operaciones de precios replicadas de forma segura entre sucursales."""

    @staticmethod
    @transaction.atomic
    def crear_listas(*, nombre, tipo_venta, sucursales, activa=True):
        """Crea o actualiza una lista del mismo tipo en varias sucursales."""
        sucursales = list(sucursales)

        if not sucursales:
            raise ValidationError("Seleccione al menos una sucursal.")

        listas = []

        for sucursal in sucursales:
            lista, _ = ListaPrecio.objects.update_or_create(
                sucursal=sucursal,
                tipo_venta=tipo_venta,
                defaults={
                    "nombre": nombre,
                    "activa": activa,
                },
            )

            # La lista detal sirve como referencia comercial inicial de la
            # sucursal cuando aún no se ha definido una predeterminada.
            if (
                tipo_venta == "DETAL"
                and sucursal.lista_precio_default_id is None
            ):
                sucursal.lista_precio_default = lista
                sucursal.save(update_fields=["lista_precio_default"])

            listas.append(lista)

        return listas

    @staticmethod
    @transaction.atomic
    def actualizar_listas(*, nombre, tipo_venta, sucursales, activa=True):
        """Actualiza la lista comercial y las sucursales que la usan.

        Cada sucursal conserva su lista técnica para que el POS la resuelva
        localmente. Al quitar una sede se desactiva su lista, sin eliminar
        precios ya registrados ni información histórica.
        """
        sucursales = list(sucursales)

        if not sucursales:
            raise ValidationError("Seleccione al menos una sucursal.")

        ListaPrecio.objects.select_for_update().filter(
            tipo_venta=tipo_venta,
        ).exclude(
            sucursal__in=sucursales,
        ).update(activa=False)

        return PrecioMasivoService.crear_listas(
            nombre=nombre,
            tipo_venta=tipo_venta,
            sucursales=sucursales,
            activa=activa,
        )

    @staticmethod
    @transaction.atomic
    def asignar_precios(*, variante, sucursales, precios_por_tipo):
        """Guarda uno o ambos precios de una variante en varias sucursales."""
        sucursales = list(sucursales)

        if not sucursales:
            raise ValidationError("Seleccione al menos una sucursal.")

        tipos = [
            tipo
            for tipo, precio in precios_por_tipo.items()
            if precio is not None
        ]

        if not tipos:
            raise ValidationError("Debe indicar al menos un precio válido.")

        listas = list(
            ListaPrecio.objects.select_for_update().filter(
                sucursal__in=sucursales,
                tipo_venta__in=tipos,
                activa=True,
            )
        )
        listas_por_clave = {
            (lista.sucursal_id, lista.tipo_venta): lista
            for lista in listas
        }
        faltantes = []

        for tipo in tipos:
            for sucursal in sucursales:
                if (sucursal.id, tipo) not in listas_por_clave:
                    faltantes.append(
                        f"{sucursal.nombre} ({tipo.title()})"
                    )

        if faltantes:
            raise ValidationError(
                "Faltan listas activas en: " + ", ".join(faltantes)
                + ". Créelas primero desde Listas de precios."
            )

        for tipo, precio in precios_por_tipo.items():
            if precio is None:
                continue

            for sucursal in sucursales:
                PrecioVariante.objects.update_or_create(
                    variante=variante,
                    lista=listas_por_clave[(sucursal.id, tipo)],
                    defaults={"precio": precio},
                )

        return len(sucursales) * len(tipos)
