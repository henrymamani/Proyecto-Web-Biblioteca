# usuarios/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    TIPO_USUARIO_CHOICES = [
        ('estudiante', 'Estudiante'),
        ('docente', 'Docente'),
        ('administrador', 'Administrador'),
    ]
    tipo_usuario = models.CharField(max_length=20, choices=TIPO_USUARIO_CHOICES)
    ru_ci = models.CharField(max_length=20, unique=True)
    google_sub = models.CharField(max_length=255, unique=True, null=True, blank=True)
    limite_prestamos = models.PositiveIntegerField(default=2, editable=False)

    LIMITES_POR_ROL = {
        'estudiante': 2,
        'docente': 3,
        'administrador': 0,
    }

    def save(self, *args, **kwargs):
        self.limite_prestamos = self.LIMITES_POR_ROL.get(self.tipo_usuario, 0)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.tipo_usuario})"
