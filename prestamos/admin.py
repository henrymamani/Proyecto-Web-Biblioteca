from django.contrib import admin

from .models import Prestamo, Reserva, Multa 
admin.site.register(Prestamo) 
admin.site.register(Reserva) 
admin.site.register(Multa)
# Register your models here.
