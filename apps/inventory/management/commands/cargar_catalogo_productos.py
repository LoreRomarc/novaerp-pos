from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.inventory.data.catalogo_productos import PRODUCTOS
from apps.inventory.models import Color, ProductoBase, ProductoVariante, Talla, TipoTela


class Command(BaseCommand):
    help = "Crea o actualiza productos y variantes desde inventory/data/catalogo_productos.py."

    @transaction.atomic
    def handle(self, *args, **options):
        creados_productos = creadas_variantes = existentes = 0

        for indice, datos_producto in enumerate(PRODUCTOS, start=1):
            nombre = str(datos_producto.get("nombre", "")).strip()
            if not nombre:
                raise CommandError(f"Producto #{indice}: falta 'nombre'.")

            producto = ProductoBase.objects.filter(nombre__iexact=nombre).first()
            if producto is None:
                producto = ProductoBase.objects.create(
                    nombre=nombre,
                    descripcion=str(datos_producto.get("descripcion", "")).strip(),
                    activo=True,
                )
                creados_productos += 1

            for indice_variante, datos in enumerate(datos_producto.get("variantes", []), start=1):
                tela = self._buscar(TipoTela, datos.get("tela"), "tela", nombre, indice_variante)
                color = self._buscar(Color, datos.get("color", "Sin Definir"), "color", nombre, indice_variante)
                talla = self._buscar(Talla, datos.get("talla"), "talla", nombre, indice_variante)

                variante, creada = ProductoVariante.objects.get_or_create(
                    producto_base=producto,
                    tipo_tela=tela,
                    color=color,
                    talla=talla,
                    defaults={
                        "precio_venta": Decimal(str(datos.get("precio_venta", 0))),
                        "costo_unitario": Decimal(str(datos.get("costo_unitario", 0))),
                        "stock_minimo": Decimal(str(datos.get("stock_minimo", 0))),
                        "activo": True,
                    },
                )
                if creada:
                    creadas_variantes += 1
                else:
                    existentes += 1

        self.stdout.write(self.style.SUCCESS(
            f"Catálogo procesado: {creados_productos} productos nuevos, "
            f"{creadas_variantes} variantes nuevas, {existentes} variantes existentes."
        ))

    @staticmethod
    def _buscar(modelo, valor, etiqueta, producto, indice):
        valor = str(valor or "").strip()
        objeto = modelo.objects.filter(nombre__iexact=valor).first()
        if objeto is None:
            raise CommandError(
                f"{producto}, variante #{indice}: no existe {etiqueta} '{valor}'."
            )
        return objeto
