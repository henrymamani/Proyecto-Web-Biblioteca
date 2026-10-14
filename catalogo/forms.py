from django import forms

from .models import Etiqueta, Libro, Resena


class LibroForm(forms.ModelForm):
    class Meta:
        model = Libro
        fields = (
            'titulo', 'autor', 'isbn', 'etiquetas', 'editorial',
            'anio_publicacion', 'ubicacion', 'stock', 'descripcion', 'imagen_url',
        )
        labels = {
            'isbn': 'Codigo',
            'anio_publicacion': 'Año de publicacion',
            'imagen_url': 'Imagen de portada (URL)',
            'stock': 'Ejemplares disponibles',
            'etiquetas': 'Etiquetas',
        }
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'anio_publicacion': forms.NumberInput(attrs={'min': 1900, 'max': 2100}),
            'stock': forms.NumberInput(attrs={'min': 0}),
            'etiquetas': forms.CheckboxSelectMultiple(),
        }


class EtiquetaForm(forms.ModelForm):
    class Meta:
        model = Etiqueta
        fields = ('nombre',)
        labels = {'nombre': 'Nueva etiqueta'}
        widgets = {
            'nombre': forms.TextInput(attrs={'placeholder': 'Ej. Bases de datos'}),
        }


class ResenaForm(forms.ModelForm):
    class Meta:
        model = Resena
        fields = ('calificacion', 'comentario')
        labels = {
            'calificacion': 'Calificación',
            'comentario': 'Comentario',
        }
        widgets = {
            'calificacion': forms.Select(choices=[
                (1, '1 estrella'),
                (2, '2 estrellas'),
                (3, '3 estrellas'),
                (4, '4 estrellas'),
                (5, '5 estrellas'),
            ]),
            'comentario': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'Comparte una opinión útil sobre este libro.',
                'maxlength': 1000,
            }),
        }
