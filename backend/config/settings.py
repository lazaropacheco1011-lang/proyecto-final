"""
Configuración de REFRIMASTE.

Ajusta los valores sensibles mediante el archivo .env (ver .env.example).
"""
import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')


def env_bool(name, default=False):
    return os.getenv(name, str(default)).lower() in ('1', 'true', 'yes', 'on')


# ---------------------------------------------------------------------------
# Seguridad
# ---------------------------------------------------------------------------
DEBUG = env_bool('DEBUG', False)

SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = 'django-insecure-refrimaste-dev-secret-key'
    else:
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY no está definido. Es obligatorio fuera de DEBUG.'
        )

# En desarrollo se aceptan todos los hosts; en producción se restringe.
ALLOWED_HOSTS = [
    h.strip() for h in os.getenv('ALLOWED_HOSTS', '*' if DEBUG else 'localhost,127.0.0.1').split(',') if h.strip()
]

# Cabeceras de seguridad (activas por defecto fuera de DEBUG).
# Render termina el TLS en su proxy; confiamos en X-Forwarded-Proto para
# que request.is_secure() y SECURE_SSL_REDIRECT funcionen correctamente.
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env_bool('SECURE_SSL_REDIRECT', not DEBUG)
SESSION_COOKIE_SECURE = env_bool('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = env_bool('CSRF_COOKIE_SECURE', not DEBUG)
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0' if DEBUG else '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', not DEBUG)
SECURE_HSTS_PRELOAD = env_bool('SECURE_HSTS_PRELOAD', not DEBUG)
SECURE_CONTENT_TYPE_NOSNIFF = env_bool('SECURE_CONTENT_TYPE_NOSNIFF', True)
SECURE_BROWSER_XSS_FILTER = env_bool('SECURE_BROWSER_XSS_FILTER', True)
X_FRAME_OPTIONS = os.getenv('X_FRAME_OPTIONS', 'DENY')
SECURE_REFERRER_POLICY = os.getenv('SECURE_REFERRER_POLICY', 'same-origin')

# ---------------------------------------------------------------------------
# Aplicaciones
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Terceros
    'corsheaders',
    'rest_framework',
    'django_filters',
    'drf_spectacular',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',

    # Módulos del proyecto
    'apps.core',
    'apps.accounts',
    'apps.clientes',
    'apps.solicitudes',
    'apps.equipos',
    'apps.instalaciones',
    'apps.servicios',
    'apps.mantenimientos',
    'apps.materiales',
    'apps.cotizaciones',
    'apps.pagos',
    'apps.notificaciones',
    'apps.evaluaciones',
    'apps.reportes',
    'apps.almacen',
    'apps.tienda',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# ---------------------------------------------------------------------------
# Base de datos (SQLite por defecto, lista para PostgreSQL)
# ---------------------------------------------------------------------------
DATABASE_ENGINE = os.getenv('DB_ENGINE', 'sqlite').lower()

if DATABASE_ENGINE == 'postgres':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.getenv('DB_NAME', 'refrimaste'),
            'USER': os.getenv('DB_USER', 'postgres'),
            'PASSWORD': os.getenv('DB_PASSWORD', ''),
            'HOST': os.getenv('DB_HOST', 'localhost'),
            'PORT': os.getenv('DB_PORT', '5432'),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.getenv('DB_NAME', str(BASE_DIR / 'db.sqlite3')),
        }
    }

# ---------------------------------------------------------------------------
# Autenticación
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ---------------------------------------------------------------------------
# Internacionalización
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'es-do'
TIME_ZONE = 'America/Santo_Domingo'
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos y media
# ---------------------------------------------------------------------------
# El frontend (HTML/CSS/JS/imágenes) vive en la carpeta "frontend" junto a
# "backend". El backend lo sirve vía config.urls (rutas /css/, /js/ y
# /assets/). Incluirlo en STATICFILES_DIRS permite que collectstatic y el
# dev server también lo resuelvan con la convención /static/ de Django.
FRONTEND_DIR = BASE_DIR.parent / 'frontend'

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    FRONTEND_DIR,
]

MEDIA_URL = '/media/'
# MEDIA_ROOT configurable por entorno para poder montar un Persistent Disk de
# Render en producción (los uploads persisten entre deploys).
MEDIA_ROOT = os.getenv('MEDIA_ROOT', str(BASE_DIR / 'media'))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.ScopedRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'anon': os.getenv('THROTTLE_ANON', '60/min'),
        'user': os.getenv('THROTTLE_USER', '300/min'),
        'auth': os.getenv('THROTTLE_AUTH', '5/min'),
        'password': os.getenv('THROTTLE_PASSWORD', '5/hour'),
        'password_reset': os.getenv('THROTTLE_PASSWORD_RESET', '10/min'),
    },
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DATETIME_FORMAT': '%Y-%m-%dT%H:%M:%S',
    'DATE_FORMAT': '%Y-%m-%d',
    'NON_FIELD_ERRORS_KEY': 'error',
    'EXCEPTION_HANDLER': 'apps.core.exceptions.custom_exception_handler',
}

# ---------------------------------------------------------------------------
# JWT (djangorestframework-simplejwt)
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=int(os.getenv('ACCESS_TOKEN_MINUTES', '60'))),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=int(os.getenv('REFRESH_TOKEN_DAYS', '7'))),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'TOKEN_USER_CLASS': 'rest_framework_simplejwt.models.TokenUser',
}

