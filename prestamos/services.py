from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from catalogo.models import Libro

from .models import Multa, Notificacion, Prestamo, Reserva


DIAS_PRESTAMO = 7
VALOR_MULTA_DIARIA = Decimal('2.00')
DIAS_AVISO = 2


class ReglaPrestamoError(Exception):
    pass


def prestamos_abiertos(usuario):
    return Prestamo.objects.filter(usuario=usuario, estado__in=['activo', 'vencido'])


@transaction.atomic
def crear_prestamo(usuario, libro):
    # Evita que dos autorizaciones consuman el mismo ejemplar al mismo tiempo.
    libro = Libro.objects.select_for_update().get(pk=libro.pk)
    if usuario.tipo_usuario not in ('estudiante', 'docente'):
        raise ReglaPrestamoError('Solo estudiantes y docentes pueden recibir prestamos.')
    if prestamos_abiertos(usuario).count() >= usuario.limite_prestamos:
        raise ReglaPrestamoError(
            f'{usuario.get_full_name() or usuario.username} alcanzo su limite de '
            f'{usuario.limite_prestamos} libros.'
        )
    if libro.stock < 1:
        raise ReglaPrestamoError('No hay ejemplares disponibles para este libro.')
    libro.stock -= 1
    libro.save(update_fields=['stock'])
    prestamo = Prestamo.objects.create(
        usuario=usuario,
        libro=libro,
        fecha_limite=timezone.localdate() + timedelta(days=DIAS_PRESTAMO),
    )
    return prestamo


@transaction.atomic
def autorizar_reserva(reserva):
    """Convierte una solicitud pendiente en un préstamo autorizado."""
    reserva = Reserva.objects.select_for_update().select_related('usuario', 'libro').get(pk=reserva.pk)
    if reserva.estado != 'pendiente':
        raise ReglaPrestamoError('Esta solicitud ya fue procesada.')

    prestamo = crear_prestamo(reserva.usuario, reserva.libro)
    reserva.estado = 'autorizada'
    reserva.save(update_fields=['estado'])
    return prestamo


@transaction.atomic
def registrar_devolucion(prestamo):
    # Se vuelve a leer bloqueado para que una devolución no se procese dos veces.
    prestamo = Prestamo.objects.select_for_update().select_related('libro').get(pk=prestamo.pk)
    if prestamo.estado == 'devuelto':
        raise ReglaPrestamoError('Este prestamo ya fue registrado como devuelto.')

    hoy = timezone.localdate()
    retraso = max(0, (hoy - prestamo.fecha_limite).days)
    prestamo.fecha_devolucion = hoy
    prestamo.estado = 'devuelto'
    prestamo.save(update_fields=['fecha_devolucion', 'estado'])
    libro = Libro.objects.select_for_update().get(pk=prestamo.libro_id)
    libro.stock += 1
    libro.save(update_fields=['stock'])

    primera_reserva = Reserva.objects.filter(
        libro=libro,
        estado='pendiente',
    ).select_related('usuario').order_by('fecha_reserva').first()
    if primera_reserva:
        mensaje_reserva = (
            f'Hay un ejemplar disponible de {prestamo.libro.titulo}. '
            'Tu solicitud esta pendiente de autorizacion por la biblioteca.'
        )
        if not Notificacion.objects.filter(
            usuario=primera_reserva.usuario,
            prestamo__isnull=True,
            tipo='reserva',
            mensaje=mensaje_reserva,
        ).exists():
            Notificacion.objects.create(
                usuario=primera_reserva.usuario,
                tipo='reserva',
                mensaje=mensaje_reserva,
            )

    if retraso:
        multa, _ = Multa.objects.update_or_create(
            prestamo=prestamo,
            defaults={'monto': VALOR_MULTA_DIARIA * retraso},
        )
        Notificacion.objects.get_or_create(
            usuario=prestamo.usuario,
            prestamo=prestamo,
            tipo='multa',
            defaults={
                'mensaje': f'Tienes una multa pendiente de Bs. {multa.monto} por devolucion tardia.'
            },
        )
    return retraso


def actualizar_sistema():
    """Marca vencidos, recalcula multas y deja un aviso antes del vencimiento."""
    hoy = timezone.localdate()
    prestamos = Prestamo.objects.filter(estado__in=['activo', 'vencido']).select_related('usuario', 'libro')
    for prestamo in prestamos:
        if prestamo.fecha_limite < hoy:
            retraso = (hoy - prestamo.fecha_limite).days
            if prestamo.estado != 'vencido':
                prestamo.estado = 'vencido'
                prestamo.save(update_fields=['estado'])
            Multa.objects.update_or_create(
                prestamo=prestamo,
                defaults={'monto': VALOR_MULTA_DIARIA * retraso},
            )
            Notificacion.objects.get_or_create(
                usuario=prestamo.usuario,
                prestamo=prestamo,
                tipo='multa',
                defaults={
                    'mensaje': f'El prestamo de {prestamo.libro.titulo} esta vencido. Multa actual: Bs. {VALOR_MULTA_DIARIA * retraso}.',
                },
            )
        elif prestamo.fecha_limite <= hoy + timedelta(days=DIAS_AVISO):
            dias = (prestamo.fecha_limite - hoy).days
            mensaje = (
                f'El libro {prestamo.libro.titulo} vence hoy.' if dias == 0
                else f'El libro {prestamo.libro.titulo} vence en {dias} dia(s).'
            )
            Notificacion.objects.get_or_create(
                usuario=prestamo.usuario,
                prestamo=prestamo,
                tipo='vencimiento',
                defaults={'mensaje': mensaje},
            )
