# Biblioteca SIS-INF

Sistema de biblioteca desarrollado con Django.

## Despliegue en Render

El repositorio ya incluye `render.yaml`, `build.sh` y la configuración necesaria para desplegar la aplicación en Render usando la base de datos MySQL de Aiven.

1. Sube estos cambios a GitHub. No subas el archivo `.env`.
2. En [Render](https://dashboard.render.com/), inicia sesión y selecciona **New +** → **Blueprint**.
3. Conecta el repositorio `Proyecto-Web-Biblioteca` y confirma el archivo `render.yaml`.
4. Pulsa **Apply**. Render creará solo el servicio web; la información seguirá almacenada en Aiven.
5. Cuando Render pida los valores marcados como secretos, agrega estos valores en **Environment** del servicio web:

   - `DJANGO_ALLOWED_HOSTS`: el dominio que Render asignó, por ejemplo `biblioteca-sis.onrender.com`.
   - `DJANGO_CSRF_TRUSTED_ORIGINS`: `https://biblioteca-sis.onrender.com`.
   - `GOOGLE_OAUTH_CLIENT_ID` y `GOOGLE_OAUTH_CLIENT_SECRET`.
   - `GOOGLE_OAUTH_REDIRECT_URI`: `https://biblioteca-sis.onrender.com/ingresar/google/retorno/`.
   - `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT`: usa los datos de conexión de Aiven.

   En **Secret Files**, agrega el certificado CA descargado de Aiven con el nombre `aiven-ca.pem`. Render lo expondrá como `/etc/secrets/aiven-ca.pem`; esa ruta ya está configurada en `DB_SSL_CA`.

   Conserva `GOOGLE_OAUTH_ALLOWED_DOMAIN=sistemas.edu.bo` si solo deben entrar cuentas institucionales.

6. En Google Cloud Console, añade la misma dirección de retorno de Render en **Authorized redirect URIs**. Debe coincidir carácter por carácter con la variable anterior.
7. Espera que termine el despliegue y abre la URL `https://...onrender.com` que muestra Render.
8. En Render abre **Shell** dentro del servicio y ejecuta `python manage.py createsuperuser` para crear el primer administrador.

El inicio del servicio ejecuta automáticamente las migraciones sobre Aiven y el comando de construcción recopila los archivos estáticos. En producción `DJANGO_DEBUG` queda desactivado.

## Desarrollo local

1. Copia `.env.example` como `.env` y completa tus variables locales.
2. Instala dependencias: `python -m pip install -r requirements.txt`.
3. Ejecuta migraciones: `python manage.py migrate`.
4. Inicia el proyecto: `python manage.py runserver`.

Para una base local rápida puedes usar SQLite:

```env
DB_ENGINE=django.db.backends.sqlite3
DB_NAME=db.sqlite3
```