# ---------------------------------------------------------------------------
# CORS (frontend)
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = env_bool('CORS_ALLOW_ALL_ORIGINS', False)
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv('CORS_ALLOWED_ORIGINS', '').split(',') if o.strip()
]
CORS_ALLOW_CREDENTIALS = env_bool('CORS_ALLOW_CREDENTIALS', True)

# Orígenes HTTPS de confianza para CSRF (se define por variable de entorno,
# sin dominio fijo en el código). Django rechaza POSTs salvo que el origen
# coincida con esta lista en producción.
CSRF_TRUSTED_ORIGINS = [
    o.strip() for o in os.getenv('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()
]

# ---------------------------------------------------------------------------
# Correo electrónico
# ---------------------------------------------------------------------------
# En desarrollo se usa el backend de consola (imprime los correos en la
# terminal) a menos que se configure SMTP mediante variables de entorno.
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG
    else 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', 'localhost')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '') or '587')
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
EMAIL_USE_TLS = env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = env_bool('EMAIL_USE_SSL', False)
# Tiempo máximo de espera al conectar/enviar por SMTP para no bloquear
# la petición si el servidor de correo no responde (en segundos).
EMAIL_TIMEOUT = int(os.getenv('EMAIL_TIMEOUT', '') or '15')
DEFAULT_FROM_EMAIL = os.getenv(
    'DEFAULT_FROM_EMAIL', 'RefriMaster <no-responder@refrimaster.com>'
)

# ---------------------------------------------------------------------------
# Recuperación de contraseña
# ---------------------------------------------------------------------------
# URL pública del frontend (se usa para construir el enlace de recuperación).
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://127.0.0.1:8000')
PASSWORD_RESET_TIMEOUT_MINUTES = int(os.getenv('PASSWORD_RESET_TIMEOUT_MINUTES', '1440'))

# ---------------------------------------------------------------------------
# Tienda y pagos
# ---------------------------------------------------------------------------
# Moneda de la vitrina y envío.
TIENDA_MONEDA = os.getenv('TIENDA_MONEDA', 'DOP')
COSTO_ENVIO = int(os.getenv('COSTO_ENVIO', '25000'))
ENVIO_GRATIS_MINIMO = int(os.getenv('ENVIO_GRATIS_MINIMO', '500000'))

# Modo del proveedor de pagos: 'sandbox' (simulación de tarjetas y PayPal)
# o 'produccion' (requiere credenciales reales).
PAYMENT_MODE = os.getenv('PAYMENT_MODE', 'sandbox').lower()

# PayPal (se usa urllib, sin dependencias extra).
PAYPAL_MODE = os.getenv('PAYPAL_MODE', 'sandbox').lower()
PAYPAL_CLIENT_ID = os.getenv('PAYPAL_CLIENT_ID', '')
PAYPAL_CLIENT_SECRET = os.getenv('PAYPAL_CLIENT_SECRET', '')
PAYPAL_API_BASE = os.getenv(
    'PAYPAL_API_BASE',
    'https://api-m.sandbox.paypal.com' if PAYPAL_MODE == 'sandbox'
    else 'https://api-m.paypal.com',
)

# ---------------------------------------------------------------------------
# Documentación de la API (drf-spectacular)
# ---------------------------------------------------------------------------
SPECTACULAR_SETTINGS = {
    'TITLE': 'REFRIMASTE API',
    'DESCRIPTION': (
        'Backend del Sistema de Administración de Instalación de Equipos '
        'de Refrigeración. Autenticación JWT, roles, clientes, equipos, '
        'instalaciones, órdenes de servicio, mantenimientos, materiales, '
        'cotizaciones, pagos, notificaciones, evaluaciones y reportes.'
    ),
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'TAGS': [
        {'name': 'Autenticación', 'description': 'Registro, login, logout, token y perfil'},
        {'name': 'Usuarios', 'description': 'Gestión de usuarios y roles'},
        {'name': 'Técnicos', 'description': 'Perfiles de técnicos'},
        {'name': 'Clientes', 'description': 'Clientes y direcciones de instalación'},
        {'name': 'Solicitudes', 'description': 'Solicitudes de instalación'},
        {'name': 'Equipos', 'description': 'Equipos de refrigeración'},
        {'name': 'Instalaciones', 'description': 'Instalaciones y agenda'},
        {'name': 'Servicios', 'description': 'Órdenes de trabajo'},
        {'name': 'Mantenimientos', 'description': 'Mantenimientos preventivos y correctivos'},
        {'name': 'Materiales', 'description': 'Materiales, repuestos e inventario'},
        {'name': 'Cotizaciones', 'description': 'Cotizaciones de instalación'},
        {'name': 'Pagos', 'description': 'Pagos y facturas'},
        {'name': 'Evidencias', 'description': 'Fotografías antes/después'},
        {'name': 'Notificaciones', 'description': 'Notificaciones del sistema'},
        {'name': 'Evaluaciones', 'description': 'Evaluación de la satisfacción del cliente'},
        {'name': 'Dashboard', 'description': 'Estadísticas y reportes'},
    ],
}
