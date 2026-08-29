# apps/sales/services/caja_service.py

from decimal import Decimal, InvalidOperation
import hashlib
import hmac

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.sales.models import Caja, TurnoCajaUsuario
from apps.sales.models_caja_enterprise import (
    ArqueoDenominacion,
    ArqueoTurno,
    Boveda,
    BovedaMovimiento,
    CajaMovimiento,
    TurnoCaja,
)


class CajaService:
    """
    Servicio central de Caja.

    REGLA:
    Las vistas NO deben modificar directamente:
        - TurnoCaja
        - CajaMovimiento
        - Boveda
        - BovedaMovimiento
        - ArqueoTurno

    Todo cambio financiero debe pasar por este servicio.
    """

    MEDIOS_VENTA_PERMITIDOS = {
        CajaMovimiento.MedioPago.EFECTIVO,
        CajaMovimiento.MedioPago.TARJETA,
        CajaMovimiento.MedioPago.TRANSFERENCIA,
    }

    TIPOS_MANUALES_PERMITIDOS = {
        CajaMovimiento.Tipo.INGRESO,
        CajaMovimiento.Tipo.EGRESO,
        CajaMovimiento.Tipo.AJUSTE,
        CajaMovimiento.Tipo.RETIRO_BOVEDA,
    }

    # ==========================================================
    # UTILIDADES
    # ==========================================================

    @staticmethod
    def decimal(valor, mensaje="El monto es inválido."):
        try:
            return Decimal(str(valor))
        except (InvalidOperation, TypeError, ValueError) as error:
            raise ValidationError(mensaje) from error

    @staticmethod
    def monto_positivo(
        monto,
        mensaje="El monto debe ser mayor a cero.",
    ):
        monto = CajaService.decimal(monto)

        if monto <= 0:
            raise ValidationError(mensaje)

        return monto

    @staticmethod
    def monto_no_negativo(
        monto,
        mensaje="El monto no puede ser negativo.",
    ):
        monto = CajaService.decimal(monto)

        if monto < 0:
            raise ValidationError(mensaje)

        return monto

    # ==========================================================
    # BÓVEDA
    # ==========================================================

    @staticmethod
    def obtener_boveda(sucursal):
        """
        Obtiene o crea la bóveda de la sucursal y la bloquea.
        """

        try:
            boveda, _ = Boveda.objects.get_or_create(
                sucursal=sucursal,
            )
        except IntegrityError:
            boveda = Boveda.objects.get(
                sucursal=sucursal,
            )

        return (
            Boveda.objects
            .select_for_update()
            .get(pk=boveda.pk)
        )

    @staticmethod
    def saldo_boveda(sucursal):
        boveda = Boveda.objects.filter(
            sucursal=sucursal
        ).first()

        if not boveda:
            return Decimal("0.00")

        return boveda.saldo_actual

    # ==========================================================
    # TURNOS
    # ==========================================================

    @staticmethod
    def obtener_turno_por_id(turno_id):
        if not turno_id:
            return None

        return (
            TurnoCaja.objects
            .select_related(
                "caja",
                "sucursal",
                "usuario_apertura",
                "usuario_supervisor",
            )
            .filter(
                pk=turno_id,
                estado=TurnoCaja.Estado.ABIERTO,
            )
            .first()
        )

    @staticmethod
    def obtener_turno_request(request):
        return CajaService.obtener_turno_por_id(
            request.session.get("turno_id")
        )

    @staticmethod
    def obtener_turno_activo_usuario(
        sucursal,
        usuario,
    ):
        return (
            TurnoCaja.objects
            .select_related(
                "caja",
                "sucursal",
                "usuario_apertura",
                "usuario_supervisor",
            )
            .filter(
                sucursal=sucursal,
                estado=TurnoCaja.Estado.ABIERTO,
            )
            .filter(
                Q(usuario_apertura=usuario)
                |
                Q(
                    cajeros__usuario=usuario,
                    cajeros__activo=True,
                )
            )
            .distinct()
            .order_by("-abierto_en")
            .first()
        )

    @staticmethod
    def obtener_turno_bloqueado(
        turno_id,
        sucursal=None,
        permitir_cerrado=False,
    ):
        filtros = {
            "id": turno_id,
        }

        if not permitir_cerrado:
            filtros["estado"] = TurnoCaja.Estado.ABIERTO

        if sucursal is not None:
            filtros["sucursal"] = sucursal

        # IMPORTANTE:
        # No usar select_related("usuario_supervisor")
        # junto con select_for_update(), porque usuario_supervisor
        # es nullable y PostgreSQL no permite FOR UPDATE sobre
        # el lado nullable de un OUTER JOIN.
        turno = (
            TurnoCaja.objects
            .select_for_update()
            .select_related(
                "caja",
                "sucursal",
                "usuario_apertura",
            )
            .filter(**filtros)
            .first()
        )

        if not turno:
            raise ValidationError(
                "El turno de caja no existe o no está disponible."
            )

        # El supervisor no hace falta para bloquear el turno.
        # Si existe, Django puede resolverlo posteriormente mediante
        # su relación normal.
        return turno

    # ==========================================================
    # AUTORIZACIONES
    # ==========================================================

    @staticmethod
    def validar_operador_turno(
        turno,
        usuario,
    ):
        if turno.usuario_apertura_id == usuario.id:
            return True

        if turno.usuario_supervisor_id == usuario.id:
            return True

        activo = (
            TurnoCajaUsuario.objects
            .filter(
                turno=turno,
                usuario=usuario,
                activo=True,
            )
            .exists()
        )

        if not activo:
            raise ValidationError(
                "El usuario no está autorizado para operar este turno."
            )

        return True

    @staticmethod
    def validar_gestor_turno(
        turno,
        usuario,
    ):
        perfil = getattr(
            usuario,
            "profile",
            None,
        )

        if not perfil:
            raise ValidationError(
                "El usuario no tiene un perfil configurado."
            )

        if perfil.role == "SUPER_ADMIN":
            return True

        if (
            perfil.role == "ADMIN_SUCURSAL"
            and perfil.sucursal_id == turno.sucursal_id
        ):
            return True

        if turno.usuario_supervisor_id == usuario.id:
            return True

        raise ValidationError(
            "El usuario no está autorizado para gestionar este turno."
        )

    # ==========================================================
    # APERTURA
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def abrir_caja(
        sucursal,
        usuario,
        monto_inicial,
        caja_id,
    ):
        monto_inicial = CajaService.monto_no_negativo(
            monto_inicial
        )

        caja = (
            Caja.objects
            .select_for_update()
            .filter(
                pk=caja_id,
                sucursal=sucursal,
                activa=True,
            )
            .first()
        )

        if not caja:
            raise ValidationError(
                "La caja no existe, no pertenece a la sucursal "
                "o está inactiva."
            )

        if TurnoCaja.objects.filter(
            caja=caja,
            estado=TurnoCaja.Estado.ABIERTO,
        ).exists():
            raise ValidationError(
                "La caja ya tiene un turno abierto."
            )

        if TurnoCaja.objects.filter(
            usuario_apertura=usuario,
            estado=TurnoCaja.Estado.ABIERTO,
        ).exists():
            raise ValidationError(
                "El usuario ya tiene un turno de caja abierto."
            )

        # Garantiza existencia de bóveda.
        CajaService.obtener_boveda(sucursal)

        try:
            turno = TurnoCaja.objects.create(
                caja=caja,
                sucursal=sucursal,
                usuario_apertura=usuario,
                monto_inicial=monto_inicial,
                estado=TurnoCaja.Estado.ABIERTO,
            )
        except IntegrityError as error:
            raise ValidationError(
                "La caja o el usuario ya tiene un turno abierto."
            ) from error

        TurnoCajaUsuario.objects.create(
            turno=turno,
            usuario=usuario,
            activo=True,
        )

        CajaMovimiento.objects.create(
            turno=turno,
            usuario=usuario,
            tipo=CajaMovimiento.Tipo.APERTURA,
            medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
            monto=monto_inicial,
            observacion="Apertura de caja",
        )

        return turno

    # ==========================================================
    # ASIGNAR / DESASIGNAR CAJERO
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def asignar_cajero(
        turno_id,
        usuario_asignado,
        usuario_responsable,
    ):
        turno = CajaService.obtener_turno_bloqueado(
            turno_id
        )

        CajaService.validar_gestor_turno(
            turno,
            usuario_responsable,
        )

        if usuario_asignado.id == turno.usuario_apertura_id:
            raise ValidationError(
                "El usuario que abrió la caja ya está asignado."
            )

        perfil = getattr(
            usuario_asignado,
            "profile",
            None,
        )

        if not perfil:
            raise ValidationError(
                "El usuario no tiene perfil."
            )

        if perfil.role != "CAJERO":
            raise ValidationError(
                "Solo se pueden asignar usuarios con rol CAJERO."
            )

        if perfil.sucursal_id != turno.sucursal_id:
            raise ValidationError(
                "El cajero pertenece a otra sucursal."
            )

        if TurnoCaja.objects.filter(
            cajeros__usuario=usuario_asignado,
            cajeros__activo=True,
            estado=TurnoCaja.Estado.ABIERTO,
        ).exists():
            raise ValidationError(
                "El cajero ya está trabajando en otro turno abierto."
            )

        try:
            asignacion = TurnoCajaUsuario.objects.create(
                turno=turno,
                usuario=usuario_asignado,
                activo=True,
            )
        except IntegrityError as error:
            raise ValidationError(
                "El cajero ya está asignado a este turno."
            ) from error

        return asignacion

    @staticmethod
    @transaction.atomic
    def desasignar_cajero(
        turno_id,
        usuario_asignado,
        usuario_responsable,
    ):
        turno = CajaService.obtener_turno_bloqueado(
            turno_id
        )

        CajaService.validar_gestor_turno(
            turno,
            usuario_responsable,
        )

        if turno.usuario_apertura_id == usuario_asignado.id:
            raise ValidationError(
                "No se puede desasignar al usuario que abrió la caja."
            )

        asignacion = (
            TurnoCajaUsuario.objects
            .select_for_update()
            .filter(
                turno=turno,
                usuario=usuario_asignado,
                activo=True,
            )
            .first()
        )

        if not asignacion:
            raise ValidationError(
                "El cajero no tiene una asignación activa."
            )

        asignacion.activo = False
        asignacion.desasignado_en = timezone.now()

        asignacion.save(
            update_fields=[
                "activo",
                "desasignado_en",
            ]
        )

        return asignacion

    # ==========================================================
    # SUPERVISOR
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def asignar_supervisor(
        turno_id,
        supervisor,
    ):
        turno = (
            TurnoCaja.objects
            .select_for_update()
            .select_related(
                "sucursal",
                "usuario_apertura",
            )
            .filter(pk=turno_id)
            .first()
        )

        if not turno:
            raise ValidationError(
                "El turno no existe."
            )

        if turno.estado != TurnoCaja.Estado.ABIERTO:
            raise ValidationError(
                "Solo se puede asignar supervisor a un turno abierto."
            )

        if supervisor.id == turno.usuario_apertura_id:
            raise ValidationError(
                "El cajero que abrió el turno no puede ser supervisor."
            )

        perfil = getattr(
            supervisor,
            "profile",
            None,
        )

        if not perfil:
            raise ValidationError(
                "El supervisor no tiene perfil."
            )

        roles = {
            "SUPER_ADMIN",
            "ADMIN_SUCURSAL",
            "SUPERVISOR",
        }

        if perfil.role not in roles:
            raise ValidationError(
                "El usuario seleccionado no tiene un rol autorizado."
            )

        if (
            perfil.role != "SUPER_ADMIN"
            and perfil.sucursal_id != turno.sucursal_id
        ):
            raise ValidationError(
                "El supervisor pertenece a otra sucursal."
            )

        if (
            turno.usuario_supervisor_id
            and turno.usuario_supervisor_id != supervisor.id
        ):
            raise ValidationError(
                "El turno ya tiene otro supervisor asignado."
            )

        turno.usuario_supervisor = supervisor

        turno.save(
            update_fields=[
                "usuario_supervisor",
            ]
        )

        return turno

    # ==========================================================
    # RESUMEN
    # ==========================================================

    @staticmethod
    def resumen_turno(turno):
        movimientos = (
            CajaMovimiento.objects
            .filter(turno=turno)
            .order_by("numero_secuencia")
        )

        resumen = {
            "monto_inicial": turno.monto_inicial,

            # Ventas normales, sin cambios.
            "ventas_efectivo": Decimal("0.00"),
            "ventas_tarjeta": Decimal("0.00"),
            "ventas_transferencia": Decimal("0.00"),

            # Excedentes cobrados por cambios.
            "cambios_efectivo": Decimal("0.00"),
            "cambios_tarjeta": Decimal("0.00"),
            "cambios_transferencia": Decimal("0.00"),

            # Reembolsos efectuados.
            "devoluciones_efectivo": Decimal("0.00"),
            "devoluciones_tarjeta": Decimal("0.00"),
            "devoluciones_transferencia": Decimal("0.00"),

            "ingresos": Decimal("0.00"),
            "egresos": Decimal("0.00"),
            "retiros": Decimal("0.00"),
            "ajustes": Decimal("0.00"),
        }

        for movimiento in movimientos:
            monto = movimiento.monto
            medio = movimiento.medio_pago

            if movimiento.tipo == CajaMovimiento.Tipo.VENTA:
                if medio == CajaMovimiento.MedioPago.EFECTIVO:
                    resumen["ventas_efectivo"] += monto

                elif medio == CajaMovimiento.MedioPago.TARJETA:
                    resumen["ventas_tarjeta"] += monto

                elif medio == CajaMovimiento.MedioPago.TRANSFERENCIA:
                    resumen["ventas_transferencia"] += monto

            elif movimiento.tipo == CajaMovimiento.Tipo.CAMBIO:
                if medio == CajaMovimiento.MedioPago.EFECTIVO:
                    resumen["cambios_efectivo"] += monto

                elif medio == CajaMovimiento.MedioPago.TARJETA:
                    resumen["cambios_tarjeta"] += monto

                elif medio == CajaMovimiento.MedioPago.TRANSFERENCIA:
                    resumen["cambios_transferencia"] += monto

            elif movimiento.tipo == CajaMovimiento.Tipo.DEVOLUCION:
                if medio == CajaMovimiento.MedioPago.EFECTIVO:
                    resumen["devoluciones_efectivo"] += monto

                elif medio == CajaMovimiento.MedioPago.TARJETA:
                    resumen["devoluciones_tarjeta"] += monto

                elif medio == CajaMovimiento.MedioPago.TRANSFERENCIA:
                    resumen["devoluciones_transferencia"] += monto

            elif movimiento.tipo == CajaMovimiento.Tipo.INGRESO:
                if medio == CajaMovimiento.MedioPago.EFECTIVO:
                    resumen["ingresos"] += monto

            elif movimiento.tipo == CajaMovimiento.Tipo.EGRESO:
                if medio == CajaMovimiento.MedioPago.EFECTIVO:
                    resumen["egresos"] += monto

            elif movimiento.tipo == CajaMovimiento.Tipo.RETIRO_BOVEDA:
                resumen["retiros"] += monto

            elif movimiento.tipo == CajaMovimiento.Tipo.AJUSTE:
                if medio == CajaMovimiento.MedioPago.EFECTIVO:
                    resumen["ajustes"] += monto

        resumen["ventas_total"] = (
            resumen["ventas_efectivo"]
            + resumen["ventas_tarjeta"]
            + resumen["ventas_transferencia"]
        )

        resumen["cambios_total"] = (
            resumen["cambios_efectivo"]
            + resumen["cambios_tarjeta"]
            + resumen["cambios_transferencia"]
        )

        resumen["devoluciones_total"] = (
            resumen["devoluciones_efectivo"]
            + resumen["devoluciones_tarjeta"]
            + resumen["devoluciones_transferencia"]
        )

        # Efectivo generado o retirado durante el turno,
        # sin incluir la base inicial.
        resumen["efectivo_operacion_neto"] = (
            resumen["ventas_efectivo"]
            + resumen["cambios_efectivo"]
            + resumen["ingresos"]
            + resumen["ajustes"]
            - resumen["egresos"]
            - resumen["retiros"]
            - resumen["devoluciones_efectivo"]
        )

        # Efectivo físico que debe existir al cierre.
        resumen["efectivo_esperado"] = (
            resumen["monto_inicial"]
            + resumen["efectivo_operacion_neto"]
        )

        resumen["pagos_no_efectivo"] = (
            resumen["ventas_tarjeta"]
            + resumen["ventas_transferencia"]
            + resumen["cambios_tarjeta"]
            + resumen["cambios_transferencia"]
            - resumen["devoluciones_tarjeta"]
            - resumen["devoluciones_transferencia"]
        )

        return resumen

    # ==========================================================
    # MOVIMIENTOS MANUALES
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def registrar_movimiento(
        turno,
        usuario,
        tipo,
        monto,
        observacion="",
        medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
    ):
        if not turno:
            raise ValidationError(
                "Turno de caja requerido."
            )

        turno = CajaService.obtener_turno_bloqueado(
            turno.id
        )

        CajaService.validar_operador_turno(
            turno,
            usuario,
        )

        if tipo not in CajaService.TIPOS_MANUALES_PERMITIDOS:
            raise ValidationError(
                "Tipo de movimiento no permitido."
            )

        monto = CajaService.monto_positivo(
            monto
        )

        observacion = (
            observacion or ""
        ).strip()

        if not observacion:
            raise ValidationError(
                "La observación es obligatoria."
            )

        # Los movimientos manuales son de efectivo.
        if medio_pago != CajaMovimiento.MedioPago.EFECTIVO:
            raise ValidationError(
                "Los movimientos manuales de caja deben ser en efectivo."
            )

        if tipo in {
            CajaMovimiento.Tipo.EGRESO,
            CajaMovimiento.Tipo.RETIRO_BOVEDA,
        }:
            resumen = CajaService.resumen_turno(
                turno
            )

            if monto > resumen["efectivo_esperado"]:
                raise ValidationError(
                    "El movimiento supera el efectivo disponible en caja."
                )

        if tipo == CajaMovimiento.Tipo.RETIRO_BOVEDA:
            return CajaService._registrar_retiro_boveda(
                turno=turno,
                monto=monto,
                usuario=usuario,
                observacion=observacion,
            )

        return CajaMovimiento.objects.create(
            turno=turno,
            usuario=usuario,
            tipo=tipo,
            medio_pago=medio_pago,
            monto=monto,
            observacion=observacion,
        )

    # ==========================================================
    # RETIRO A BÓVEDA
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def _registrar_retiro_boveda(
        turno,
        monto,
        usuario,
        observacion,
    ):
        turno = CajaService.obtener_turno_bloqueado(
            turno.id
        )

        CajaService.validar_operador_turno(
            turno,
            usuario,
        )

        monto = CajaService.monto_positivo(
            monto
        )

        resumen = CajaService.resumen_turno(
            turno
        )

        if monto > resumen["efectivo_esperado"]:
            raise ValidationError(
                "El retiro supera el efectivo disponible."
            )

        movimiento_caja = CajaMovimiento.objects.create(
            turno=turno,
            usuario=usuario,
            tipo=CajaMovimiento.Tipo.RETIRO_BOVEDA,
            medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
            monto=monto,
            observacion=observacion,
        )

        boveda = CajaService.obtener_boveda(
            turno.sucursal
        )

        BovedaMovimiento.objects.create(
            boveda=boveda,
            turno=turno,
            movimiento_caja=movimiento_caja,
            usuario=usuario,
            tipo=BovedaMovimiento.Tipo.RETIRO_CAJA,
            monto=monto,
            observacion=observacion,
        )

        boveda.saldo_actual += monto

        boveda.save(
            update_fields=[
                "saldo_actual",
                "actualizada_en",
            ]
        )

        return movimiento_caja

    @staticmethod
    @transaction.atomic
    def retiro_caja(
        turno_id,
        monto,
        usuario,
    ):
        turno = CajaService.obtener_turno_bloqueado(
            turno_id
        )

        return CajaService._registrar_retiro_boveda(
            turno=turno,
            monto=monto,
            usuario=usuario,
            observacion="Retiro a bóveda",
        )

    # ==========================================================
    # VENTAS
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def registrar_movimientos_venta(
        venta,
        usuario,
        pagos,
    ):
        if not isinstance(pagos, dict):
            raise ValidationError(
                "Los pagos de la venta son inválidos."
            )

        venta = (
            venta.__class__.objects
            .select_for_update()
            .select_related("sucursal")
            .get(pk=venta.pk)
        )

        turno = CajaService.obtener_turno_bloqueado(
            venta.turno_id,
            sucursal=venta.sucursal,
        )

        CajaService.validar_operador_turno(
            turno,
            usuario,
        )

        if venta.estado not in {
            "ABIERTA",
            "CERRADA",
        }:
            raise ValidationError(
                "La venta no tiene un estado financiero válido."
            )

        if CajaMovimiento.objects.filter(
            referencia_venta=venta,
            tipo=CajaMovimiento.Tipo.VENTA,
        ).exists():
            raise ValidationError(
                "La venta ya tiene movimientos de caja."
            )

        normalizados = {}

        for medio in CajaService.MEDIOS_VENTA_PERMITIDOS:
            normalizados[medio] = CajaService.decimal(
                pagos.get(medio, 0) or 0,
                f"El pago {medio} es inválido.",
            )

            if normalizados[medio] < 0:
                raise ValidationError(
                    f"El pago {medio} no puede ser negativo."
                )

        if set(pagos.keys()) - CajaService.MEDIOS_VENTA_PERMITIDOS:
            raise ValidationError(
                "La venta contiene medios de pago no permitidos."
            )

        total_pagado = sum(
            normalizados.values(),
            Decimal("0.00"),
        )

        if total_pagado < venta.total:
            raise ValidationError(
                "El pago no cubre el total de la venta."
            )

        tarjeta = normalizados[
            CajaMovimiento.MedioPago.TARJETA
        ]

        transferencia = normalizados[
            CajaMovimiento.MedioPago.TRANSFERENCIA
        ]

        efectivo_recibido = normalizados[
            CajaMovimiento.MedioPago.EFECTIVO
        ]

        no_efectivo = tarjeta + transferencia

        if no_efectivo > venta.total:
            raise ValidationError(
                "Tarjeta y transferencia no pueden superar el total."
            )

        efectivo_necesario = (
            venta.total - no_efectivo
        )

        if efectivo_recibido < efectivo_necesario:
            raise ValidationError(
                "El efectivo recibido no cubre el saldo."
            )

        efectivo_que_ingresa = efectivo_necesario

        if efectivo_que_ingresa > 0:
            cambio = (
                efectivo_recibido
                - efectivo_que_ingresa
            )

            observacion = f"Venta #{venta.id}"

            if cambio > 0:
                observacion += (
                    f" | Cambio entregado: {cambio}"
                )

            CajaMovimiento.objects.create(
                turno=turno,
                usuario=usuario,
                tipo=CajaMovimiento.Tipo.VENTA,
                medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
                monto=efectivo_que_ingresa,
                referencia_venta=venta,
                observacion=observacion,
            )

        if tarjeta > 0:
            CajaMovimiento.objects.create(
                turno=turno,
                usuario=usuario,
                tipo=CajaMovimiento.Tipo.VENTA,
                medio_pago=CajaMovimiento.MedioPago.TARJETA,
                monto=tarjeta,
                referencia_venta=venta,
                observacion=f"Venta #{venta.id}",
            )

        if transferencia > 0:
            CajaMovimiento.objects.create(
                turno=turno,
                usuario=usuario,
                tipo=CajaMovimiento.Tipo.VENTA,
                medio_pago=CajaMovimiento.MedioPago.TRANSFERENCIA,
                monto=transferencia,
                referencia_venta=venta,
                observacion=f"Venta #{venta.id}",
            )

        CajaService.verificar_retiro_automatico(
            turno
        )

    # ==========================================================
    # RETIRO AUTOMÁTICO
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def verificar_retiro_automatico(turno):
        limite = getattr(
            settings,
            "LIMITE_EFECTIVO_CAJA",
            None,
        )

        if limite in (None, ""):
            return None

        limite = CajaService.monto_positivo(
            limite,
            "LIMITE_EFECTIVO_CAJA debe ser mayor que cero.",
        )

        turno = CajaService.obtener_turno_bloqueado(
            turno.id
        )

        resumen = CajaService.resumen_turno(
            turno
        )

        if resumen["efectivo_esperado"] <= limite:
            return None

        exceso = (
            resumen["efectivo_esperado"]
            - limite
        )

        return CajaService._registrar_retiro_boveda(
            turno=turno,
            monto=exceso,
            usuario=turno.usuario_apertura,
            observacion=(
                "Retiro automático por límite de efectivo."
            ),
        )

    # ==========================================================
    # ARQUEO
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def crear_arqueo(
        turno,
        usuario,
        denominaciones,
        observacion="",
    ):
        if not turno:
            raise ValidationError(
                "Turno requerido."
            )

        turno = CajaService.obtener_turno_bloqueado(
            turno.id
        )

        CajaService.validar_operador_turno(
            turno,
            usuario,
        )

        if not isinstance(denominaciones, dict):
            raise ValidationError(
                "Las denominaciones deben ser un objeto."
            )

        total_contado = Decimal("0.00")
        limpias = []

        for valor, cantidad in denominaciones.items():
            denominacion = CajaService.decimal(
                valor,
                "Denominación inválida.",
            )

            try:
                cantidad = int(cantidad)
            except (TypeError, ValueError):
                raise ValidationError(
                    "Cantidad de denominación inválida."
                )

            if denominacion <= 0:
                raise ValidationError(
                    "La denominación debe ser mayor que cero."
                )

            if cantidad < 0:
                raise ValidationError(
                    "La cantidad no puede ser negativa."
                )

            if cantidad == 0:
                continue

            limpias.append(
                {
                    "denominacion": denominacion,
                    "cantidad": cantidad,
                }
            )

            total_contado += (
                denominacion * cantidad
            )

        resumen = CajaService.resumen_turno(
            turno
        )

        esperado = resumen[
            "efectivo_esperado"
        ]

        diferencia = (
            total_contado - esperado
        )

        try:
            arqueo = ArqueoTurno.objects.create(
                turno=turno,
                realizado_por=usuario,
                monto_esperado=esperado,
                total_contado=total_contado,
                diferencia=diferencia,
                observacion=(
                    observacion or ""
                ).strip(),
            )
        except IntegrityError as error:
            raise ValidationError(
                "Ya existe un arqueo pendiente para este turno."
            ) from error

        ArqueoDenominacion.objects.bulk_create(
            [
                ArqueoDenominacion(
                    arqueo=arqueo,
                    denominacion=item["denominacion"],
                    cantidad=item["cantidad"],
                )
                for item in limpias
            ]
        )

        return arqueo

    # ==========================================================
    # CIERRE
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def cerrar_caja(
        sucursal,
        usuario,
        turno_id=None,
        monto_real=None,
    ):
        if not turno_id:
            raise ValidationError(
                "Debe indicar el turno que desea cerrar."
            )

        turno = CajaService.obtener_turno_bloqueado(
            turno_id,
            sucursal=sucursal,
        )

        CajaService.validar_operador_turno(
            turno,
            usuario,
        )

        from apps.sales.models import Venta

        ventas_abiertas = Venta.objects.filter(
            turno=turno,
            estado="ABIERTA",
        ).exists()

        if ventas_abiertas:
            raise ValidationError(
                "No se puede cerrar la caja mientras existan ventas abiertas."
            )

        arqueo = (
            ArqueoTurno.objects.select_for_update()
            .filter(
                turno=turno,
                estado=ArqueoTurno.Estado.REGISTRADO,
            )
            .order_by("-creado_en", "-id")
            .first()
        )

        if not arqueo:
            raise ValidationError(
                "Debe realizar un arqueo antes de cerrar la caja."
            )

        resumen = CajaService.resumen_turno(turno)

        if arqueo.monto_esperado != resumen["efectivo_esperado"]:
            raise ValidationError(
                "El arqueo quedó desactualizado. Realice un nuevo arqueo."
            )

        monto_real_confirmado = arqueo.total_contado
        diferencia = (
            monto_real_confirmado
            - resumen["efectivo_esperado"]
        )

        turno.cerrar(
            monto_real=monto_real_confirmado,
            monto_esperado=resumen["efectivo_esperado"],
            diferencia=diferencia,
            usuario=usuario,
        )

        return turno

    # ==========================================================
    # DEVOLUCIONES
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def registrar_devolucion_venta(
        venta,
        turno_id,
        usuario,
        observacion="",
    ):
        if venta.estado != "CERRADA":
            raise ValidationError(
                "Solo se pueden devolver ventas cerradas."
            )

        turno = CajaService.obtener_turno_bloqueado(
            turno_id,
            sucursal=venta.sucursal,
        )

        CajaService.validar_operador_turno(
            turno,
            usuario,
        )

        if CajaMovimiento.objects.filter(
            referencia_venta=venta,
            tipo=CajaMovimiento.Tipo.DEVOLUCION,
        ).exists():
            raise ValidationError(
                "La venta ya tiene una devolución registrada."
            )

        movimientos = list(
            CajaMovimiento.objects.filter(
                referencia_venta=venta,
                tipo=CajaMovimiento.Tipo.VENTA,
            ).order_by("id")
        )

        if not movimientos:
            raise ValidationError(
                "La venta no tiene movimientos financieros."
            )

        efectivo = sum(
            (
                m.monto
                for m in movimientos
                if m.medio_pago
                == CajaMovimiento.MedioPago.EFECTIVO
            ),
            Decimal("0.00"),
        )

        resumen = CajaService.resumen_turno(
            turno
        )

        if efectivo > resumen["efectivo_esperado"]:
            raise ValidationError(
                "No hay suficiente efectivo en la caja "
                "para realizar la devolución."
            )

        detalle = (
            f"Devolución de venta #{venta.id}"
        )

        if observacion:
            detalle += (
                f" | {observacion.strip()}"
            )

        resultado = []

        for movimiento in movimientos:
            resultado.append(
                CajaMovimiento.objects.create(
                    turno=turno,
                    usuario=usuario,
                    tipo=CajaMovimiento.Tipo.DEVOLUCION,
                    medio_pago=movimiento.medio_pago,
                    monto=movimiento.monto,
                    referencia_venta=venta,
                    observacion=detalle,
                )
            )

        return resultado

    # ==========================================================
    # DEVOLUCIONES Y CAMBIOS
    # ==========================================================

    @staticmethod
    @transaction.atomic
    def registrar_movimientos_devolucion(
        devolucion,
        turno,
        usuario,
        pagos_adicionales=None,
        medio_reembolso="",
    ):
        """
        Registra únicamente el movimiento financiero de un cambio.

        - Si el cliente lleva una prenda más costosa:
          registra CAMBIO por el excedente cobrado.

        - Si lleva una prenda más barata y se autorizó reembolso:
          registra DEVOLUCION por el valor devuelto.

        - Si acepta no recibir dinero:
          no crea movimiento de caja.
        """

        pagos_adicionales = pagos_adicionales or {}

        turno = CajaService.obtener_turno_bloqueado(
            turno.id,
            sucursal=devolucion.sucursal,
        )

        CajaService.validar_operador_turno(
            turno,
            usuario,
        )

        if turno.sucursal_id != devolucion.sucursal_id:
            raise ValidationError(
                "El turno no pertenece a la sucursal de la devolución."
            )

        pagos_limpios = {
            medio: CajaService.monto_positivo(
                pagos_adicionales.get(medio, 0),
                f"El monto de {medio} es inválido.",
            )
            if pagos_adicionales.get(medio, 0)
            else Decimal("0.00")
            for medio in CajaService.MEDIOS_VENTA_PERMITIDOS
        }

        total_cobrado = sum(
            pagos_limpios.values(),
            Decimal("0.00"),
        )

        # Cliente debe pagar una diferencia.
        if devolucion.monto_cobrado > 0:
            if total_cobrado != devolucion.monto_cobrado:
                raise ValidationError(
                    "Los pagos no coinciden con el excedente del cambio."
                )

            for medio, monto in pagos_limpios.items():
                if monto <= 0:
                    continue

                CajaMovimiento.objects.create(
                    turno=turno,
                    usuario=usuario,
                    tipo=CajaMovimiento.Tipo.CAMBIO,
                    medio_pago=medio,
                    monto=monto,
                    referencia_venta=devolucion.venta,
                    referencia_devolucion=devolucion,
                    observacion=(
                        f"Cobro por cambio #{devolucion.id} "
                        f"de venta #{devolucion.venta_id}"
                    ),
                )

            CajaService.verificar_retiro_automatico(turno)

        elif total_cobrado > 0:
            raise ValidationError(
                "No debe registrar pagos adicionales en este cambio."
            )

        # Cliente recibe una devolución de dinero.
        if devolucion.monto_reembolsado > 0:
            if medio_reembolso not in CajaService.MEDIOS_VENTA_PERMITIDOS:
                raise ValidationError(
                    "Debe seleccionar un medio válido para el reembolso."
                )

            if medio_reembolso == CajaMovimiento.MedioPago.EFECTIVO:
                resumen = CajaService.resumen_turno(turno)

                if (
                    devolucion.monto_reembolsado
                    > resumen["efectivo_esperado"]
                ):
                    raise ValidationError(
                        "No hay suficiente efectivo en caja "
                        "para realizar el reembolso."
                    )

            CajaMovimiento.objects.create(
                turno=turno,
                usuario=usuario,
                tipo=CajaMovimiento.Tipo.DEVOLUCION,
                medio_pago=medio_reembolso,
                monto=devolucion.monto_reembolsado,
                referencia_venta=devolucion.venta,
                referencia_devolucion=devolucion,
                observacion=(
                    f"Reembolso de devolución #{devolucion.id} "
                    f"de venta #{devolucion.venta_id}"
                ),
            )

    # ==========================================================
    # INTEGRIDAD
    # ==========================================================

    @staticmethod
    def verificar_integridad_turno(
        turno_id,
    ):
        movimientos = (
            CajaMovimiento.objects
            .filter(turno_id=turno_id)
            .order_by(
                "numero_secuencia",
                "id",
            )
        )

        errores = []
        hash_anterior = "GENESIS"
        secuencia = 1

        for movimiento in movimientos:

            if movimiento.numero_secuencia != secuencia:
                errores.append(
                    {
                        "movimiento_id": movimiento.id,
                        "error": "Secuencia inválida.",
                    }
                )

            partes_hash = [
                hash_anterior,
                str(movimiento.turno_id),
                str(movimiento.numero_secuencia),
                str(movimiento.sucursal_id),
                str(movimiento.caja_id),
                str(movimiento.usuario_id),
                movimiento.tipo,
                movimiento.medio_pago or "",
                str(movimiento.monto),
                str(movimiento.referencia_venta_id or ""),
                movimiento.observacion,
                movimiento.creado_en.isoformat(),
            ]

            if movimiento.referencia_devolucion_id:
                partes_hash.insert(
                    -2,
                    str(movimiento.referencia_devolucion_id),
                )

            cadena = "|".join(partes_hash)

            calculado = hashlib.sha256(
                cadena.encode("utf-8")
            ).hexdigest()

            if not hmac.compare_digest(
                movimiento.hash_integridad,
                calculado,
            ):
                errores.append(
                    {
                        "movimiento_id": movimiento.id,
                        "error": "Hash inválido.",
                    }
                )

            if (
                movimiento.hash_anterior
                != hash_anterior
            ):
                errores.append(
                    {
                        "movimiento_id": movimiento.id,
                        "error": "Cadena de hashes rota.",
                    }
                )

            hash_anterior = (
                movimiento.hash_integridad
            )

            secuencia += 1

        return {
            "valido": not errores,
            "turno_id": turno_id,
            "movimientos_verificados": (
                secuencia - 1
            ),
            "errores": errores,
        }

    @staticmethod
    def verificar_integridad_boveda(
        boveda_id,
    ):
        movimientos = (
            BovedaMovimiento.objects
            .filter(boveda_id=boveda_id)
            .order_by(
                "numero_secuencia",
                "id",
            )
        )

        errores = []
        hash_anterior = "GENESIS"
        secuencia = 1

        for movimiento in movimientos:

            if movimiento.numero_secuencia != secuencia:
                errores.append(
                    {
                        "movimiento_id": movimiento.id,
                        "error": "Secuencia inválida.",
                    }
                )

            cadena = "|".join(
                [
                    hash_anterior,
                    str(movimiento.boveda_id),
                    str(movimiento.numero_secuencia),
                    str(movimiento.turno_id or ""),
                    str(
                        movimiento.movimiento_caja_id
                        or ""
                    ),
                    str(movimiento.usuario_id),
                    movimiento.tipo,
                    str(movimiento.monto),
                    movimiento.observacion,
                    movimiento.creado_en.isoformat(),
                ]
            )

            calculado = hashlib.sha256(
                cadena.encode("utf-8")
            ).hexdigest()

            if not hmac.compare_digest(
                movimiento.hash_integridad,
                calculado,
            ):
                errores.append(
                    {
                        "movimiento_id": movimiento.id,
                        "error": "Hash inválido.",
                    }
                )

            if (
                movimiento.hash_anterior
                != hash_anterior
            ):
                errores.append(
                    {
                        "movimiento_id": movimiento.id,
                        "error": "Cadena de hashes rota.",
                    }
                )

            hash_anterior = (
                movimiento.hash_integridad
            )

            secuencia += 1

        return {
            "valido": not errores,
            "boveda_id": boveda_id,
            "movimientos_verificados": (
                secuencia - 1
            ),
            "errores": errores,
        }

    # ==========================================================
    # MOVIMIENTOS RECIENTES
    # ==========================================================

    @staticmethod
    def ultimos_movimientos(
        turno,
        limite=30,
    ):
        return (
            CajaMovimiento.objects
            .filter(turno=turno)
            .select_related(
                "usuario",
                "referencia_venta",
            )
            .order_by(
                "-creado_en",
                "-id",
            )[:limite]
        )