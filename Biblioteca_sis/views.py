import csv
from collections import Counter
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import IntegrityError
from django.db.models import Avg, Count, Q, Sum
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from catalogo.forms import EtiquetaForm, LibroForm, ResenaForm
from catalogo.models import Etiqueta, Libro, Resena
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


NOMBRES_MESES = (
    'Ene', 'Feb', 'Mar', 'Abr', 'May', 'Jun',
    'Jul', 'Ago', 'Sep', 'Oct', 'Nov', 'Dic',
)


def _filtrar_libros_por_consulta(libros, consulta):
    if not consulta:
        return libros
    return libros.filter(
        Q(titulo__icontains=consulta)
        | Q(autor__icontains=consulta)
        | Q(isbn__icontains=consulta)
        | Q(editorial__icontains=consulta)
        | Q(descripcion__icontains=consulta)
        | Q(etiquetas__nombre__icontains=consulta)
    ).distinct()


def inicio(request):
    if request.user.is_authenticated:
        return redirect('panel')
    consulta = request.GET.get('q', '').strip()
    libros = _filtrar_libros_por_consulta(
        Libro.objects.filter(stock__gte=0).prefetch_related('etiquetas'),
        consulta,
    ).order_by('titulo')
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
            'etiquetas': Etiqueta.objects.annotate(total=Count('libros')).order_by('-total', 'nombre')[:5],
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
    etiquetas_activas = [
        int(etiqueta_id)
        for etiqueta_id in request.GET.getlist('etiquetas')
        if etiqueta_id.isdigit()
    ]
    orden = request.GET.get('orden', 'titulo')
    ordenes = {
        'titulo': ('titulo', 'autor'),
        'autor': ('autor', 'titulo'),
        'recientes': ('-creado_en', 'titulo'),
        'disponibilidad': ('-stock', 'titulo'),
    }
    if orden not in ordenes:
        orden = 'titulo'

    libros = _filtrar_libros_por_consulta(
        Libro.objects.all().prefetch_related('etiquetas'),
        consulta,
    )
    if etiquetas_activas:
        libros = libros.filter(etiquetas__id__in=etiquetas_activas).distinct()
    libros = libros.order_by(*ordenes[orden])
    return render(request, 'catalogo.html', {
        'libros': libros,
        'consulta': consulta,
        'etiquetas': Etiqueta.objects.annotate(total=Count('libros')).order_by('nombre'),
        'etiquetas_activas': etiquetas_activas,
        'orden': orden,
    })


def detalle_libro(request, libro_id):
    libro = get_object_or_404(
        Libro.objects.prefetch_related('etiquetas', 'resenas__usuario'),
        pk=libro_id,
    )
    resenas = libro.resenas.select_related('usuario').all()
    resumen_calificaciones = resenas.aggregate(promedio=Avg('calificacion'), total=Count('id'))
    resena_usuario = None
    if request.user.is_authenticated:
        resena_usuario = resenas.filter(usuario=request.user).first()

    return render(request, 'detalle_libro.html', {
        'libro': libro,
        'resenas': resenas,
        'promedio_calificacion': resumen_calificaciones['promedio'],
        'total_calificaciones': resumen_calificaciones['total'],
        'resena_usuario': resena_usuario,
        'form_resena': ResenaForm(),
    })


@login_required
def crear_resena(request, libro_id):
    if request.method != 'POST':
        return HttpResponseForbidden('Accion no permitida.')

    libro = get_object_or_404(Libro, pk=libro_id)
    if Resena.objects.filter(libro=libro, usuario=request.user).exists():
        messages.info(request, 'Ya registraste una calificacion y comentario para este libro.')
        return redirect('detalle_libro', libro_id=libro.id)

    form = ResenaForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Completa una calificacion y un comentario valido antes de publicarlo.')
        return redirect('detalle_libro', libro_id=libro.id)

    try:
        Resena.objects.create(
            libro=libro,
            usuario=request.user,
            calificacion=form.cleaned_data['calificacion'],
            comentario=form.cleaned_data['comentario'],
        )
    except IntegrityError:
        messages.info(request, 'Ya registraste una calificacion y comentario para este libro.')
    else:
        messages.success(request, 'Tu calificacion y comentario fueron publicados.')
    return redirect('detalle_libro', libro_id=libro.id)


@administrador_requerido
def eliminar_resena(request, resena_id):
    if request.method != 'POST':
        return HttpResponseForbidden('Accion no permitida.')
    resena = get_object_or_404(Resena, pk=resena_id)
    libro_id = resena.libro_id
    resena.delete()
    messages.success(request, 'El comentario fue eliminado del catalogo.')
    return redirect('detalle_libro', libro_id=libro_id)


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
        'libros': Libro.objects.prefetch_related('etiquetas').order_by('titulo'),
    })


