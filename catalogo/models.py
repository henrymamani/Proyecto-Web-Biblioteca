# catalogo/models.py
from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class Etiqueta(models.Model):
    nombre = models.CharField(max_length=60, unique=True)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

class Libro(models.Model):
    titulo = models.CharField(max_length=200)
    autor = models.CharField(max_length=150)
    isbn = models.CharField(max_length=20, unique=True, null=True, blank=True)
    etiquetas = models.ManyToManyField(Etiqueta, blank=True, related_name='libros')
    editorial = models.CharField(max_length=120, blank=True)
    anio_publicacion = models.PositiveIntegerField(null=True, blank=True)
    ubicacion = models.CharField(max_length=80, blank=True)
    descripcion = models.TextField(blank=True)
    imagen_url = models.URLField(blank=True)
    stock = models.PositiveIntegerField(default=1)
    creado_en = models.DateTimeField(auto_now_add=True, null=True)

    def __str__(self):
        return self.titulo

    @property
    def disponible(self):
        return self.stock > 0


class Resena(models.Model):
    libro = models.ForeignKey(Libro, on_delete=models.CASCADE, related_name='resenas')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    calificacion = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comentario = models.TextField(max_length=1000)
    creada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creada_en']
        constraints = [
            models.UniqueConstraint(
                fields=['libro', 'usuario'],
                name='una_resena_por_usuario_y_libro',
            )
        ]

    def __str__(self):
        return f'{self.libro} - {self.usuario}'
