# usuarios/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    TIPO_USUARIO_CHOICES = [
        ('estudiante', 'Estudiante'),
        ('docente', 'Docente'),
        ('bibliotecario', 'Bibliotecario'),
    ]
    tipo_usuario = models.CharField(max_length=20, choices=TIPO_USUARIO_CHOICES)
    ru_ci = models.CharField(max_length=20, unique=True)
    limite_prestamos = models.PositiveIntegerField(default=2)

    def save(self, *args, **kwargs):
        # Asigna el límite automáticamente según el rol, si no se definió a mano
        if self.tipo_usuario == 'estudiante':
            self.limite_prestamos = self.limite_prestamos or 2
        elif self.tipo_usuario == 'docente':
            self.limite_prestamos = self.limite_prestamos or 5
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.tipo_usuario})"