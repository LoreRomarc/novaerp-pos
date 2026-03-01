# apps/reports/views.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from apps.sales.models import Venta
from django.db.models import Sum
from datetime import date


@login_required
def reporte_ventas(request):

    usuario = request.user
    perfil = usuario.userprofile

    if perfil.role not in ['SUPER_ADMIN', 'ADMIN_SUCURSAL']:
        return render(request, 'reports/sin_permiso.html')

    hoy = date.today()

    if perfil.role == 'SUPER_ADMIN':
        ventas = Venta.objects.all()
    else:
        ventas = Venta.objects.filter(sucursal=perfil.sucursal)

    ventas_hoy = ventas.filter(fecha__date=hoy)

    total_general = ventas.aggregate(total=Sum('total'))['total'] or 0
    total_hoy = ventas_hoy.aggregate(total=Sum('total'))['total'] or 0

    ventas_pendientes = ventas.filter(estado_pago='PENDIENTE')


    context = {
        'ventas': ventas.order_by('-fecha')[:20],
        'total_general': total_general,
        'total_hoy': total_hoy,
        'ventas_pendientes': ventas_pendientes,
    }

    return render(request, 'reports/reporte_ventas.html', context)
