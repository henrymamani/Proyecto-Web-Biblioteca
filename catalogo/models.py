# catalogo/models.py
from django.db import models

class Libro(models.Model):
    titulo = models.CharField(max_length=200)
    autor = models.CharField(max_length=150)
    categoria = models.CharField(max_length=100)
    stock = models.PositiveIntegerField(default=1)

    def __str__(self):
        return self.titulo

    @property
    def disponible(self):
        return self.stock > 0