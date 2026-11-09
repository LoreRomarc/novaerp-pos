"""Importación segura de catálogo y existencias desde POS_JNSTUDIO.

El archivo JSON de origen conserva ventas y pagos históricos, pero este comando
no los recrea como operaciones NovaERP: hacerlo afectaría caja, reportes y
stock por segunda vez. Importa sólo los datos necesarios para continuar la
operación: maestros, sucursales, vendedores, precios y stock inicial.
"""

import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.core.models import Empresa, Sucursal
from apps.inventory.models import (
    Color,
    MovimientoStock,
    ProductoBase,
    ProductoVariante,
    ProductoVarianteCodigoBarra,
    RegistroMigracionExterna,
    Stock,
    Talla,
    TipoTela,
)
from apps.sales.models import ListaPrecio, PrecioVariante, Vendedor


def texto(valor):
    return str(valor or "").strip().upper()


def decimal(valor, etiqueta):
    try:
        return Decimal(str(valor))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise CommandError(f"Valor inválido para {etiqueta}: {valor!r}.") from error


class Command(BaseCommand):
    help = (
        "Importa maestros, códigos de barra, precios y stock inicial desde "
        "el JSON generado por POS_JNSTUDIO. Nunca crea ventas históricas."
    )

    def add_arguments(self, parser):
        parser.add_argument("--archivo", required=True, help="Ruta al JSON exportado desde POS_JNSTUDIO.")
        parser.add_argument("--empresa", default="", help="Empresa NovaERP a usar; si se omite usa la primera.")
        parser.add_argument("--dry-run", action="store_true", help="Valida y muestra resultados sin guardar.")
        parser.add_argument(
            "--ajustar-stock-negativo",
            action="store_true",
            help=(
                "Convierte existencias negativas heredadas en cero. El valor "
                "original queda conservado en el JSON de exportación."
            ),
        )

    @transaction.atomic
    def handle(self, *args, **options):
        archivo = Path(options["archivo"]).expanduser()
        if not archivo.is_file():
            raise CommandError(f"No existe el archivo: {archivo}")
        try:
            origen = json.loads(archivo.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as error:
            raise CommandError(f"No se pudo leer el JSON: {error}") from error
        if origen.get("formato") != "POS_JNSTUDIO_A_NOVAERP":
            raise CommandError("El archivo no corresponde a una exportación válida de POS_JNSTUDIO.")

        resumen = {clave: 0 for clave in (
            "sucursales", "telas", "tallas", "productos", "variantes",
            "vendedores", "precios", "stocks", "conflictos_codigo",
            "stocks_negativos_ajustados", "codigos_alternos",
        )}
        empresa = self._empresa(options["empresa"], resumen)
        catalogos = origen.get("catalogos", {})
        color, _ = self._por_nombre(Color, "SIN DEFINIR", codigo_hex="#6B7280")

        sucursales = self._importar_sucursales(catalogos.get("locales", []), empresa, resumen)
        telas = self._importar_maestro(TipoTela, catalogos.get("telas", []), resumen, "telas")
        tallas = self._importar_maestro(Talla, catalogos.get("tallas", []), resumen, "tallas")
        # El POS antiguo permite variantes sin tela o talla. Se conservan con
        # maestros explícitos, en vez de asignarlas arbitrariamente a otro.
        tela_sin_definir, creada = self._por_nombre(TipoTela, "SIN DEFINIR")
        telas.setdefault("SIN DEFINIR", tela_sin_definir)
        resumen["telas"] += int(creada)
        talla_sin_definir, creada = self._por_nombre(Talla, "SIN TALLA")
        tallas.setdefault("SIN TALLA", talla_sin_definir)
        resumen["tallas"] += int(creada)
        productos = self._importar_maestro(ProductoBase, catalogos.get("productos", []), resumen, "productos")
        variantes = self._importar_variantes(
            origen.get("variantes", []),
            productos,
            telas,
            tallas,
            color,
            resumen,
        )
        self._importar_vendedores(catalogos.get("vendedores", []), sucursales, resumen)
        precios_origen = {
            str(item.get("id_origen")): item
            for item in origen.get("variantes", [])
        }
        self._importar_stock_y_precios(
            origen.get("inventario", []),
            sucursales,
            variantes,
            precios_origen,
            resumen,
            options["ajustar_stock_negativo"],
        )

        if options["dry_run"]:
            transaction.set_rollback(True)
            prefijo = "SIMULACIÓN: "
        else:
            prefijo = "IMPORTACIÓN COMPLETADA: "
        self.stdout.write(self.style.SUCCESS(
            prefijo + "; ".join(f"{clave}={valor}" for clave, valor in resumen.items())
        ))
        historial = origen.get("historial", {})
        self.stdout.write(
            "Historial conservado en el JSON, sin recrearlo como operación nueva: "
            f"ventas={len(historial.get('ventas', []))}; "
            f"movimientos={len(historial.get('movimientos_inventario', []))}."
        )

    def _empresa(self, nombre, resumen):
        if nombre:
            empresa = Empresa.objects.filter(nombre__iexact=nombre.strip()).first()
            if empresa is None:
                raise CommandError(f"No existe la empresa NovaERP '{nombre}'.")
            return empresa
        empresa = Empresa.objects.order_by("id").first()
        if empresa:
            return empresa
        empresa = Empresa.objects.create(nombre="EMPRESA MIGRADA POS_JNSTUDIO")
        return empresa

    def _por_nombre(self, modelo, nombre, **defaults):
        nombre = texto(nombre)
        objeto = modelo.objects.filter(nombre__iexact=nombre).first()
        if objeto:
            return objeto, False
        return modelo.objects.create(nombre=nombre, **defaults), True

    def _importar_sucursales(self, datos, empresa, resumen):
        resultado = {}
        for item in datos:
            nombre = texto(item.get("nombre"))
            if not nombre:
                continue
            sucursal = Sucursal.objects.filter(nombre__iexact=nombre).first()
            if sucursal is None:
                sucursal = Sucursal.objects.create(
                    empresa=empresa,
                    nombre=nombre,
                    direccion="MIGRADA DESDE POS_JNSTUDIO",
                    activa=True,
                )
                resumen["sucursales"] += 1
            resultado[nombre] = sucursal
        if not resultado:
            raise CommandError("La exportación no contiene locales/sucursales.")
        return resultado

    def _importar_maestro(self, modelo, datos, resumen, clave):
        resultado = {}
        for item in datos:
            nombre = texto(item.get("nombre"))
            if not nombre:
                continue
            objeto, creado = self._por_nombre(modelo, nombre)
            if creado:
                resumen[clave] += 1
            resultado[nombre] = objeto
        return resultado

    def _importar_variantes(self, datos, productos, telas, tallas, color, resumen):
        resultado = {}
        for item in datos:
            producto_nombre = texto(item.get("producto"))
            tela_nombre = texto(item.get("tela")) or "SIN DEFINIR"
            talla_nombre = texto(item.get("talla")) or "SIN TALLA"
            producto = productos.get(producto_nombre)
            tela = telas.get(tela_nombre)
            talla = tallas.get(talla_nombre)
            if not all((producto, tela, talla)):
                raise CommandError(
                    f"Variante origen {item.get('id_origen')}: faltan maestros "
                    f"({producto_nombre}, {tela_nombre}, {talla_nombre})."
                )
            variante = ProductoVariante.objects.filter(
                producto_base=producto, tipo_tela=tela, color=color, talla=talla
            ).first()
            codigo = texto(item.get("codigo_barras")) or None
            if variante is None:
                if codigo and ProductoVariante.objects.filter(codigo_barras__iexact=codigo).exists():
                    resumen["conflictos_codigo"] += 1
                    codigo = None
                variante = ProductoVariante.objects.create(
                    producto_base=producto,
                    tipo_tela=tela,
                    color=color,
                    talla=talla,
                    codigo_barras=codigo,
                    precio_venta=decimal(item.get("precio_detal", 0), "precio detal"),
                )
                resumen["variantes"] += 1
            elif codigo and variante.codigo_barras != codigo:
                codigo_principal_usado = ProductoVariante.objects.exclude(
                    pk=variante.pk
                ).filter(codigo_barras__iexact=codigo).exists()
                if codigo_principal_usado:
                    resumen["conflictos_codigo"] += 1
                else:
                    _, creado = ProductoVarianteCodigoBarra.objects.get_or_create(
                        codigo=codigo,
                        defaults={
                            "variante": variante,
                            "origen": "POS_JNSTUDIO",
                        },
                    )
                    if creado:
                        resumen["codigos_alternos"] += 1
            resultado[str(item.get("id_origen"))] = variante
            self._registrar_origen("VARIANTE", item.get("id_origen"), variante, item)
        return resultado

    @staticmethod
    def _registrar_origen(tipo_registro, id_origen, objeto_destino, datos_origen):
        """Conserva la relación de auditoría sin alterar el modelo operativo."""
        RegistroMigracionExterna.objects.update_or_create(
            origen="POS_JNSTUDIO",
            tipo_registro=tipo_registro,
            id_origen=str(id_origen),
            defaults={
                "modelo_destino": objeto_destino._meta.label,
                "id_destino": objeto_destino.pk,
                "datos_origen": datos_origen,
            },
        )

    def _importar_vendedores(self, datos, sucursales, resumen):
        sucursal_predeterminada = next(iter(sucursales.values()))
        for item in datos:
            nombre = texto(item.get("nombre"))
            if not nombre:
                continue
            vendedor = Vendedor.objects.filter(
                sucursal=sucursal_predeterminada, nombre__iexact=nombre
            ).first()
            if vendedor is None:
                Vendedor.objects.create(
                    sucursal=sucursal_predeterminada,
                    nombre=nombre,
                    telefono=str(item.get("telefono") or "").strip(),
                    activo=bool(item.get("activo", True)),
                )
                resumen["vendedores"] += 1

    def _listas(self, sucursal):
        mayor, _ = ListaPrecio.objects.get_or_create(
            sucursal=sucursal,
            tipo_venta="MAYORISTA",
            defaults={"nombre": "MAYORISTA", "activa": True},
        )
        detal, _ = ListaPrecio.objects.get_or_create(
            sucursal=sucursal,
            tipo_venta="DETAL",
            defaults={"nombre": "DETAL", "activa": True},
        )
        return mayor, detal

    def _importar_stock_y_precios(
        self, datos, sucursales, variantes, precios_origen, resumen,
        ajustar_stock_negativo,
    ):
        for item in datos:
            sucursal = sucursales.get(texto(item.get("local")))
            variante = variantes.get(str(item.get("variante_origen_id")))
            if not sucursal or not variante:
                continue
            cantidad = decimal(item.get("cantidad", 0), "stock")
            if cantidad < 0:
                if not ajustar_stock_negativo:
                    raise CommandError(
                        "Hay stock negativo heredado. Revise el origen o ejecute "
                        "nuevamente con --ajustar-stock-negativo. Registro: "
                        f"{item!r}"
                    )
                self.stdout.write(self.style.WARNING(
                    f"Stock negativo ajustado a cero: {item!r}"
                ))
                cantidad = Decimal("0")
                resumen["stocks_negativos_ajustados"] += 1
            referencia = f"MIGRACION-POS-JNSTUDIO-{item.get('variante_origen_id')}-{sucursal.id}"
            movimiento = MovimientoStock.objects.filter(referencia=referencia).first()
            if movimiento is None and cantidad > 0:
                stock, _ = Stock.objects.get_or_create(
                    sucursal=sucursal,
                    variante=variante,
                    defaults={"cantidad": Decimal("0"), "costo_promedio": Decimal("0")},
                )
                stock.cantidad += cantidad
                stock.save(update_fields=["cantidad"])
                MovimientoStock.objects.create(
                    sucursal=sucursal,
                    variante=variante,
                    tipo="INICIAL",
                    cantidad=cantidad,
                    saldo_post_movimiento=stock.cantidad,
                    referencia=referencia,
                    observacion="INVENTARIO INICIAL MIGRADO DESDE POS_JNSTUDIO",
                    costo_unitario=stock.costo_promedio,
                )
                self._registrar_origen(
                    "INVENTARIO",
                    f"{item.get('local')}:{item.get('variante_origen_id')}",
                    stock,
                    item,
                )
                resumen["stocks"] += 1
            mayor, detal = self._listas(sucursal)
            origen_variante = precios_origen.get(
                str(item.get("variante_origen_id")), {}
            )
            for lista, campo in ((mayor, "precio_mayor"), (detal, "precio_detal")):
                precio = decimal(origen_variante.get(campo, 0), campo)
                if precio <= 0:
                    continue
                _, creado = PrecioVariante.objects.get_or_create(
                    lista=lista,
                    variante=variante,
                    defaults={"precio": precio},
                )
                resumen["precios"] += int(creado)
