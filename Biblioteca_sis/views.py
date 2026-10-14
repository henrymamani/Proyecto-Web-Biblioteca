import csv
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from catalogo.forms import LibroForm
from catalogo.models import Libro
from prestamos.models import Multa, Notificacion, Prestamo, Reserva
from prestamos.services import (
    ReglaPrestamoError,
    actualizar_sistema,
    autorizar_reserva,
    registrar_devolucion,
)
from usuarios.forms import RegistroEstudianteForm


def es_administrador(usuario):
    return usuario.is_authenticated and (
        usuario.is_staff or usuario.is_superuser or usuario.tipo_usuario == 'administrador'
    )


administrador_requerido = user_passes_test(es_administrador)


def inicio(request):
    if request.user.is_authenticated:
        return redirect('panel')
    consulta = request.GET.get('q', '').strip()
    libros = Libro.objects.filter(stock__gte=0).order_by('titulo')
    if consulta:
        libros = libros.filter(titulo__icontains=consulta) | libros.filter(autor__icontains=consulta)
    return render(request, 'inicio.html', {
        'libros': libros[:6],
        'consulta': consulta,
        'total_libros': Libro.objects.count(),
        'total_disponibles': Libro.objects.filter(stock__gt=0).count(),
    })


def registro(request):
    if request.user.is_authenticated:
        return redirect('panel')
    form = RegistroEstudianteForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        login(request, usuario)
        messages.success(request, 'Tu cuenta de estudiante fue creada correctamente.')
        return redirect('panel')
    return render(request, 'registration/registro.html', {'form': form})


def salir(request):
    """Cierra la sesion actual y vuelve al acceso publico."""
    logout(request)
    messages.info(request, 'Sesion cerrada.')
    return redirect('inicio')


@login_required
def panel(request):
    actualizar_sistema()
    if es_administrador(request.user):
        prestamos = Prestamo.objects.select_related('usuario', 'libro').order_by('-fecha_prestamo')
        return render(request, 'panel_admin.html', {
            'prestamos_recientes': prestamos[:6],
            'total_titulos': Libro.objects.count(),
            'total_ejemplares': Libro.objects.aggregate(total=Sum('stock'))['total'] or 0,
            'prestamos_activos': prestamos.filter(estado='activo').count(),
            'prestamos_vencidos': prestamos.filter(estado='vencido').count(),
            'multas_pendientes': Multa.objects.filter(pagada=False).aggregate(total=Sum('monto'))['total'] or 0,
            'categorias': Libro.objects.values('categoria').annotate(total=Count('id')).order_by('-total')[:5],
            'notificaciones': Notificacion.objects.filter(leida=False).count(),
        })

    prestamos = Prestamo.objects.filter(usuario=request.user).select_related('libro').order_by('-fecha_prestamo')
    return render(request, 'panel_usuario.html', {
        'prestamos': prestamos.filter(estado__in=['activo', 'vencido']),
        'historial': prestamos.filter(estado='devuelto')[:5],
        'reservas': Reserva.objects.filter(usuario=request.user, estado='pendiente').select_related('libro'),
        'notificaciones': Notificacion.objects.filter(usuario=request.user, leida=False)[:4],
        'limite_restante': max(0, request.user.limite_prestamos - prestamos.filter(estado__in=['activo', 'vencido']).count()),
    })


def catalogo(request):
    consulta = request.GET.get('q', '').strip()
    categoria = request.GET.get('categoria', '').strip()
    libros = Libro.objects.all().order_by('titulo')
    if consulta:
        libros = libros.filter(titulo__icontains=consulta) | libros.filter(autor__icontains=consulta) | libros.filter(categoria__icontains=consulta)
    if categoria:
        libros = libros.filter(categoria=categoria)
    return render(request, 'catalogo.html', {
        'libros': libros,
        'consulta': consulta,
        'categoria_actual': categoria,
        'categorias': Libro.objects.values_list('categoria', flat=True).distinct().order_by('categoria'),
    })


@administrador_requerido
def administrar_libros(request, libro_id=None):
    libro = get_object_or_404(Libro, pk=libro_id) if libro_id else None
    form = LibroForm(request.POST or None, instance=libro)
    if request.method == 'POST' and form.is_valid():
        item = form.save()
        messages.success(request, f'El libro {item.titulo} fue guardado.')
        return redirect('administrar_libros')
    return render(request, 'administrar_libros.html', {
        'form': form,
        'libro_editando': libro,
        'libros': Libro.objects.all().order_by('titulo'),
    })


@administrador_requerido
def administrar_prestamos(request):
    actualizar_sistema()
    return render(request, 'administrar_prestamos.html', {
        'prestamos': Prestamo.objects.select_related('usuario', 'libro').order_by('-fecha_prestamo'),
    })


