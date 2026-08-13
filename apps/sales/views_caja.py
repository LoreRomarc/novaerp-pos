# apps/sales/views_caja.py
import json

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import TemplateView, View
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.core.serializers.json import DjangoJSONEncoder
from django.core.paginator import Paginator
from django.db import transaction


from apps.accounts.models import UserProfile
from apps.core.models import Sucursal
from apps.sales.mixins import CajaActivaRequiredMixin, SucursalIsolationMixin
from apps.sales.models import Caja
from apps.sales.models_caja_enterprise import ArqueoTurno, Boveda, CajaMovimiento, TurnoCaja
from apps.sales.permissions import RolePermissionMixin
from apps.sales.services.caja_service import CajaService


def _obtener_datos_request(request):
    if request.content_type and request.content_type.startswith("application/json"):
        try:
            datos = json.loads(request.body or "{}")
        except json.JSONDecodeError as error:
            raise ValidationError("El cuerpo de la solicitud no es JSON válido.") from error

        if not isinstance(datos, dict):
            raise ValidationError("El cuerpo de la solicitud debe ser un objeto JSON.")

        return datos

    return request.POST.dict()


def _respuesta_error(error, status=400):
    return JsonResponse(
        {
            "success": False,
            "error": str(error),
        },
        status=status,
    )


def _respuesta_movimiento(turno, movimiento):
    return JsonResponse(
        {
            "success": True,
            "movimiento": {
                "id": movimiento.id,
                "tipo": movimiento.tipo,
                "medio_pago": movimiento.medio_pago,
                "monto": movimiento.monto,
                "observacion": movimiento.observacion,
                "creado_en": movimiento.creado_en,
            },
            "resumen": CajaService.resumen_turno(turno),
        },
        encoder=DjangoJSONEncoder,
    )


class SeleccionarSucursalView(
    LoginRequiredMixin,
    View,
):
    def get(self, request):
        perfil = (
            UserProfile.objects
            .filter(user=request.user)
            .first()
        )

        if not perfil:
            raise PermissionDenied(
                "Su usuario no tiene un perfil configurado."
            )

        if perfil.role != UserProfile.Role.SUPER_ADMIN:
            return redirect("sales:abrir_caja")

        sucursales = (
            Sucursal.objects
            .filter(activa=True)
            .order_by("nombre")
        )

        return render(
            request,
            "sales/seleccionar_sucursal.html",
            {
                "sucursales": sucursales,
            },
        )

    def post(self, request):
        perfil = (
            UserProfile.objects
            .filter(user=request.user)
            .first()
        )

        if not perfil:
            raise PermissionDenied(
                "Su usuario no tiene un perfil configurado."
            )

        if perfil.role != UserProfile.Role.SUPER_ADMIN:
            raise PermissionDenied(
                "No tiene permiso para seleccionar sucursal."
            )

        sucursal_id = request.POST.get("sucursal_id")

        sucursal = (
            Sucursal.objects
            .filter(
                pk=sucursal_id,
                activa=True,
            )
            .first()
        )

        if not sucursal:
            return render(
                request,
                "sales/seleccionar_sucursal.html",
                {
                    "error": "Debe seleccionar una sucursal válida.",
                    "sucursales": (
                        Sucursal.objects
                        .filter(activa=True)
                        .order_by("nombre")
                    ),
                },
                status=400,
            )

        request.session["sucursal_id"] = sucursal.id
        request.session.modified = True

        return redirect("sales:abrir_caja")
    
class CajaDashboardView(
    LoginRequiredMixin,
    RolePermissionMixin,
    CajaActivaRequiredMixin,
    SucursalIsolationMixin,
    TemplateView,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO",
    ]

    template_name = "sales/caja/caja.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        turno = CajaService.obtener_turno_request(self.request)

        context["turno"] = turno
        context["arqueo_actual"] = None
        context["cierre_en_proceso"] = False
        context["puede_asignar_supervisor"] = False
        context["supervisores"] = []

        if not turno:
            return context

        arqueo_actual = (
            ArqueoTurno.objects.prefetch_related("denominaciones")
            .filter(
                turno=turno,
                estado=ArqueoTurno.Estado.REGISTRADO,
            )
            .order_by("-creado_en", "-id")
            .first()
        )

        context["resumen"] = CajaService.resumen_turno(turno)
        context["movimientos"] = CajaService.ultimos_movimientos(turno)
        context["arqueo_actual"] = arqueo_actual
        context["cierre_en_proceso"] = arqueo_actual is not None

        if self.get_user_role() not in {
            "SUPER_ADMIN",
            "ADMIN_SUCURSAL",
        }:
            return context

        context["puede_asignar_supervisor"] = True
        context["supervisores"] = (
            UserProfile.objects.select_related("user")
            .filter(
                user__is_active=True,
                role__in=[
                    UserProfile.Role.SUPER_ADMIN,
                    UserProfile.Role.ADMIN_SUCURSAL,
                    UserProfile.Role.SUPERVISOR,
                ],
            )
            .filter(
                Q(sucursal=turno.sucursal)
                | Q(role=UserProfile.Role.SUPER_ADMIN)
            )
            .exclude(user_id=turno.usuario_apertura_id)
            .order_by(
                "user__first_name",
                "user__last_name",
                "user__username",
            )
        )

        return context


