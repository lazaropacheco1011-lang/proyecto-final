"""Verificación de B8-B16: endurecimiento de settings, throttling,
exposición de admin/docs y validación de subidas de imágenes."""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django

django.setup()

from django.conf import settings
from PIL import Image
from rest_framework.test import APIClient

from apps.materiales.models import Material
from apps.servicios.models import OrdenServicio

PASS = FAIL = 0


def env_true(name, default=False):
    return os.getenv(name, str(default)).lower() in ('1', 'true', 'yes', 'on')


def check(nombre, condicion, detalle=''):
    global PASS, FAIL
    if condicion:
        PASS += 1
        print(f'  [OK]   {nombre}')
    else:
        FAIL += 1
        print(f'  [FAIL] {nombre} {detalle}')


# --- B8-B12: defaults de configuración (según .env actual DEBUG=True) -----
check('B8 settings.DEBUG sigue config de entorno', settings.DEBUG == env_true('DEBUG'))
check('B12 SECURE_CONTENT_TYPE_NOSNIFF activo', settings.SECURE_CONTENT_TYPE_NOSNIFF is True)
check('B12 X_FRAME_OPTIONS DENY', settings.X_FRAME_OPTIONS == 'DENY')
check('B12 SECURE_REFERRER_POLICY definida', bool(settings.SECURE_REFERRER_POLICY))
check('B12 SECURE_HSTS_SECONDS entero >= 0', settings.SECURE_HSTS_SECONDS >= 0)

# --- B13: throttle en login (6 intentos -> el 6º 429) ----------------------
# Se limpia la caché para no arrastrar conteos de llamadas previas.
from django.core.cache import cache

cache.clear()
c = APIClient()
codigos = []
for _ in range(6):
    r = c.post('/api/auth/login/', {'username': 'noexiste', 'password': 'incorrecta'}, format='json')
    codigos.append(r.status_code)
check('B13 login admite intentos normales', codigos[0] == 400, codigos)
check('B13 login se limita tras 5 intentos', codigos[-1] == 429, codigos)

# --- B14/B15: admin y docs disponibles en desarrollo -----------------------
r = c.get('/api/docs/')
check('B15 /api/docs/ disponible en DEBUG', r.status_code == 200, r.status_code)
r = c.get('/admin/login/')
check('B14 /admin/ disponible en DEBUG', r.status_code == 200, r.status_code)

# --- B16: límite de tamaño en subidas de imágenes --------------------------
cache.clear()
admin = APIClient()
ar = admin.post('/api/auth/login/', {'username': 'admin', 'password': 'Refrimaste2026!'}, format='json')
check('B16 login admin', ar.status_code == 200, ar.content[:200])
admin.credentials(HTTP_AUTHORIZATION=f"Bearer {ar.json()['access']}")

mat = Material.objects.filter(codigo='MAT-VERIF-B7').first()
orden = OrdenServicio.objects.first()
check('B16 existe material/orden de referencia', mat is not None and orden is not None)

if mat is not None and orden is not None:
    buf = io.BytesIO()
    Image.new('RGB', (3000, 3000), (120, 80, 200)).save(buf, format='BMP')
    buf.seek(0)
    buf.name = 'grande.bmp'
    r = admin.post('/api/firmas/', {
        'content_type': 'servicios.ordenservicio',
        'object_id': orden.pk,
        'nombre': 'Prueba Tamaño',
        'documento': '001-1234567-8',
        'imagen': buf,
    }, format='multipart')
    check('B16 imagen >5MB rechazada', r.status_code == 400 and '5 MB' in r.content.decode('utf-8', 'ignore'),
          r.content[:300])

    buf = io.BytesIO()
    Image.new('RGB', (8, 8), (10, 20, 30)).save(buf, format='PNG')
    buf.seek(0)
    buf.name = 'firma_valida.png'
    r = admin.post('/api/firmas/', {
        'content_type': 'servicios.ordenservicio',
        'object_id': orden.pk,
        'nombre': 'Prueba Válida',
        'documento': '001-1234567-8',
        'imagen': buf,
    }, format='multipart')
    check('B16 imagen válida aceptada', r.status_code == 201, r.content[:300])
    if r.status_code == 201:
        admin.delete(f"/api/firmas/{r.json()['id']}/")

print(f'RESULTADO: {PASS} OK, {FAIL} FALLOS')
raise SystemExit(1 if FAIL else 0)