@administrador_requerido
def devolver_prestamo(request, prestamo_id):
    if request.method != 'POST':
        return HttpResponseForbidden('Accion no permitida.')
    prestamo = get_object_or_404(Prestamo, pk=prestamo_id)
    try:
        retraso = registrar_devolucion(prestamo)
        mensaje = 'Devolucion registrada sin multa.' if not retraso else f'Devolucion registrada con {retraso} dia(s) de retraso.'
        messages.success(request, mensaje)
    except ReglaPrestamoError as error:
        messages.error(request, str(error))
    return redirect('administrar_prestamos')


@login_required
def mis_prestamos(request):
    actualizar_sistema()
    prestamos = Prestamo.objects.filter(usuario=request.user).select_related('libro').order_by('-fecha_prestamo')
    multas = Multa.objects.filter(prestamo__usuario=request.user, pagada=False).select_related('prestamo__libro')
    return render(request, 'mis_prestamos.html', {
        'prestamos': prestamos,
        'multas': multas,
        'multa_actual': multas.aggregate(total=Sum('monto'))['total'] or Decimal('0.00'),
    })


@login_required
def crear_reserva(request, libro_id):
    if request.method != 'POST':
        return HttpResponseForbidden('Accion no permitida.')
    if es_administrador(request.user):
        messages.error(request, 'Las reservas estan disponibles para estudiantes y docentes.')
        return redirect('catalogo')
    libro = get_object_or_404(Libro, pk=libro_id)
    if Reserva.objects.filter(usuario=request.user, libro=libro, estado='pendiente').exists():
        messages.info(request, 'Ya tienes una reserva pendiente para este libro.')
    else:
        Reserva.objects.create(usuario=request.user, libro=libro)
        messages.success(request, 'Solicitud enviada. La biblioteca debe autorizarla antes de registrar el prestamo.')
    return redirect('catalogo')


@login_required
def reservas(request):
    if es_administrador(request.user):
        reservas_lista = Reserva.objects.select_related('usuario', 'libro').order_by('estado', '-fecha_reserva')
        return render(request, 'reservas_admin.html', {'reservas': reservas_lista})
    return render(request, 'reservas.html', {
        'reservas': Reserva.objects.filter(usuario=request.user).select_related('libro').order_by('-fecha_reserva')
    })


@administrador_requerido
def actualizar_reserva(request, reserva_id, accion):
    if request.method != 'POST' or accion not in ('autorizar', 'rechazar'):
        return HttpResponseForbidden('Accion no permitida.')
    reserva = get_object_or_404(Reserva, pk=reserva_id)
    if reserva.estado != 'pendiente':
        messages.info(request, 'Esta solicitud ya fue procesada.')
    elif accion == 'autorizar':
        try:
            prestamo = autorizar_reserva(reserva)
            messages.success(
                request,
                f'Solicitud autorizada. Prestamo registrado hasta el {prestamo.fecha_limite:%d/%m/%Y}.',
            )
        except ReglaPrestamoError as error:
            messages.error(request, f'No se pudo autorizar la solicitud: {error}')
    else:
        reserva.estado = 'rechazada'
        reserva.save(update_fields=['estado'])
        messages.success(request, 'Solicitud rechazada.')
    return redirect('reservas')


@login_required
def notificaciones(request):
    actualizar_sistema()
    if request.method == 'POST':
        Notificacion.objects.filter(usuario=request.user, leida=False).update(leida=True)
        messages.success(request, 'Las notificaciones fueron marcadas como leidas.')
        return redirect('notificaciones')
    return render(request, 'notificaciones.html', {
        'notificaciones': Notificacion.objects.filter(usuario=request.user)
    })


