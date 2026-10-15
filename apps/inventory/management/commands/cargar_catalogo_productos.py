from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.inventory.data.catalogo_productos import PRODUCTOS
from apps.inventory.models import Color, ProductoBase, ProductoVariante, Talla, TipoTela


class Command(BaseCommand):
    help = (
        "Crea productos y variantes desde inventory/data/catalogo_productos.py "
        "sin duplicar ni alterar registros existentes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--actualizar",
            action="store_true",
            help=(
                "Actualiza únicamente descripción, estado, precios, costo y "
                "stock mínimo de elementos ya existentes. Nunca cambia SKU, "
                "código de barras, stock ni historial."
            ),
        )
        parser.add_argument(
            "--simular",
            action="store_true",
            help="Muestra el resultado esperado sin guardar cambios en la base.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        actualizar = options["actualizar"]
        simular = options["simular"]
        creados_productos = creadas_variantes = existentes = actualizados = 0

        for indice, datos_producto in enumerate(PRODUCTOS, start=1):
            nombre = str(datos_producto.get("nombre", "")).strip()
            if not nombre:
                raise CommandError(f"Producto #{indice}: falta 'nombre'.")

            producto = ProductoBase.objects.filter(nombre__iexact=nombre).first()
            nombre_anterior = str(
                datos_producto.get("nombre_anterior", "")
            ).strip()

            if producto is None and nombre_anterior:
                producto_anterior = ProductoBase.objects.filter(
                    nombre__iexact=nombre_anterior
                ).first()
                if producto_anterior and actualizar:
                    if simular:
                        self.stdout.write(
                            f"[SIMULACIÓN] Renombraría producto: "
                            f"{producto_anterior.nombre} → {nombre}"
                        )
                    else:
                        producto_anterior.nombre = nombre
                        producto_anterior.save(update_fields=["nombre"])
                    producto = producto_anterior
                    actualizados += 1
                elif producto_anterior:
                    raise CommandError(
                        f"{nombre}: incluye nombre_anterior. Ejecute de forma "
                        "explícita con --actualizar para confirmar el renombre."
                    )

            if producto is None:
                if simular:
                    producto = ProductoBase(
                        nombre=nombre,
                        descripcion=str(datos_producto.get("descripcion", "")).strip(),
                        activo=bool(datos_producto.get("activo", True)),
                    )
                    self.stdout.write(f"[SIMULACIÓN] Crearía producto: {nombre}")
                else:
                    producto = ProductoBase.objects.create(
                        nombre=nombre,
                        descripcion=str(datos_producto.get("descripcion", "")).strip(),
                        activo=bool(datos_producto.get("activo", True)),
                    )
                creados_productos += 1
            elif actualizar:
                campos_producto = {
                    "descripcion": str(
                        datos_producto.get("descripcion", producto.descripcion)
                    ).strip(),
                    "activo": bool(datos_producto.get("activo", producto.activo)),
                }
                cambios = [
                    campo for campo, valor in campos_producto.items()
                    if getattr(producto, campo) != valor
                ]
                if cambios:
                    if simular:
                        self.stdout.write(
                            f"[SIMULACIÓN] Actualizaría producto: {producto.nombre}"
                        )
                    else:
                        for campo in cambios:
                            setattr(producto, campo, campos_producto[campo])
                        producto.save(update_fields=cambios)
                    actualizados += 1

            for indice_variante, datos in enumerate(datos_producto.get("variantes", []), start=1):
                tela = self._buscar(TipoTela, datos.get("tela"), "tela", nombre, indice_variante)
                color = self._buscar(Color, datos.get("color", "Sin Definir"), "color", nombre, indice_variante)
                talla = self._buscar(Talla, datos.get("talla"), "talla", nombre, indice_variante)

                # Un producto simulado todavía no tiene PK; por definición sus
                # variantes serían nuevas y no se consulta la base con él.
                variante = None if producto.pk is None else ProductoVariante.objects.filter(
                    producto_base=producto,
                    tipo_tela=tela,
                    color=color,
                    talla=talla,
                ).first()
                creada = variante is None
                if creada:
                    datos_nueva_variante = {
                        "precio_venta": Decimal(str(datos.get("precio_venta", 0))),
                        "costo_unitario": Decimal(str(datos.get("costo_unitario", 0))),
                        "stock_minimo": Decimal(str(datos.get("stock_minimo", 0))),
                        "activo": bool(datos.get("activo", True)),
                    }
                    if simular:
                        self.stdout.write(
                            f"[SIMULACIÓN] Crearía variante: {nombre} · "
                            f"{tela.nombre} · {color.nombre} · {talla.nombre}"
                        )
                    else:
                        variante = ProductoVariante.objects.create(
                            producto_base=producto,
                            tipo_tela=tela,
                            color=color,
                            talla=talla,
                            **datos_nueva_variante,
                        )
                if creada:
                    creadas_variantes += 1
                else:
                    existentes += 1
                    if actualizar:
                        campos_variante = {
                            "precio_venta": Decimal(
                                str(datos.get("precio_venta", variante.precio_venta))
                            ),
                            "costo_unitario": Decimal(
                                str(datos.get("costo_unitario", variante.costo_unitario))
                            ),
                            "stock_minimo": Decimal(
                                str(datos.get("stock_minimo", variante.stock_minimo))
                            ),
                            "activo": bool(datos.get("activo", variante.activo)),
                        }
                        cambios = [
                            campo for campo, valor in campos_variante.items()
                            if getattr(variante, campo) != valor
                        ]
                        if cambios:
                            if simular:
                                self.stdout.write(
                                    f"[SIMULACIÓN] Actualizaría variante: "
                                    f"{variante.sku}"
                                )
                            else:
                                for campo in cambios:
                                    setattr(variante, campo, campos_variante[campo])
                                variante.save(update_fields=cambios)
                            actualizados += 1

        if simular:
            transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS(
            f"Catálogo procesado: {creados_productos} productos nuevos, "
            f"{creadas_variantes} variantes nuevas, {existentes} variantes existentes, "
            f"{actualizados} actualizaciones."
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