@administrador_requerido
def administrar_etiquetas(request):
    form = EtiquetaForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        etiqueta = form.save()
        messages.success(request, f'La etiqueta {etiqueta.nombre} fue creada.')
        return redirect('administrar_etiquetas')
    return render(request, 'administrar_etiquetas.html', {
        'form': form,
        'etiquetas': Etiqueta.objects.annotate(total=Count('libros')).order_by('nombre'),
    })


@administrador_requerido
def eliminar_etiqueta(request, etiqueta_id):
    if request.method != 'POST':
        return HttpResponseForbidden('Accion no permitida.')
    etiqueta = get_object_or_404(Etiqueta, pk=etiqueta_id)
    nombre = etiqueta.nombre
    etiqueta.delete()
    messages.success(request, f'La etiqueta {nombre} fue eliminada.')
    return redirect('administrar_etiquetas')


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
    total_activos = prestamos.filter(estado='activo').count()
    total_vencidos = prestamos.filter(estado='vencido').count()
    libros_populares = list(
        prestamos.values('libro__titulo', 'libro__autor')
        .annotate(total=Count('id'))
        .order_by('-total', 'libro__titulo')[:8]
    )
    max_prestamos_libro = max((libro['total'] for libro in libros_populares), default=1)
    for libro in libros_populares:
        libro['barra'] = round(libro['total'] / max_prestamos_libro * 100)

    perfiles = list(
        prestamos.values('usuario__tipo_usuario')
        .annotate(total=Count('id'))
        .order_by('-total')
    )
    max_prestamos_perfil = max((perfil['total'] for perfil in perfiles), default=1)
    for perfil in perfiles:
        perfil['barra'] = round(perfil['total'] / max_prestamos_perfil * 100)

    estados_prestamo = [
        {'nombre': 'Activos', 'total': total_activos, 'clase': 'chart-blue'},
        {'nombre': 'Devueltos', 'total': total_devueltos, 'clase': 'chart-green'},
        {'nombre': 'Vencidos', 'total': total_vencidos, 'clase': 'chart-red'},
    ]
    max_estado = max((estado['total'] for estado in estados_prestamo), default=1)
    for estado in estados_prestamo:
        estado['barra'] = round(estado['total'] / max_estado * 100) if max_estado else 0

    conteo_mensual = Counter(
        (prestamo.fecha_prestamo.year, prestamo.fecha_prestamo.month)
        for prestamo in prestamos
    )
    prestamos_por_mes = [
        {
            'etiqueta': f'{NOMBRES_MESES[mes - 1]} {str(anio)[-2:]}',
            'total': total,
        }
        for (anio, mes), total in sorted(conteo_mensual.items())[-8:]
    ]
    max_mensual = max((item['total'] for item in prestamos_por_mes), default=1)
    for item in prestamos_por_mes:
        item['barra'] = round(item['total'] / max_mensual * 100)

    etiquetas_populares = list(
        Etiqueta.objects.annotate(total=Count('libros')).filter(total__gt=0).order_by('-total', 'nombre')[:8]
    )
    max_etiquetas = max((etiqueta.total for etiqueta in etiquetas_populares), default=1)
    for etiqueta in etiquetas_populares:
        etiqueta.barra = round(etiqueta.total / max_etiquetas * 100)

    resumen_resenas = Resena.objects.aggregate(
        promedio=Avg('calificacion'),
        total=Count('id'),
    )
    calificaciones = list(
        Resena.objects.values('calificacion').annotate(total=Count('id')).order_by('calificacion')
    )
    calificaciones_por_valor = {item['calificacion']: item['total'] for item in calificaciones}
    distribucion_calificaciones = [
        {'valor': valor, 'total': calificaciones_por_valor.get(valor, 0)}
        for valor in range(5, 0, -1)
    ]
    max_calificaciones = max((item['total'] for item in distribucion_calificaciones), default=1)
    for item in distribucion_calificaciones:
        item['barra'] = round(item['total'] / max_calificaciones * 100) if max_calificaciones else 0

    multas_usuarios = list(
        Multa.objects.filter(pagada=False)
        .values('prestamo__usuario__first_name', 'prestamo__usuario__last_name', 'prestamo__usuario__username', 'prestamo__usuario__tipo_usuario')
        .annotate(multa_actual=Sum('monto'), prestamos_con_multa=Count('id'))
        .order_by('-multa_actual')
    )
    total_multas_actuales = sum((item['multa_actual'] for item in multas_usuarios), Decimal('0.00'))
    for item in multas_usuarios:
        item['nombre'] = ' '.join(filter(None, [item['prestamo__usuario__first_name'], item['prestamo__usuario__last_name']])) or item['prestamo__usuario__username']

    vista = request.GET.get('vista', 'estadisticas')
    if vista not in {'estadisticas', 'prestamos', 'libros', 'multas'}:
        vista = 'estadisticas'

    return render(request, 'reportes.html', {
        'vista': vista,
        'fecha_inicio': fecha_inicio.isoformat() if fecha_inicio else '',
        'fecha_fin': fecha_fin.isoformat() if fecha_fin else '',
        'error_fechas': error_fechas,
        'total_prestamos': total_prestamos,
        'total_devueltos': total_devueltos,
        'total_activos': total_activos,
        'total_vencidos': total_vencidos,
        'estados_prestamo': estados_prestamo,
        'prestamos_por_mes': prestamos_por_mes,
        'libros_populares': libros_populares,
        'perfiles': perfiles,
        'etiquetas_populares': etiquetas_populares,
        'promedio_calificacion': resumen_resenas['promedio'],
        'total_resenas': resumen_resenas['total'],
        'distribucion_calificaciones': distribucion_calificaciones,
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
    respuesta['Content-Disposition'] = f'attachment; filename="reporte_biblioteca{sufijo}.csv"'
    respuesta.write('\ufeff')
    escritor = csv.writer(respuesta, delimiter=';', lineterminator='\n')
    escritor.writerow(['REPORTE DE PRÉSTAMOS | BIBLIOTECA SIS-INF'])
    escritor.writerow(['Periodo desde', fecha_inicio.strftime('%d/%m/%Y') if fecha_inicio else 'Inicio de registros'])
    escritor.writerow(['Periodo hasta', fecha_fin.strftime('%d/%m/%Y') if fecha_fin else 'Hoy'])
    escritor.writerow([])
    prestamos = Prestamo.objects.select_related('usuario', 'libro', 'multa').prefetch_related('libro__etiquetas').order_by('-fecha_prestamo')
    if fecha_inicio:
        prestamos = prestamos.filter(fecha_prestamo__gte=fecha_inicio)
    if fecha_fin:
        prestamos = prestamos.filter(fecha_prestamo__lte=fecha_fin)

    total_prestamos = prestamos.count()
    escritor.writerow(['RESUMEN OPERATIVO'])
    escritor.writerow(['Indicador', 'Cantidad'])
    escritor.writerow(['Préstamos registrados', total_prestamos])
    escritor.writerow(['Activos', prestamos.filter(estado='activo').count()])
    escritor.writerow(['Devueltos', prestamos.filter(estado='devuelto').count()])
    escritor.writerow(['Vencidos', prestamos.filter(estado='vencido').count()])
    escritor.writerow([])
    escritor.writerow(['DETALLE DE PRESTAMOS'])
    escritor.writerow([
        'Usuario', 'Perfil', 'Código/ISBN', 'Libro', 'Autor', 'Etiquetas',
        'Fecha préstamo', 'Fecha límite', 'Fecha devolución', 'Estado', 'Multa pendiente (Bs.)',
    ])
    for prestamo in prestamos:
        multa = getattr(prestamo, 'multa', None)
        escritor.writerow([
            prestamo.usuario.get_full_name() or prestamo.usuario.username,
            prestamo.usuario.get_tipo_usuario_display(),
            prestamo.libro.isbn or 'Sin código',
            prestamo.libro.titulo,
            prestamo.libro.autor,
            ', '.join(etiqueta.nombre for etiqueta in prestamo.libro.etiquetas.all()) or 'Sin etiquetas',
            prestamo.fecha_prestamo.strftime('%d/%m/%Y'),
            prestamo.fecha_limite.strftime('%d/%m/%Y'),
            prestamo.fecha_devolucion.strftime('%d/%m/%Y') if prestamo.fecha_devolucion else 'Pendiente',
            prestamo.get_estado_display(),
            f'{multa.monto:.2f}' if multa and not multa.pagada else '0.00',
        ])
    escritor.writerow([])
    escritor.writerow(['LIBROS MÁS SOLICITADOS'])
    escritor.writerow(['Libro', 'Autor', 'Préstamos'])
    populares = prestamos.values('libro__titulo', 'libro__autor').annotate(total=Count('id')).order_by('-total', 'libro__titulo')[:10]
    for item in populares:
        escritor.writerow([item['libro__titulo'], item['libro__autor'], item['total']])
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