class CajaIngresoView(
    LoginRequiredMixin,
    RolePermissionMixin,
    CajaActivaRequiredMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO",
    ]

    def post(self, request):
        try:
            datos = _obtener_datos_request(request)
            turno = CajaService.obtener_turno_request(request)

            movimiento = CajaService.registrar_movimiento(
                turno=turno,
                usuario=request.user,
                tipo=CajaMovimiento.Tipo.INGRESO,
                monto=datos.get("monto"),
                observacion=datos.get("motivo", ""),
                medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
            )

            return _respuesta_movimiento(turno, movimiento)

        except ValidationError as error:
            return _respuesta_error(error)

        except Exception as error:
            import traceback

            traceback.print_exc()

            return JsonResponse(
                {
                    "success": False,
                    "error": str(error),
                    "trace": traceback.format_exc(),
                },
                status=500,
            )


class CajaEgresoView(
    LoginRequiredMixin,
    RolePermissionMixin,
    CajaActivaRequiredMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO",
    ]

    def post(self, request):
        try:
            datos = _obtener_datos_request(request)
            turno = CajaService.obtener_turno_request(request)

            movimiento = CajaService.registrar_movimiento(
                turno=turno,
                usuario=request.user,
                tipo=CajaMovimiento.Tipo.EGRESO,
                monto=datos.get("monto"),
                observacion=datos.get("motivo", ""),
                medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
            )

            return _respuesta_movimiento(turno, movimiento)

        except ValidationError as error:
            return _respuesta_error(error)

        except Exception:
            return _respuesta_error(
                "No fue posible registrar el egreso.",
                status=500,
            )


class CajaRetiroView(
    LoginRequiredMixin,
    RolePermissionMixin,
    CajaActivaRequiredMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO",
    ]

    def post(self, request):
        try:
            datos = _obtener_datos_request(request)
            turno = CajaService.obtener_turno_request(request)

            movimiento = CajaService.registrar_movimiento(
                turno=turno,
                usuario=request.user,
                tipo=CajaMovimiento.Tipo.RETIRO_BOVEDA,
                monto=datos.get("monto"),
                observacion=datos.get("motivo", "Retiro a bóveda"),
                medio_pago=CajaMovimiento.MedioPago.EFECTIVO,
            )

            return _respuesta_movimiento(turno, movimiento)

        except ValidationError as error:
            return _respuesta_error(error)

        except Exception:
            return _respuesta_error(
                "No fue posible registrar el retiro a bóveda.",
                status=500,
            )

class CajaArqueoView(
    LoginRequiredMixin,
    RolePermissionMixin,
    CajaActivaRequiredMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO",
    ]

    def post(self, request):
        try:
            datos = _obtener_datos_request(request)
            turno = CajaService.obtener_turno_request(request)

            arqueo = CajaService.crear_arqueo(
                turno=turno,
                usuario=request.user,
                denominaciones=datos.get("denominaciones", {}),
                observacion=datos.get("observacion", ""),
            )

            return JsonResponse(
                {
                    "success": True,
                    "arqueo": {
                        "id": arqueo.id,
                        "monto_esperado": str(arqueo.monto_esperado),
                        "total_contado": str(arqueo.total_contado),
                        "diferencia": str(arqueo.diferencia),
                        "estado": arqueo.estado,
                        "estado_display": arqueo.get_estado_display(),
                        "creado_en": arqueo.creado_en.strftime(
                            "%d/%m/%Y %H:%M"
                        ),
                        "observacion": arqueo.observacion,
                        "denominaciones": [
                            {
                                "denominacion": str(item.denominacion),
                                "cantidad": item.cantidad,
                                "subtotal": str(item.subtotal),
                            }
                            for item in arqueo.denominaciones.order_by(
                                "-denominacion"
                            )
                        ],
                    },
                }
            )

        except ValidationError as error:
            return _respuesta_error(error)

        except Exception:
            return _respuesta_error(
                "No fue posible registrar el arqueo.",
                status=500,
            )


