# apps/setup/service/setup_service.py
from django.db import transaction
from django.contrib.auth.models import User
from apps.accounts.models import UserProfile
from apps.core.models import (
    Empresa,
    Sucursal,
)
from apps.sales.models import (
    Caja,
    ListaPrecio,
)
from apps.sales.models_caja_enterprise import (
    Boveda,
    TurnoCaja,
)

from apps.setup.service.initial_data_service import InitialDataService
from apps.setup.service.setup_checker import SetupChecker
from apps.core.models_config import SistemaConfiguracion

class SetupService:

    @staticmethod
    @transaction.atomic
    def crear_sistema(datos):

        # ==================================================
        # VALIDAR QUE NO ESTE CONFIGURADO
        # ==================================================
        if SetupChecker.sistema_configurado():

            raise Exception(
                "El sistema ya está instalado. Use administración."
            )

        # ==================================================
        # CREAR EMPRESA
        # ==================================================
        empresa = Empresa.objects.create(

            nombre=datos["nombre_empresa"],

            activa=True

        )

        # ==================================================
        # CREAR SUCURSAL
        # ==================================================
        sucursal = Sucursal.objects.create(

            empresa=empresa,

            nombre=datos["nombre_sucursal"],

            direccion=datos["direccion"],

            activa=True

        )

        # ==================================================
        # CREAR LISTA DETAL
        # ==================================================
        lista_detal = ListaPrecio.objects.create(

            sucursal=sucursal,

            nombre="Precio Detal",

            tipo_venta="DETAL",

            activa=True

        )

        # ==================================================
        # CREAR LISTA MAYORISTA
        # ==================================================

        ListaPrecio.objects.create(

            sucursal=sucursal,

            nombre="Precio Mayorista",

            tipo_venta="MAYORISTA",

            activa=True

        )

        # ==================================================
        # LISTA DEFAULT DE SUCURSAL
        # ==================================================
        sucursal.lista_precio_default = lista_detal

        sucursal.save(
            update_fields=[
                "lista_precio_default"
            ]
        )

        # ==================================================
        # CREAR BOVEDA
        # ==================================================
        Boveda.objects.create(

            sucursal=sucursal,

            saldo_actual=0

        )

        # ==================================================
        # CREAR CAJA
        # ==================================================
        caja = Caja.objects.create(

            sucursal=sucursal,

            codigo=datos["codigo_caja"],

            nombre=datos["nombre_caja"],

            activa=True

        )

        # ==================================================
        # CREAR O ACTUALIZAR USUARIO ADMIN
        # ==================================================
        usuario, creado = User.objects.get_or_create(

            username=datos["username"],

            defaults={

                "first_name": datos["first_name"],

                "last_name": datos["last_name"],

                "email": datos["email"],

                "is_staff": True,

                "is_superuser": True,

                "is_active": True,

            }

        )


        # Actualizar datos si el usuario ya existía

        usuario.first_name = datos["first_name"]

        usuario.last_name = datos["last_name"]

        usuario.email = datos["email"]

        usuario.is_staff = True

        usuario.is_superuser = True

        usuario.is_active = True


        usuario.set_password(
            datos["password"]
        )


        usuario.save()


        # ==================================================
        # CREAR O ACTUALIZAR PERFIL
        # ==================================================
        perfil, _ = UserProfile.objects.get_or_create(

            user=usuario

        )

        perfil.role = "SUPER_ADMIN"
        perfil.sucursal = None
        perfil.save()

        # ==================================================
        # DATOS MAESTROS INICIALES
        # ==================================================

        InitialDataService.crear_datos_base()

        # ==================================================
        # MARCAR SISTEMA COMO INSTALADO
        # ==================================================

        SistemaConfiguracion.objects.update_or_create(

            id=1,

            defaults={

                "instalado": True,

                "usuario_inicial": usuario,

                "version_instalacion": "1.0",

            }

        )

        return {
            "usuario": usuario,
            "empresa": empresa,
            "sucursal": sucursal,
            "caja": caja,
        }

