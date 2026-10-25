from django.test import TestCase
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.test import RequestFactory
from django.urls import reverse

from Biblioteca_sis.views import actualizar_reserva, crear_reserva
from catalogo.models import Libro
from usuarios.models import Usuario

from .models import Prestamo, Reserva
from .services import ReglaPrestamoError, registrar_devolucion


class FlujoAutorizacionReservasTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.libro = Libro.objects.create(
            titulo='Algoritmos',
            autor='Ada Lovelace',
            isbn='978-0-123456-47-2',
            stock=2,
        )
        self.estudiante = Usuario.objects.create_user(
            username='estudiante',
            password='clave-segura',
            ru_ci='EST-001',
            tipo_usuario='estudiante',
        )
        self.docente = Usuario.objects.create_user(
            username='docente',
            password='clave-segura',
            ru_ci='DOC-001',
            tipo_usuario='docente',
        )
        self.administrador = Usuario.objects.create_superuser(
            username='administrador',
            password='clave-segura',
            email='admin@biblioteca.test',
            ru_ci='ADM-001',
            tipo_usuario='administrador',
        )

    def solicitud_post(self, url, usuario):
        request = self.factory.post(url)
        request.user = usuario
        SessionMiddleware(lambda request: None).process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)
        return request

    def test_estudiante_y_docente_pueden_enviar_solicitudes(self):
        for usuario in (self.estudiante, self.docente):
            with self.subTest(usuario=usuario.username):
                url = reverse('crear_reserva', args=[self.libro.id])
                respuesta = crear_reserva(self.solicitud_post(url, usuario), self.libro.id)

                self.assertEqual(respuesta.status_code, 302)
                self.assertEqual(respuesta.url, reverse('catalogo'))
                self.assertTrue(
                    Reserva.objects.filter(usuario=usuario, libro=self.libro, estado='pendiente').exists()
                )

    def test_autorizar_solicitud_crea_prestamo_y_actualiza_stock(self):
        reserva = Reserva.objects.create(usuario=self.estudiante, libro=self.libro)
        url = reverse('actualizar_reserva', args=[reserva.id, 'autorizar'])
        respuesta = actualizar_reserva(
            self.solicitud_post(url, self.administrador), reserva.id, 'autorizar'
        )

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(respuesta.url, reverse('reservas'))
        reserva.refresh_from_db()
        self.libro.refresh_from_db()
        self.assertEqual(reserva.estado, 'autorizada')
        self.assertTrue(Prestamo.objects.filter(usuario=self.estudiante, libro=self.libro).exists())
        self.assertEqual(self.libro.stock, 1)

    def test_no_se_puede_autorizar_dos_veces_la_misma_solicitud(self):
        reserva = Reserva.objects.create(usuario=self.estudiante, libro=self.libro)
        url = reverse('actualizar_reserva', args=[reserva.id, 'autorizar'])

        actualizar_reserva(self.solicitud_post(url, self.administrador), reserva.id, 'autorizar')
        actualizar_reserva(self.solicitud_post(url, self.administrador), reserva.id, 'autorizar')

        self.assertEqual(Prestamo.objects.filter(usuario=self.estudiante, libro=self.libro).count(), 1)

    def test_no_se_puede_registrar_la_misma_devolucion_dos_veces(self):
        prestamo = Prestamo.objects.create(
            usuario=self.estudiante,
            libro=self.libro,
            fecha_limite='2030-01-10',
        )
        self.libro.stock = 1
        self.libro.save(update_fields=['stock'])

        registrar_devolucion(prestamo)
        with self.assertRaises(ReglaPrestamoError):
            registrar_devolucion(prestamo)

        self.libro.refresh_from_db()
        self.assertEqual(self.libro.stock, 2)

# Create your tests here.
