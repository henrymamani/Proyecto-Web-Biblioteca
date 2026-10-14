"""
URL configuration for Biblioteca_sis project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('registro/', views.registro, name='registro'),
    path('ingresar/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    path('salir/', views.salir, name='logout'),
    path('panel/', views.panel, name='panel'),
    path('catalogo/', views.catalogo, name='catalogo'),
    path('catalogo/<int:libro_id>/', views.detalle_libro, name='detalle_libro'),
    path('gestion/libros/', views.administrar_libros, name='administrar_libros'),
    path('gestion/libros/<int:libro_id>/editar/', views.administrar_libros, name='editar_libro'),
    path('gestion/etiquetas/', views.administrar_etiquetas, name='administrar_etiquetas'),
    path('gestion/etiquetas/<int:etiqueta_id>/eliminar/', views.eliminar_etiqueta, name='eliminar_etiqueta'),
    path('gestion/prestamos/', views.administrar_prestamos, name='administrar_prestamos'),
    path('gestion/prestamos/<int:prestamo_id>/devolver/', views.devolver_prestamo, name='devolver_prestamo'),
    path('mis-prestamos/', views.mis_prestamos, name='mis_prestamos'),
    path('catalogo/<int:libro_id>/reservar/', views.crear_reserva, name='crear_reserva'),
    path('catalogo/<int:libro_id>/resenas/', views.crear_resena, name='crear_resena'),
    path('resenas/<int:resena_id>/eliminar/', views.eliminar_resena, name='eliminar_resena'),
    path('reservas/', views.reservas, name='reservas'),
    path('reservas/<int:reserva_id>/<str:accion>/', views.actualizar_reserva, name='actualizar_reserva'),
    path('notificaciones/', views.notificaciones, name='notificaciones'),
    path('reportes/', views.reportes, name='reportes'),
    path('reportes/prestamos.csv', views.exportar_reporte_prestamos, name='exportar_reporte_prestamos'),
]
