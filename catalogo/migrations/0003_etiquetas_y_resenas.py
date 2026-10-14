from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models
import django.db.models.deletion


def migrar_categorias_a_etiquetas(apps, schema_editor):
    Libro = apps.get_model('catalogo', 'Libro')
    Etiqueta = apps.get_model('catalogo', 'Etiqueta')

    for libro in Libro.objects.exclude(categoria__isnull=True).exclude(categoria__exact=''):
        etiqueta, _ = Etiqueta.objects.get_or_create(nombre=libro.categoria.strip())
        libro.etiquetas.add(etiqueta)


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('catalogo', '0002_detalle_bibliografico'),
    ]

    operations = [
        migrations.CreateModel(
            name='Etiqueta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=60, unique=True)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
            ],
            options={'ordering': ['nombre']},
        ),
        migrations.AddField(
            model_name='libro',
            name='etiquetas',
            field=models.ManyToManyField(blank=True, related_name='libros', to='catalogo.etiqueta'),
        ),
        migrations.RunPython(migrar_categorias_a_etiquetas, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='libro',
            name='categoria',
        ),
        migrations.CreateModel(
            name='Resena',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('calificacion', models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])),
                ('comentario', models.TextField(max_length=1000)),
                ('creada_en', models.DateTimeField(auto_now_add=True)),
                ('libro', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='resenas', to='catalogo.libro')),
                ('usuario', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={'ordering': ['-creada_en']},
        ),
        migrations.AddConstraint(
            model_name='resena',
            constraint=models.UniqueConstraint(fields=('libro', 'usuario'), name='una_resena_por_usuario_y_libro'),
        ),
    ]
