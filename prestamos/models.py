# prestamos/models.py
from django.db import models
from django.conf import settings
from catalogo.models import Libro

class Prestamo(models.Model):
    ESTADO_CHOICES = [
        ('activo', 'Activo'),
        ('devuelto', 'Devuelto'),
        ('vencido', 'Vencido'),
    ]
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    libro = models.ForeignKey(Libro, on_delete=models.CASCADE)
    fecha_prestamo = models.DateField(auto_now_add=True)
    fecha_devolucion = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='activo')

    def __str__(self):
        return f"{self.usuario} - {self.libro} ({self.estado})"

class Reserva(models.Model):
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    libro = models.ForeignKey(Libro, on_delete=models.CASCADE)
    fecha_reserva = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"{self.usuario} reservó {self.libro}"

class Multa(models.Model):
    prestamo = models.OneToOneField(Prestamo, on_delete=models.CASCADE)
    monto = models.DecimalField(max_digits=8, decimal_places=2)
    pagada = models.BooleanField(default=False)

    def __str__(self):
        return f"Multa {self.monto} - {'pagada' if self.pagada else 'pendiente'}"