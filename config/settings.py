from pathlib import Path
import os
import urllib.parse

BASE_DIR = Path(__file__).resolve().parent.parent

# Configuración sensible y de entorno
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-informatica-2026-cambiar-en-produccion')

DEBUG = os.environ.get('DEBUG', 'True').lower() in ('true', '1', 't', 'yes')

allowed_hosts_env = os.environ.get('ALLOWED_HOSTS', '*')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_env.split(',') if h.strip()]

# Soporte para orígenes de confianza CSRF (Requerido en despliegues con HTTPS / Traefik / Coolify)
csrf_origins_env = os.environ.get('CSRF_TRUSTED_ORIGINS', '')
if csrf_origins_env:
    CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_origins_env.split(',') if o.strip()]

# Configuración de proxy inverso (Traefik / Coolify SSL termination)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True
USE_X_FORWARDED_PORT = True

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'documentos',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

X_FRAME_OPTIONS = 'SAMEORIGIN'

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'documentos.context_processors.sidebar_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Base de datos: Soporte para PostgreSQL (Coolify / Producción) y SQLite (Desarrollo / Local)
database_url = os.environ.get('DATABASE_URL')
db_name = os.environ.get('DB_NAME') or os.environ.get('POSTGRES_DB')
db_host = os.environ.get('DB_HOST') or os.environ.get('POSTGRES_HOST')

if database_url:
    # Soporte para URL única (ej: postgresql://usuario:clave@host:5432/nombre_db)
    url = urllib.parse.urlparse(database_url)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': url.path.lstrip('/'),
            'USER': urllib.parse.unquote(url.username or ''),
            'PASSWORD': urllib.parse.unquote(url.password or ''),
            'HOST': url.hostname or 'localhost',
            'PORT': url.port or 5432,
        }
    }
elif db_name and db_host:
    # Soporte para variables individuales (ej: DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': db_name,
            'USER': os.environ.get('DB_USER') or os.environ.get('POSTGRES_USER', 'postgres'),
            'PASSWORD': os.environ.get('DB_PASSWORD') or os.environ.get('POSTGRES_PASSWORD', ''),
            'HOST': db_host,
            'PORT': int(os.environ.get('DB_PORT') or os.environ.get('POSTGRES_PORT', 5432)),
        }
    }
else:
    # SQLite por defecto para desarrollo local o volumen persistente simple
    sqlite_path = os.environ.get('SQLITE_DB_PATH')
    if sqlite_path:
        db_file = Path(sqlite_path)
    else:
        db_file = BASE_DIR / 'db.sqlite3'

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': db_file,
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-ar'
TIME_ZONE = 'America/Argentina/Buenos_Aires'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

media_root_env = os.environ.get('MEDIA_ROOT')
if media_root_env:
    MEDIA_ROOT = Path(media_root_env)
else:
    MEDIA_ROOT = BASE_DIR / 'media'

MEDIA_URL = '/media/'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Autenticación
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'
