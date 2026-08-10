"""Verificación de la sección "Mi perfil": foto de perfil + datos por rol + permisos.

Crea usuarios temporales, prueba subir/reemplazar/eliminar foto, actualizar datos
de cliente/técnico/administrador, validaciones de formato/tamaño y que nadie pueda
modificar el perfil de otro usuario. Al final elimina los registros y archivos
temporales creados (re-ejecutable sobre la misma BD).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django

django.setup()

from io import BytesIO

from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.clientes.models import Cliente
from apps.core.permissions import CLIENTE, TECNICO

PASS = FAIL = 0


def check(nombre, condicion, detalle=''):
    global PASS, FAIL
    if condicion:
        PASS += 1
        print(f'  [OK]   {nombre}')
    else:
        FAIL += 1
        print(f'  [FAIL] {nombre} {detalle}')


def login(creds):
    c = APIClient()
    r = c.post('/api/auth/login/', creds, format='json')
    assert r.status_code == 200, r.content[:300]
    c.credentials(HTTP_AUTHORIZATION='Bearer ' + r.json()['access'])
    return c


def foto_png(color=(2, 132, 199)):
    img = BytesIO()
    Image.new('RGB', (48, 48), color).save(img, 'PNG')
    img.name = 'perfil_test.png'
    img.seek(0)
    return img


creados = {'usuarios': [], 'fotos': [], 'documentos': []}
try:
    # ------------------------------------------------------------------
    # Usuarios temporales
    # ------------------------------------------------------------------
    admin = login({'username': 'admin', 'password': 'Refrimaste2026!'})

    cli = APIClient()
    r = cli.post('/api/auth/register/', {
        'username': 'perfil_cliente', 'email': 'perfil_cliente@test.com',
        'password': 'ClaveSegura2026!', 'first_name': 'Ana', 'last_name': 'Pérez',
        'role': 'cliente', 'documento': 'PERFIL-CLI-001', 'tipo_documento': 'cc',
    }, format='json')
    check('registro cliente temporal', r.status_code == 201, r.content[:300])
    if r.status_code == 201:
        creados['usuarios'].append(r.json()['user']['id'])
        creados['documentos'].append('PERFIL-CLI-001')
    cli.credentials(HTTP_AUTHORIZATION='Bearer ' + r.json()['access'])

    tec = APIClient()
    r = tec.post('/api/auth/register/', {
        'username': 'perfil_tecnico', 'email': 'perfil_tecnico@test.com',
        'password': 'ClaveSegura2026!', 'first_name': 'Luis', 'last_name': 'Roa',
        'role': 'tecnico',
    }, format='json')
    check('registro tecnico temporal', r.status_code == 201, r.content[:300])
    if r.status_code == 201:
        creados['usuarios'].append(r.json()['user']['id'])
    tec.credentials(HTTP_AUTHORIZATION='Bearer ' + r.json()['access'])

    # ------------------------------------------------------------------
    # GET perfil según rol
    # ------------------------------------------------------------------
    r = cli.get('/api/auth/me/perfil/')
    p = r.json().get('perfil', {})
    check('perfil cliente GET', r.status_code == 200 and p.get('role') == CLIENTE, r.content[:200])
    check('perfil cliente incluye nombre/apellidos', p.get('nombre') == 'Ana' and p.get('apellidos') == 'Pérez', p)

    r = tec.get('/api/auth/me/perfil/')
    p = r.json().get('perfil', {})
    check('perfil tecnico GET', r.status_code == 200 and p.get('role') == TECNICO, r.content[:200])
    check('perfil tecnico incluye especialidad', 'especialidad' in p, p)

    r = admin.get('/api/auth/me/perfil/')
    check('perfil admin GET', r.status_code == 200 and r.json()['perfil']['role'] == 'administrador', r.content[:200])

    # ------------------------------------------------------------------
    # Actualización de datos personales por rol
    # ------------------------------------------------------------------
    r = cli.patch('/api/auth/me/perfil/', {
        'nombre': 'Ana María', 'apellidos': 'Pérez Gómez', 'telefono': '8095550101',
        'ciudad': 'Santo Domingo', 'email': 'perfil_cliente@test.com',
    }, format='json')
    p = r.json().get('perfil', {})
    check('cliente actualiza datos', r.status_code == 200 and p.get('nombre') == 'Ana María'
          and p.get('ciudad') == 'Santo Domingo', r.content[:200])
    check('cliente nombre visible en cuenta', r.json()['perfil']['full_name'] == 'Ana María Pérez Gómez', p.get('full_name'))

    r = tec.patch('/api/auth/me/perfil/', {
        'especialidad': 'Cuartos fríos', 'direccion': 'Av. Central 12', 'telefono': '8095550202',
    }, format='json')
    p = r.json().get('perfil', {})
    check('tecnico actualiza datos', r.status_code == 200 and p.get('especialidad') == 'Cuartos fríos'
          and p.get('direccion') == 'Av. Central 12', r.content[:200])

    r = admin.patch('/api/auth/me/perfil/', {
        'first_name': 'Carlos', 'last_name': 'Administrador', 'phone': '8095550303',
    }, format='json')
    check('admin actualiza datos', r.status_code == 200 and r.json()['perfil']['phone'] == '8095550303', r.content[:200])

    # ------------------------------------------------------------------
    # Foto de perfil: subir, verificar, reemplazar, eliminar
    # ------------------------------------------------------------------
    r = cli.post('/api/auth/me/foto/', {'foto': foto_png()}, format='multipart')
    photo1 = r.json().get('user', {}).get('photo')
    check('subir foto', r.status_code == 200 and bool(photo1), r.content[:200])

    archivo = photo1.replace('/media/', '')
    ruta = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'media', archivo)
    check('foto guardada en disco', os.path.isfile(ruta), f'ruta={ruta}')

    r = cli.get('/api/auth/me/')
    check('foto visible en /me (persistencia)', r.json()['user'].get('photo') == photo1, r.content[:200])

    r = cli.get('/api/auth/me/perfil/')
    check('foto visible en perfil', r.json()['perfil'].get('photo') == photo1, r.content[:200])

    r = cli.post('/api/auth/me/foto/', {'foto': foto_png((220, 38, 38))}, format='multipart')
    photo2 = r.json().get('user', {}).get('photo')
    check('reemplazar foto', r.status_code == 200 and bool(photo2) and photo2 != photo1, r.content[:200])

    r = cli.post('/api/auth/me/foto/', {'eliminar': True}, format='json')
    check('eliminar foto', r.status_code == 200 and r.json()['user'].get('photo') is None, r.content[:200])
    r = cli.get('/api/auth/me/')
    check('foto eliminada persiste', r.json()['user'].get('photo') is None, r.content[:200])

    # ------------------------------------------------------------------
    # Validaciones: formato y tamaño
    # ------------------------------------------------------------------
    txt = BytesIO(b'no soy una imagen')
    txt.name = 'malo.txt'
    r = cli.post('/api/auth/me/foto/', {'foto': txt}, format='multipart')
    check('formato inválido rechazado', r.status_code == 400, r.content[:200])

    grande = BytesIO(b'\x00' * (6 * 1024 * 1024))
    grande.name = 'grande.png'
    r = cli.post('/api/auth/me/foto/', {'foto': grande}, format='multipart')
    check('imagen >5MB rechazada', r.status_code == 400, r.content[:200])

    r = cli.post('/api/auth/me/foto/', {})
    check('sin archivo rechazado', r.status_code == 400, r.content[:200])

    # ------------------------------------------------------------------
    # Seguridad: nadie modifica el perfil de otro ni cambia su rol
    # ------------------------------------------------------------------
    r = cli.patch('/api/auth/me/perfil/', {'role': 'administrador'}, format='json')
    check('cliente no cambia su rol', r.status_code in (400, 403), r.content[:200])

    r = tec.patch('/api/auth/me/perfil/', {'role': 'administrador', 'is_active': False}, format='json')
    check('tecnico no cambia rol ni is_active', r.status_code in (400, 403), r.content[:200])

    admin_id = User.objects.get(username='admin').id
    r = cli.patch(f'/api/usuarios/{admin_id}/', {'first_name': 'HACK'}, format='json')
    check('cliente no edita otro usuario', r.status_code == 403, r.content[:200])

    r = tec.patch(f'/api/usuarios/{admin_id}/', {'first_name': 'HACK'}, format='json')
    check('tecnico no edita otro usuario', r.status_code == 403, r.content[:200])

    cli_obj = Cliente.objects.get(user__username='perfil_cliente')
    r = cli.patch(f'/api/clientes/{cli_obj.pk}/', {'nombre': 'HACK'}, format='json')
    check('cliente edita su propio cliente', r.status_code == 200, r.content[:200])
    cli_obj.refresh_from_db()
    check('cliente editado correctamente', cli_obj.nombre == 'HACK', cli_obj.nombre)

    # Email duplicado rechazado
    r = cli.patch('/api/auth/me/perfil/', {'email': 'perfil_tecnico@test.com'}, format='json')
    check('email duplicado rechazado', r.status_code == 400, r.content[:200])

    print('RESULTADO: %d OK, %d FALLOS' % (PASS, FAIL))
finally:
    # ------------------------------------------------------------------
    # Limpieza: usuarios temporales, perfiles y archivos de foto
    # ------------------------------------------------------------------
    for uid in creados['usuarios']:
        try:
            u = User.objects.get(pk=uid)
            if u.photo:
                u.photo.delete(save=False)
            u.delete()
        except User.DoesNotExist:
            pass
    # El perfil Cliente puede quedar huérfano (user nullable): eliminarlo por documento.
    from apps.clientes.models import Cliente as ClienteModel
    for doc in creados['documentos']:
        ClienteModel.objects.filter(documento_numero=doc).delete()
    print('Registros temporales eliminados.')
    raise SystemExit(1 if FAIL else 0)