class CajaAsignarSupervisorView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
    ]

    def post(self, request):
        try:
            datos = _obtener_datos_request(request)
            turno = CajaService.obtener_turno_request(request)

            if not turno:
                raise ValidationError("No existe un turno activo en esta sesión.")

            supervisor_id = datos.get("supervisor_id")

            if not supervisor_id:
                raise ValidationError("Debe seleccionar un supervisor.")

            supervisor = get_user_model().objects.filter(
                pk=supervisor_id,
                is_active=True,
            ).first()

            if not supervisor:
                raise ValidationError("El supervisor seleccionado no existe.")

            turno = CajaService.asignar_supervisor(
                turno_id=turno.id,
                supervisor=supervisor,
            )

            return JsonResponse(
                {
                    "success": True,
                    "turno_id": turno.id,
                    "supervisor": {
                        "id": turno.usuario_supervisor_id,
                        "nombre": str(turno.usuario_supervisor),
                    },
                }
            )

        except ValidationError as error:
            return _respuesta_error(error)

        except Exception:
            return _respuesta_error(
                "No fue posible asignar el supervisor.",
                status=500,
            )

class CajaAsignarCajeroView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "SUPERVISOR",
    ]

    def post(self, request):
        try:
            datos = _obtener_datos_request(request)
            turno = CajaService.obtener_turno_request(request)

            if not turno:
                raise ValidationError("No existe un turno activo en esta sesión.")

            cajero_id = datos.get("cajero_id")

            if not cajero_id:
                raise ValidationError("Debe seleccionar un cajero.")

            perfil_cajero = (
                UserProfile.objects.select_related("user")
                .filter(
                    user_id=cajero_id,
                    user__is_active=True,
                    role=UserProfile.Role.CAJERO,
                    sucursal=turno.sucursal,
                )
                .first()
            )

            if not perfil_cajero:
                raise ValidationError(
                    "El cajero seleccionado no pertenece a la sucursal activa."
                )

            asignacion = CajaService.asignar_cajero(
                turno_id=turno.id,
                usuario_asignado=perfil_cajero.user,
                usuario_responsable=request.user,
            )

            return JsonResponse(
                {
                    "success": True,
                    "asignacion": {
                        "id": asignacion.id,
                        "usuario_id": asignacion.usuario_id,
                        "usuario": str(asignacion.usuario),
                    },
                }
            )

        except ValidationError as error:
            return _respuesta_error(error)

        except Exception:
            return _respuesta_error(
                "No fue posible asignar el cajero.",
                status=500,
            )


class CajaDesasignarCajeroView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "SUPERVISOR",
    ]

    def post(self, request, usuario_id):
        try:
            turno = CajaService.obtener_turno_request(request)

            if not turno:
                raise ValidationError("No existe un turno activo en esta sesión.")

            perfil_cajero = (
                UserProfile.objects.select_related("user")
                .filter(
                    user_id=usuario_id,
                    user__is_active=True,
                    role=UserProfile.Role.CAJERO,
                    sucursal=turno.sucursal,
                )
                .first()
            )

            if not perfil_cajero:
                raise ValidationError(
                    "El cajero seleccionado no pertenece a la sucursal activa."
                )

            CajaService.desasignar_cajero(
                turno_id=turno.id,
                usuario_asignado=perfil_cajero.user,
                usuario_responsable=request.user,
            )

            return JsonResponse({"success": True})

        except ValidationError as error:
            return _respuesta_error(error)

        except Exception:
            return _respuesta_error(
                "No fue posible desasignar el cajero.",
                status=500,
            )
        
class CajaAprobarArqueoView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "SUPERVISOR",
    ]

    def post(self, request, arqueo_id):
        try:
            datos = _obtener_datos_request(request)

            arqueo = (
                ArqueoTurno.objects.select_related("turno")
                .filter(
                    pk=arqueo_id,
                    turno__sucursal=self.get_sucursal(),
                )
                .first()
            )

            if not arqueo:
                raise ValidationError(
                    "El arqueo no existe o no pertenece a la sucursal activa."
                )

            arqueo = CajaService.aprobar_arqueo(
                arqueo_id=arqueo.id,
                usuario=request.user,
                observacion=datos.get("observacion", ""),
            )

            return JsonResponse(
                {
                    "success": True,
                    "arqueo": {
                        "id": arqueo.id,
                        "estado": arqueo.estado,
                        "aprobado_en": arqueo.aprobado_en,
                    },
                }
            )

        except ValidationError as error:
            return _respuesta_error(error)

        except Exception:
            return _respuesta_error(
                "No fue posible aprobar el arqueo.",
                status=500,
            )
        
