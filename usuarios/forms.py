from django import forms
from django.contrib.auth.forms import UserCreationForm

from .models import Usuario


class RegistroEstudianteForm(UserCreationForm):
    first_name = forms.CharField(label='Nombres', max_length=150)
    last_name = forms.CharField(label='Apellidos', max_length=150)
    email = forms.EmailField(label='Correo institucional')

    class Meta:
        model = Usuario
        fields = ('first_name', 'last_name', 'ru_ci', 'email', 'username', 'password1', 'password2')
        labels = {
            'ru_ci': 'Carnet de Identidad',
            'username': 'Usuario',
            'password1': 'Contrasena',
            'password2': 'Confirmar contrasena',
        }

    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.tipo_usuario = 'estudiante'
        if commit:
            usuario.save()
        return usuario
