from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'tipo_usuario', 'is_active')
    fieldsets = UserAdmin.fieldsets + (
        ('Biblioteca', {'fields': ('tipo_usuario', 'ru_ci', 'google_sub', 'limite_prestamos')}),
    )