class AbrirCajaView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO",
    ]

    @staticmethod
    def _obtener_supervisores(sucursal, usuario_apertura):
        return (
            UserProfile.objects
            .select_related("user")
            .filter(
                user__is_active=True,
                role__in=[
                    UserProfile.Role.SUPER_ADMIN,
                    UserProfile.Role.ADMIN_SUCURSAL,
                    UserProfile.Role.SUPERVISOR,
                ],
            )
            .filter(
                Q(sucursal=sucursal)
                | Q(role=UserProfile.Role.SUPER_ADMIN)
            )
            .exclude(user=usuario_apertura)
            .order_by(
                "user__first_name",
                "user__last_name",
                "user__username",
            )
        )

    def _contexto_apertura(
        self,
        sucursal,
        usuario,
        error=None,
        caja_seleccionada=None,
        supervisor_seleccionado=None,
        monto_inicial="0",
    ):
        perfil = getattr(usuario, "profile", None)

        supervisor_requerido = (
            not perfil
            or perfil.role != UserProfile.Role.SUPER_ADMIN
        )

        return {
            "error": error,
            "sucursal": sucursal,
            "cajas": (
                Caja.objects
                .filter(
                    sucursal=sucursal,
                    activa=True,
                )
                .order_by("codigo")
            ),
            "supervisor_requerido": supervisor_requerido,
            "supervisores": (
                self._obtener_supervisores(
                    sucursal=sucursal,
                    usuario_apertura=usuario,
                )
                if supervisor_requerido
                else []
            ),
            "caja_seleccionada": str(caja_seleccionada or ""),
            "supervisor_seleccionado": str(
                supervisor_seleccionado or ""
            ),
            "monto_inicial": monto_inicial or "0",
        }

    def get(self, request):
        perfil = (
            UserProfile.objects
            .filter(user=request.user)
            .first()
        )

        if (
            perfil
            and perfil.role == UserProfile.Role.SUPER_ADMIN
            and not request.session.get("sucursal_id")
        ):
            return redirect("sales:seleccionar_sucursal")

        sucursal = self.get_sucursal()

        turno = CajaService.obtener_turno_activo_usuario(
            sucursal=sucursal,
            usuario=request.user,
        )

        if turno:
            request.session["turno_id"] = turno.id
            request.session["caja_id"] = turno.caja_id
            request.session.modified = True

            return redirect("sales:caja_dashboard")

        request.session.pop("turno_id", None)
        request.session.pop("caja_id", None)
        request.session.modified = True

        return render(
            request,
            "sales/abrir_caja.html",
            self._contexto_apertura(
                sucursal=sucursal,
                usuario=request.user,
            ),
        )

    def post(self, request):
        perfil = (
            UserProfile.objects
            .filter(user=request.user)
            .first()
        )

        if (
            perfil
            and perfil.role == UserProfile.Role.SUPER_ADMIN
            and not request.session.get("sucursal_id")
        ):
            return redirect("sales:seleccionar_sucursal")

        sucursal = self.get_sucursal()

        caja_id = request.POST.get("caja_id")
        supervisor_id = request.POST.get("supervisor_id")
        monto_inicial = request.POST.get("monto_inicial", "0")

        supervisor_requerido = (
            not perfil
            or perfil.role != UserProfile.Role.SUPER_ADMIN
        )

        try:
            supervisor = None

            if supervisor_requerido:
                if not supervisor_id:
                    raise ValidationError(
                        "Debe seleccionar el supervisor responsable "
                        "del turno."
                    )

                supervisor = (
                    get_user_model()
                    .objects
                    .filter(
                        pk=supervisor_id,
                        is_active=True,
                    )
                    .first()
                )

                if not supervisor:
                    raise ValidationError(
                        "El supervisor seleccionado no existe "
                        "o está inactivo."
                    )

            with transaction.atomic():
                turno = CajaService.abrir_caja(
                    sucursal=sucursal,
                    usuario=request.user,
                    monto_inicial=monto_inicial,
                    caja_id=caja_id,
                )

                if supervisor:
                    CajaService.asignar_supervisor(
                        turno_id=turno.id,
                        supervisor=supervisor,
                    )

            request.session["turno_id"] = turno.id
            request.session["caja_id"] = turno.caja_id
            request.session.modified = True

            messages.success(
                request,
                (
                    "Caja abierta correctamente."
                    if supervisor_requerido
                    else (
                        "Caja abierta correctamente. Como Super "
                        "Administrador, puede supervisar y aprobar "
                        "el arqueo de este turno."
                    )
                ),
            )

            return redirect("sales:caja_dashboard")

        except ValidationError as error:
            return render(
                request,
                "sales/abrir_caja.html",
                self._contexto_apertura(
                    sucursal=sucursal,
                    usuario=request.user,
                    error=str(error),
                    caja_seleccionada=caja_id,
                    supervisor_seleccionado=supervisor_id,
                    monto_inicial=monto_inicial,
                ),
                status=400,
            )