@administrador_requerido
def reportes(request):
    actualizar_sistema()
    fecha_inicio, fecha_fin, error_fechas = _rango_fechas(request)
    prestamos = Prestamo.objects.select_related('usuario', 'libro').order_by('-fecha_prestamo')
    if fecha_inicio:
        prestamos = prestamos.filter(fecha_prestamo__gte=fecha_inicio)
    if fecha_fin:
        prestamos = prestamos.filter(fecha_prestamo__lte=fecha_fin)

    total_prestamos = prestamos.count()
    total_devueltos = prestamos.filter(estado='devuelto').count()
    total_vencidos = prestamos.filter(estado='vencido').count()
    tasa_retorno = round((total_devueltos / total_prestamos * 100), 1) if total_prestamos else 0
    tasa_vencimiento = round((total_vencidos / total_prestamos * 100), 1) if total_prestamos else 0
    libros_populares = list(
        prestamos.values('libro__titulo', 'libro__autor')
        .annotate(total=Count('id'))
        .order_by('-total', 'libro__titulo')[:8]
    )
    for libro in libros_populares:
        libro['porcentaje'] = round((libro['total'] / total_prestamos * 100), 1) if total_prestamos else 0

    perfiles = list(
        prestamos.values('usuario__tipo_usuario')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    for perfil in perfiles:
        perfil['porcentaje'] = round((perfil['total'] / total_prestamos * 100), 1) if total_prestamos else 0

    multas_usuarios = list(
        Multa.objects.filter(pagada=False)
        .values('prestamo__usuario__first_name', 'prestamo__usuario__last_name', 'prestamo__usuario__username', 'prestamo__usuario__tipo_usuario')
        .annotate(multa_actual=Sum('monto'), prestamos_con_multa=Count('id'))
        .order_by('-multa_actual')
    )
    total_multas_actuales = sum((item['multa_actual'] for item in multas_usuarios), Decimal('0.00'))
    for item in multas_usuarios:
        item['nombre'] = ' '.join(filter(None, [item['prestamo__usuario__first_name'], item['prestamo__usuario__last_name']])) or item['prestamo__usuario__username']

    vista = request.GET.get('vista', 'resumen')
    if vista not in {'resumen', 'prestamos', 'libros', 'multas'}:
        vista = 'resumen'

    return render(request, 'reportes.html', {
        'vista': vista,
        'fecha_inicio': fecha_inicio.isoformat() if fecha_inicio else '',
        'fecha_fin': fecha_fin.isoformat() if fecha_fin else '',
        'error_fechas': error_fechas,
        'total_prestamos': total_prestamos,
        'total_devueltos': total_devueltos,
        'total_pendientes': total_prestamos - total_devueltos,
        'total_vencidos': total_vencidos,
        'tasa_retorno': tasa_retorno,
        'tasa_vencimiento': tasa_vencimiento,
        'libros_populares': libros_populares,
        'perfiles': perfiles,
        'multas_usuarios': multas_usuarios,
        'total_multas_actuales': total_multas_actuales,
        'prestamos_detalle': prestamos[:100],
    })


@administrador_requerido
def exportar_reporte_prestamos(request):
    actualizar_sistema()
    fecha_inicio, fecha_fin, _ = _rango_fechas(request)
    respuesta = HttpResponse(content_type='text/csv; charset=utf-8')
    sufijo = f'_{fecha_inicio:%Y%m%d}' if fecha_inicio else ''
    sufijo += f'_{fecha_fin:%Y%m%d}' if fecha_fin else ''
    respuesta['Content-Disposition'] = f'attachment; filename="reporte_prestamos{sufijo}.csv"'
    respuesta.write('\ufeff')
    escritor = csv.writer(respuesta)
    escritor.writerow(['REPORTE DE PRESTAMOS'])
    escritor.writerow(['Desde', fecha_inicio or 'Inicio de registros', 'Hasta', fecha_fin or 'Hoy'])
    escritor.writerow([])
    escritor.writerow(['DETALLE DE PRESTAMOS'])
    escritor.writerow(['Usuario', 'Tipo', 'Libro', 'Autor', 'Fecha prestamo', 'Fecha limite', 'Devolucion', 'Estado', 'Multa actual'])
    prestamos = Prestamo.objects.select_related('usuario', 'libro').order_by('-fecha_prestamo')
    if fecha_inicio:
        prestamos = prestamos.filter(fecha_prestamo__gte=fecha_inicio)
    if fecha_fin:
        prestamos = prestamos.filter(fecha_prestamo__lte=fecha_fin)
    for prestamo in prestamos:
        multa = getattr(prestamo, 'multa', None)
        escritor.writerow([
            prestamo.usuario.get_full_name() or prestamo.usuario.username,
            prestamo.usuario.tipo_usuario,
            prestamo.libro.titulo,
            prestamo.libro.autor,
            prestamo.fecha_prestamo,
            prestamo.fecha_limite,
            prestamo.fecha_devolucion or '',
            prestamo.estado,
            multa.monto if multa and not multa.pagada else '0.00',
        ])
    escritor.writerow([])
    escritor.writerow(['LIBROS MAS PRESTADOS'])
    escritor.writerow(['Libro', 'Prestamos', 'Porcentaje'])
    total = prestamos.count()
    populares = prestamos.values('libro__titulo').annotate(total=Count('id')).order_by('-total', 'libro__titulo')[:10]
    for item in populares:
        escritor.writerow([item['libro__titulo'], item['total'], f"{round(item['total'] / total * 100, 1) if total else 0}%"])
    return respuesta


def _rango_fechas(request):
    """Obtiene un intervalo valido para filtrar los informes por fecha de prestamo."""
    inicio_raw = request.GET.get('fecha_inicio', '').strip()
    fin_raw = request.GET.get('fecha_fin', '').strip()
    try:
        inicio = datetime.strptime(inicio_raw, '%Y-%m-%d').date() if inicio_raw else None
        fin = datetime.strptime(fin_raw, '%Y-%m-%d').date() if fin_raw else None
    except ValueError:
        return None, None, 'Ingresa las fechas con el formato correcto.'
    if inicio and fin and inicio > fin:
        return None, None, 'La fecha inicial no puede ser posterior a la fecha final.'
    return inicio, fin, ''
