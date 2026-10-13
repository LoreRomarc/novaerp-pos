from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.accounts.models import UserProfile
from apps.core.models import Empresa, Sucursal
from apps.inventory.models import Color, ProductoBase, ProductoVariante, Stock, Talla, TipoTela
from apps.inventory.services.search_service import InventorySearchService
from apps.inventory.services.stock_service import InventoryService
from apps.inventory.views import TrasladoForm


class VarianteYBusquedaTests(TestCase):
    """Regresiones para creación automática y lectura por código de barras."""

    def setUp(self):
        self.empresa = Empresa.objects.create(nombre="Empresa de prueba")
        self.origen = Sucursal.objects.create(
            empresa=self.empresa, nombre="Origen", direccion="Calle 1"
        )
        self.destino = Sucursal.objects.create(
            empresa=self.empresa, nombre="Destino", direccion="Calle 2"
        )
        self.variante = ProductoVariante.objects.create(
            producto_base=ProductoBase.objects.create(nombre="Camisa"),
            tipo_tela=TipoTela.objects.create(nombre="Algodón"),
            color=Color.objects.create(nombre="Azul"),
            talla=Talla.objects.get_or_create(
                nombre="M", defaults={"orden": 1, "activo": True}
            )[0],
        )
        self.usuario = User.objects.create_user("inventario", password="segura")
        self.usuario.profile.role = UserProfile.Role.INVENTARIO
        self.usuario.profile.sucursal = self.origen
        self.usuario.profile.save()

    def test_variante_genera_sku_y_codigo_ean13_interno(self):
        self.assertTrue(self.variante.sku)
        self.assertEqual(len(self.variante.codigo_barras), 13)
        self.assertTrue(self.variante.codigo_barras.isdigit())

    def test_busqueda_serializa_talla_como_texto(self):
        resultados = InventorySearchService.search_variantes(
            self.variante.codigo_barras
        )
        datos = InventorySearchService.serialize(resultados)
        self.assertEqual(datos[0]["id"], self.variante.id)
        self.assertEqual(datos[0]["codigo_barras"], self.variante.codigo_barras)
        self.assertEqual(datos[0]["talla"], "M")

    def test_traslado_exige_sucursales_diferentes_y_motivo(self):
        form = TrasladoForm(data={
            "tipo": "COMPLETO",
            "origen": self.origen.id,
            "destino": self.origen.id,
            "variante": self.variante.id,
            "cantidad": "1",
            "motivo": "Prueba",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("Origen y destino no pueden ser iguales.", form.non_field_errors())

    def test_stock_y_kardex_se_mantienen_separados_por_sucursal(self):
        InventoryService.agregar_stock(
            variante=self.variante, cantidad="5", user=self.usuario,
            sucursal_id=self.origen.id, tipo="INICIAL", referencia="PRUEBA",
        )
        InventoryService.agregar_stock(
            variante=self.variante, cantidad="3", user=self.usuario,
            sucursal_id=self.destino.id, tipo="INICIAL", referencia="PRUEBA",
        )
        InventoryService.descontar_stock(
            variante=self.variante, cantidad="2", user=self.usuario,
            sucursal_id=self.origen.id, referencia="PRUEBA",
        )

        self.assertEqual(Stock.objects.get(variante=self.variante, sucursal=self.origen).cantidad, 3)
        self.assertEqual(Stock.objects.get(variante=self.variante, sucursal=self.destino).cantidad, 3)
        with self.assertRaises(ValidationError):
            InventoryService.descontar_stock(
                variante=self.variante, cantidad="4", user=self.usuario,
                sucursal_id=self.origen.id, referencia="PRUEBA",
            )
        self.assertEqual(Stock.objects.get(variante=self.variante, sucursal=self.origen).cantidad, 3)
