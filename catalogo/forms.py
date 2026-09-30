from django import forms

from .models import Libro


class LibroForm(forms.ModelForm):
    class Meta:
        model = Libro
        fields = (
            'titulo', 'autor', 'isbn', 'categoria', 'editorial',
            'anio_publicacion', 'ubicacion', 'stock', 'descripcion', 'imagen_url',
        )
        labels = {
            'isbn': 'Codigo',
            'anio_publicacion': 'Año de publicacion',
            'imagen_url': 'Imagen de portada (URL)',
            'stock': 'Ejemplares disponibles',
        }
        widgets = {
            'descripcion': forms.Textarea(attrs={'rows': 3}),
            'anio_publicacion': forms.NumberInput(attrs={'min': 1900, 'max': 2100}),
            'stock': forms.NumberInput(attrs={'min': 0}),
        }
