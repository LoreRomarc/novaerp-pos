from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from decimal import Decimal

from apps.accounts.models import UserProfile
from apps.core.models import Empresa, Sucursal
from apps.core.models_config import SistemaConfiguracion
from apps.inventory.models import Color, ProductoBase, ProductoVariante, Stock, Talla, TipoTela
from apps.sales.models import Caja, TurnoCajaUsuario, Venta, AbonoVenta, Carrito, CarritoItem
from apps.sales.models_caja_enterprise import CajaMovimiento, TurnoCaja
from apps.sales.services.caja_service import CajaService
from apps.sales.services.carrito_service import CarritoService
from apps.sales.services.credito_service import CreditoService


class TurnoOperableTests(TestCase):
    """Evita la regresión de enviar usuarios a abrir una segunda caja."""

    def setUp(self):
        empresa = Empresa.objects.create(nombre="Empresa de prueba")
        self.sucursal = Sucursal.objects.create(
            empresa=empresa, nombre="Sucursal", direccion="Calle 1"
        )
        SistemaConfiguracion.objects.create(instalado=True)
        self.superadmin = User.objects.create_user("superadmin", password="segura")
        self.superadmin.profile.role = UserProfile.Role.SUPER_ADMIN
        self.superadmin.profile.sucursal = self.sucursal
        self.superadmin.profile.save()

        self.admin = User.objects.create_user("admin", password="segura")
        self.admin.profile.role = UserProfile.Role.ADMIN_SUCURSAL
        self.admin.profile.sucursal = self.sucursal
        self.admin.profile.save()

        self.cajero = User.objects.create_user("cajero", password="segura")
        self.cajero.profile.role = UserProfile.Role.CAJERO
        self.cajero.profile.sucursal = self.sucursal
        self.cajero.profile.save()

        caja = Caja.objects.create(sucursal=self.sucursal, codigo="P01", nombre="Principal")
        self.turno = TurnoCaja.objects.create(
            caja=caja, sucursal=self.sucursal, usuario_apertura=self.superadmin
        )

    def test_administrador_de_sucursal_puede_operar_turno_abierto(self):
        self.assertEqual(
            CajaService.obtener_turno_operable(self.sucursal, self.admin),
            self.turno,
        )

    def test_cajero_requiere_asignacion_expresa_al_turno(self):
        self.assertIsNone(
            CajaService.obtener_turno_operable(self.sucursal, self.cajero)
        )
        TurnoCajaUsuario.objects.create(turno=self.turno, usuario=self.cajero)
        self.assertEqual(
            CajaService.obtener_turno_operable(self.sucursal, self.cajero),
            self.turno,
        )

    def test_abono_cierra_credito_y_deja_trazabilidad_en_caja(self):
        venta = Venta.objects.create(
            sucursal=self.sucursal,
            turno=self.turno,
            usuario=self.superadmin,
            estado="CREDITO",
            total=Decimal("15000"),
            monto_efectivo=Decimal("0"),
            monto_transferencia=Decimal("0"),
            monto_tarjeta=Decimal("0"),
            stock_descontado=True,
        )

        venta = CreditoService.registrar_abono(
            venta_id=venta.id,
            sucursal=self.sucursal,
            turno_id=self.turno.id,
            usuario=self.superadmin,
            pagos={"EFECTIVO": "15000", "TRANSFERENCIA": 0, "TARJETA": 0},
            observacion="pago total",
        )

        self.assertEqual(venta.estado, "CERRADA")
        self.assertEqual(venta.saldo_pendiente, Decimal("0"))
        self.assertEqual(AbonoVenta.objects.filter(venta=venta).count(), 1)
        self.assertTrue(
            CajaMovimiento.objects.filter(
                referencia_venta=venta,
                tipo=CajaMovimiento.Tipo.ABONO_CREDITO,
                monto=Decimal("15000"),
            ).exists()
        )

    def test_pantalla_creditos_es_accesible_para_cajero_asignado(self):
        TurnoCajaUsuario.objects.create(turno=self.turno, usuario=self.cajero)
        self.client.force_login(self.cajero)
        respuesta = self.client.get(reverse("sales:creditos"))
        self.assertEqual(respuesta.status_code, 200)

    def test_reporte_caja_separa_abonos_y_ticket_credito_es_imprimible(self):
        venta = Venta.objects.create(
            sucursal=self.sucursal,
            turno=self.turno,
            usuario=self.superadmin,
            cliente="Cliente de crédito",
            estado="CREDITO",
            total=Decimal("15000"),
            stock_descontado=True,
        )
        CreditoService.registrar_abono(
            venta_id=venta.id,
            sucursal=self.sucursal,
            turno_id=self.turno.id,
            usuario=self.superadmin,
            pagos={"EFECTIVO": "5000", "TRANSFERENCIA": 0, "TARJETA": 0},
        )
        self.client.force_login(self.superadmin)
        sesion = self.client.session
        sesion["sucursal_id"] = self.sucursal.id
        sesion.save()

        respuesta = self.client.get(reverse("sales:caja_reportes"))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(respuesta.context["resumen"]["abonos_efectivo"], Decimal("5000"))
        self.assertContains(respuesta, "Abonos a crédito")

        ticket = self.client.get(reverse("sales:ticket_venta", args=[venta.id]))
        self.assertEqual(ticket.status_code, 200)
        self.assertContains(ticket, "FACTURA DE VENTA A CRÉDITO")

    def test_reportes_filtran_credito_y_abonos_sin_duplicar_la_venta(self):
        venta = Venta.objects.create(
            sucursal=self.sucursal,
            turno=self.turno,
            usuario=self.superadmin,
            cliente="Cliente de filtros",
            estado="CREDITO",
            total=Decimal("15000"),
            stock_descontado=True,
        )
        CreditoService.registrar_abono(
            venta_id=venta.id,
            sucursal=self.sucursal,
            turno_id=self.turno.id,
            usuario=self.superadmin,
            pagos={"EFECTIVO": "5000", "TRANSFERENCIA": 0, "TARJETA": 0},
        )
        self.client.force_login(self.superadmin)
        sesion = self.client.session
        sesion["sucursal_id"] = self.sucursal.id
        sesion.save()

        ventas = self.client.get(
            reverse("sales:reportes"), {"tipo_pago": "CREDITO"}
        )
        self.assertEqual(ventas.status_code, 200)
        self.assertEqual(list(ventas.context["ventas"]), [venta])

        caja = self.client.get(
            reverse("sales:caja_reportes"), {"medio_pago": "CREDITO"}
        )
        self.assertEqual(caja.status_code, 200)
        self.assertTrue(
            CajaMovimiento.objects.filter(
                id__in=[movimiento.id for movimiento in caja.context["movimientos"]],
                tipo=CajaMovimiento.Tipo.ABONO_CREDITO,
                referencia_venta=venta,
            ).exists()
        )

    def test_credito_descuenta_stock_una_sola_vez_y_las_cuotas_no_duplican_venta(self):
        tela = TipoTela.objects.create(nombre="Algodón")
        color = Color.objects.create(nombre="Azul")
        talla = Talla.objects.get_or_create(
            nombre="M", defaults={"orden": 1, "activo": True}
        )[0]
        producto = ProductoBase.objects.create(nombre="Suéter crédito")
        variante = ProductoVariante.objects.create(
            producto_base=producto,
            tipo_tela=tela,
            color=color,
            talla=talla,
        )
        stock = Stock.objects.create(
            variante=variante, sucursal=self.sucursal, cantidad=Decimal("2")
        )
        carrito = Carrito.objects.create(usuario=self.superadmin, sucursal=self.sucursal)
        CarritoItem.objects.create(
            carrito=carrito,
            variante=variante,
            cantidad=Decimal("1"),
            precio_unitario=Decimal("10000"),
        )

        venta = CarritoService.finalizar(
            carrito=carrito,
            turno=self.turno,
            usuario=self.superadmin,
            pagos={"EFECTIVO": Decimal("4000")},
            permitir_credito=True,
        )
        stock.refresh_from_db()
        self.assertEqual(venta.estado, "CREDITO")
        self.assertEqual(stock.cantidad, Decimal("1"))
        self.assertEqual(
            CajaMovimiento.objects.filter(
                referencia_venta=venta, tipo=CajaMovimiento.Tipo.VENTA
            ).count(),
            1,
        )

        venta = CreditoService.registrar_abono(
            venta_id=venta.id,
            sucursal=self.sucursal,
            turno_id=self.turno.id,
            usuario=self.superadmin,
            pagos={"EFECTIVO": Decimal("6000")},
        )
        stock.refresh_from_db()
        self.assertEqual(venta.estado, "CERRADA")
        self.assertEqual(stock.cantidad, Decimal("1"))
        self.assertEqual(Venta.objects.filter(pk=venta.id).count(), 1)
        self.assertEqual(
            CajaMovimiento.objects.filter(
                referencia_venta=venta, tipo=CajaMovimiento.Tipo.ABONO_CREDITO
            ).count(),
            1,
        )
