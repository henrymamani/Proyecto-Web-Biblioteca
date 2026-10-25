from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from usuarios.models import Usuario
from prestamos.models import Prestamo

from .models import Etiqueta, Libro, Resena


class CatalogoEtiquetasYResenasTests(TestCase):
    def setUp(self):
        self.libro = Libro.objects.create(
            titulo='Diseño de algoritmos',
            autor='Ada Lovelace',
            stock=2,
        )
        self.etiqueta = Etiqueta.objects.create(nombre='Algoritmos')
        self.libro.etiquetas.add(self.etiqueta)
        self.estudiante = Usuario.objects.create_user(
            username='lectora',
            password='clave-segura',
            ru_ci='EST-RESENA-001',
            tipo_usuario='estudiante',
        )
        self.administrador = Usuario.objects.create_user(
            username='gestor',
            password='clave-segura',
            ru_ci='ADM-RESENA-001',
            tipo_usuario='administrador',
        )

    def test_busqueda_encuentra_libros_por_etiqueta(self):
        respuesta = self.client.get(reverse('catalogo'), {'q': 'Algoritmos'})

        self.assertContains(respuesta, self.libro.titulo)
        self.assertContains(respuesta, self.etiqueta.nombre)

    def test_catalogo_muestra_ejemplares_disponibles_y_registrados(self):
        Prestamo.objects.create(
            usuario=self.estudiante,
            libro=self.libro,
            fecha_limite='2030-01-10',
        )
        self.libro.stock = 1
        self.libro.save(update_fields=['stock'])

        respuesta = self.client.get(reverse('catalogo'))

        self.assertContains(respuesta, '1/2 disponible(s)')

    def test_inventario_no_duplica_prestamos_al_filtrar_varias_etiquetas(self):
        segunda_etiqueta = Etiqueta.objects.create(nombre='Programación')
        self.libro.etiquetas.add(segunda_etiqueta)
        Prestamo.objects.create(
            usuario=self.estudiante,
            libro=self.libro,
            fecha_limite='2030-01-10',
        )
        self.libro.stock = 1
        self.libro.save(update_fields=['stock'])

        respuesta = self.client.get(
            reverse('catalogo'),
            {'etiquetas': [self.etiqueta.id, segunda_etiqueta.id]},
        )

        self.assertContains(respuesta, '1/2 disponible(s)')

    def test_una_persona_solo_puede_calificar_una_vez_el_mismo_libro(self):
        Resena.objects.create(
            libro=self.libro,
            usuario=self.estudiante,
            calificacion=5,
            comentario='Muy claro.',
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Resena.objects.create(
                    libro=self.libro,
                    usuario=self.estudiante,
                    calificacion=4,
                    comentario='Intento duplicado.',
                )

    def test_solo_administracion_elimina_comentarios(self):
        resena = Resena.objects.create(
            libro=self.libro,
            usuario=self.estudiante,
            calificacion=5,
            comentario='Lectura recomendada.',
        )
        url = reverse('eliminar_resena', args=[resena.id])

        self.client.force_login(self.estudiante)
        respuesta = self.client.post(url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertTrue(Resena.objects.filter(pk=resena.id).exists())

        self.client.force_login(self.administrador)
        respuesta = self.client.post(url)
        self.assertEqual(respuesta.status_code, 302)
        self.assertFalse(Resena.objects.filter(pk=resena.id).exists())