class CerrarCajaView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "CAJERO",
    ]

    def post(self, request):
        turno = CajaService.obtener_turno_request(request)

        if not turno:
            messages.error(
                request,
                "No existe un turno activo.",
            )
            return redirect("sales:abrir_caja")

        try:
            CajaService.cerrar_caja(
                sucursal=self.get_sucursal(),
                usuario=request.user,
                turno_id=turno.id,
            )

            request.session.pop("turno_id", None)
            request.session.pop("caja_id", None)
            request.session.modified = True

            messages.success(
                request,
                "Caja cerrada correctamente. El arqueo queda pendiente de aprobación.",
            )

            return redirect("sales:abrir_caja")

        except ValidationError as error:
            messages.error(request, str(error))
            return redirect("sales:caja_dashboard")


class CajaHistorialCierresView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    TemplateView,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "SUPERVISOR",
    ]

    template_name = "sales/caja/historial_cierres.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sucursal = self.get_sucursal()

        inicio = self.request.GET.get("inicio", "").strip()
        fin = self.request.GET.get("fin", "").strip()
        caja_id = self.request.GET.get("caja", "").strip()
        estado = self.request.GET.get("estado", "").strip()

        estados_cerrados = [
            TurnoCaja.Estado.CERRADO_CAJERO,
            TurnoCaja.Estado.CERRADO_SUPERVISOR,
            TurnoCaja.Estado.AUDITADO,
        ]

        turnos = (
            TurnoCaja.objects.select_related(
                "caja",
                "usuario_apertura",
                "usuario_supervisor",
                "cerrado_por",
                "auditado_por",
            )
            .prefetch_related(
                "arqueos",
                "arqueos__denominaciones",
                "arqueos__realizado_por",
                "arqueos__aprobado_por",
            )
            .filter(
                sucursal=sucursal,
                estado__in=estados_cerrados,
            )
            .order_by("-cerrado_en", "-id")
        )

        if inicio:
            turnos = turnos.filter(cerrado_en__date__gte=inicio)

        if fin:
            turnos = turnos.filter(cerrado_en__date__lte=fin)

        if caja_id:
            turnos = turnos.filter(caja_id=caja_id)

        if estado:
            turnos = turnos.filter(estado=estado)

        paginador = Paginator(turnos, 25)
        pagina = paginador.get_page(
            self.request.GET.get("pagina")
        )

        context.update(
            {
                "turnos": pagina,
                "cajas": Caja.objects.filter(
                    sucursal=sucursal,
                ).order_by("codigo"),
                "inicio": inicio,
                "fin": fin,
                "caja_id": caja_id,
                "estado": estado,
            }
        )

        return context
    
class CajaVerificarIntegridadView(
    LoginRequiredMixin,
    RolePermissionMixin,
    SucursalIsolationMixin,
    View,
):
    allowed_roles = [
        "SUPER_ADMIN",
        "ADMIN_SUCURSAL",
        "SUPERVISOR",
    ]

    def get(self, request, turno_id):
        turno = (
            TurnoCaja.objects.select_related("sucursal")
            .filter(
                pk=turno_id,
                sucursal=self.get_sucursal(),
            )
            .first()
        )

        if not turno:
            return _respuesta_error(
                "El turno no existe o no pertenece a la sucursal activa.",
                status=404,
            )

        resultado_turno = CajaService.verificar_integridad_turno(
            turno_id=turno.id,
        )

        boveda = Boveda.objects.filter(
            sucursal=turno.sucursal,
        ).first()

        resultado_boveda = (
            CajaService.verificar_integridad_boveda(
                boveda_id=boveda.id,
            )
            if boveda
            else {
                "valido": True,
                "boveda_id": None,
                "movimientos_verificados": 0,
                "errores": [],
            }
        )

        return JsonResponse(
            {
                "success": (
                    resultado_turno["valido"]
                    and resultado_boveda["valido"]
                ),
                "turno": resultado_turno,
                "boveda": resultado_boveda,
            }
        )