from django.test import TestCase
from django.test import override_settings
from django.urls import reverse
from unittest.mock import Mock, patch

from .models import Usuario


class RegistroDesdeAdministracionTests(TestCase):
    def setUp(self):
        self.administrador = Usuario.objects.create_user(
            username='admin',
            password='clave-segura',
            ru_ci='ADM-REGISTRO-001',
            tipo_usuario='administrador',
        )

    def test_administrador_puede_registrar_estudiante_sin_cerrar_sesion(self):
        self.client.force_login(self.administrador)

        respuesta = self.client.post(reverse('registro'), {
            'first_name': 'Ana',
            'last_name': 'Pérez',
            'ru_ci': 'EST-REGISTRO-001',
            'email': 'ana@example.com',
            'username': 'ana',
            'password1': 'Clave-segura-123',
            'password2': 'Clave-segura-123',
        })

        self.assertRedirects(respuesta, reverse('panel'))
        self.assertTrue(Usuario.objects.filter(username='ana', tipo_usuario='estudiante').exists())
        self.assertEqual(self.client.session['_auth_user_id'], str(self.administrador.id))


@override_settings(
    GOOGLE_OAUTH_CLIENT_ID='cliente-prueba',
    GOOGLE_OAUTH_CLIENT_SECRET='secreto-prueba',
    GOOGLE_OAUTH_ALLOWED_DOMAIN='sistemas.edu.bo',
)
class AccesoGoogleTests(TestCase):
    @patch('Biblioteca_sis.views._verificar_token_google')
    @patch('Biblioteca_sis.views.requests.post')
    def test_crea_e_ingresa_estudiante_con_correo_google_verificado(self, post, verificar):
        post.return_value = Mock(json=lambda: {'id_token': 'token-prueba'})
        verificar.return_value = {
            'sub': '109876543210987654321',
            'email': 'estudiante@sistemas.edu.bo',
            'email_verified': True,
            'hd': 'sistemas.edu.bo',
            'given_name': 'Estudiante',
            'family_name': 'Google',
        }

        inicio = self.client.get(reverse('login_google'))
        estado = self.client.session['google_oauth_estado']
        respuesta = self.client.get(reverse('retorno_google'), {'state': estado, 'code': 'codigo-prueba'})

        self.assertRedirects(respuesta, reverse('panel'))
        usuario = Usuario.objects.get(email='estudiante@sistemas.edu.bo')
        self.assertEqual(usuario.tipo_usuario, 'estudiante')
        self.assertEqual(usuario.google_sub, '109876543210987654321')
        self.assertFalse(usuario.has_usable_password())

    @patch('Biblioteca_sis.views._verificar_token_google')
    @patch('Biblioteca_sis.views.requests.post')
    def test_rechaza_cuenta_fuera_del_dominio_institucional(self, post, verificar):
        post.return_value = Mock(json=lambda: {'id_token': 'token-prueba'})
        verificar.return_value = {
            'sub': '109876543210987654321',
            'email': 'persona@gmail.com',
            'email_verified': True,
            'hd': '',
        }

        self.client.get(reverse('login_google'))
        estado = self.client.session['google_oauth_estado']
        respuesta = self.client.get(reverse('retorno_google'), {'state': estado, 'code': 'codigo-prueba'})

        self.assertRedirects(respuesta, reverse('login'))
        self.assertFalse(Usuario.objects.filter(email='persona@gmail.com').exists())
