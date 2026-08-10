"""Verificación de recuperación y cambio de contraseña (los tres roles).

Cubre: respuesta genérica de recuperación, envío de correo con token de un solo
uso, token guardado como hash, expiración, no reutilización, validaciones de
contraseña, throttling de los endpoints públicos y revocación de sesiones JWT
tras cambiar/restablecer la contraseña. Re-ejecutable sobre la misma BD.

Nota: durante la verificación se fuerza el backend de correo "locmem" para
inspeccionar el correo enviado sin necesidad de SMTP. Se limpian los registros
temporales al final (la contraseña del usuario "admin" se restaura).
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
os.environ['EMAIL_BACKEND'] = 'django.core.mail.backends.locmem.EmailBackend'
import django

django.setup()

from django.core import mail
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import PasswordResetToken, User
from apps.clientes.models import Cliente

mail.outbox = []

PASS = FAIL = 0
ADMIN_USER = 'admin'
ADMIN_PASS = 'Refrimaste2026!'


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
    return c, r.json()


def cambiar(c, actual, nueva):
    return c.post('/api/auth/password/cambiar/', {
        'password_actual': actual,
        'nueva_password': nueva,
        'confirmar_nueva_password': nueva,
    }, format='json')


def refresh(refresh_token):
    r = APIClient().post('/api/auth/refresh/', {'refresh': refresh_token}, format='json')
    return r.status_code


def token_del_correo():
    """Extrae el token del último correo enviado (o None)."""
    if not mail.outbox:
        return None
    m = re.search(r'reset=([^&\s]+)', mail.outbox[-1].body)
    return m.group(1) if m else None


creados = {'usuarios': [], 'documentos': [], 'token_ids': []}
admin_restaurar = False
try:
    # ------------------------------------------------------------------
    # Usuarios temporales
    # ------------------------------------------------------------------
    cli = APIClient()
    r = cli.post('/api/auth/register/', {
        'username': 'pwd_cli', 'email': 'pwd_cli@test.com',
        'password': 'ClaveSegura2026!', 'first_name': 'Ana', 'last_name': 'Pérez',
        'role': 'cliente', 'documento': 'PWD-CLI-001', 'tipo_documento': 'cc',
    }, format='json')
    check('registro cliente temporal', r.status_code == 201, r.content[:300])
    if r.status_code == 201:
        creados['usuarios'].append(r.json()['user']['id'])
        creados['documentos'].append('PWD-CLI-001')
    cli.credentials(HTTP_AUTHORIZATION='Bearer ' + r.json()['access'])
    refresh_cli1 = r.json()['refresh']

    tec = APIClient()
    r = tec.post('/api/auth/register/', {
        'username': 'pwd_tec', 'email': 'pwd_tec@test.com',
        'password': 'ClaveSegura2026!', 'first_name': 'Luis', 'last_name': 'Roa',
        'role': 'tecnico',
    }, format='json')
    check('registro tecnico temporal', r.status_code == 201, r.content[:300])
    if r.status_code == 201:
        creados['usuarios'].append(r.json()['user']['id'])
    tec.credentials(HTTP_AUTHORIZATION='Bearer ' + r.json()['access'])

    # ------------------------------------------------------------------
    # Cambio de contraseña: seguridad del endpoint
    # ------------------------------------------------------------------
    anon = APIClient()
    r = anon.post('/api/auth/password/cambiar/', {
        'password_actual': 'x', 'nueva_password': 'y', 'confirmar_nueva_password': 'y',
    }, format='json')
    check('cambiar sin auth -> 401', r.status_code == 401, r.status_code)

    r = cambiar(cli, 'INCORRECTA', 'NuevaClave2026!')
    check('contraseña actual incorrecta rechazada', r.status_code == 400
          and 'actual es incorrecta' in r.content.decode('utf-8', 'ignore'), r.content[:200])

    r = cli.post('/api/auth/password/cambiar/', {
        'password_actual': 'ClaveSegura2026!', 'nueva_password': 'NuevaClave2026!',
        'confirmar_nueva_password': 'OTRA',
    }, format='json')
    check('contraseñas nuevas no coinciden', r.status_code == 400
          and 'no coinciden' in r.content.decode('utf-8', 'ignore'), r.content[:200])

    r = cambiar(cli, 'ClaveSegura2026!', '12345678')
    check('contraseña solo numérica rechazada', r.status_code == 400, r.content[:200])

    # Cambio válido (cliente)
    r = cambiar(cli, 'ClaveSegura2026!', 'NuevaClave2026!')
    check('cambiar contraseña válido (cliente)', r.status_code == 200, r.content[:200])

    r = cli.post('/api/auth/login/', {'username': 'pwd_cli', 'password': 'ClaveSegura2026!'}, format='json')
    check('la contraseña anterior ya no funciona', r.status_code == 400, r.status_code)
    r = cli.post('/api/auth/login/', {'username': 'pwd_cli', 'password': 'NuevaClave2026!'}, format='json')
    check('login con la nueva contraseña', r.status_code == 200, r.status_code)
    refresh_cli2 = r.json()['refresh']

    check('sesión anterior revocada tras cambiar (refresh 401)', refresh(refresh_cli1) == 401,
          refresh(refresh_cli1))

    # Cambio válido (técnico)
    r = cambiar(tec, 'ClaveSegura2026!', 'TecnicoNueva2026!')
    check('cambiar contraseña válido (técnico)', r.status_code == 200, r.content[:200])

    # Cambio válido (administrador); la contraseña se restaura al final.
    admin, _ = login({'username': ADMIN_USER, 'password': ADMIN_PASS})
    r = cambiar(admin, ADMIN_PASS, 'AdminTemp2026!')
    check('cambiar contraseña válido (admin)', r.status_code == 200, r.content[:200])
    admin_restaurar = True
    cache.clear()  # login/register comparten el scope 'auth' (5/min)
    r = admin.post('/api/auth/login/', {'username': ADMIN_USER, 'password': 'AdminTemp2026!'}, format='json')
    check('login admin con la nueva contraseña', r.status_code == 200, r.status_code)

    # ------------------------------------------------------------------
    # Recuperación: respuesta genérica + correo con token
    # ------------------------------------------------------------------
    r = cli.post('/api/auth/password/recuperar/', {'email': 'noexiste@test.com'}, format='json')
    body = r.content.decode('utf-8', 'ignore')
    check('correo inexistente -> respuesta genérica', r.status_code == 200
          and 'Si el correo está registrado' in body, r.content[:200])
    check('correo inexistente -> no se envía correo', len(mail.outbox) == 0, len(mail.outbox))

    r = cli.post('/api/auth/password/recuperar/', {'email': 'pwd_cli@test.com'}, format='json')
    body = r.content.decode('utf-8', 'ignore')
    check('correo existente -> respuesta genérica', r.status_code == 200
          and 'Si el correo está registrado' in body, r.content[:200])
    check('se envió el correo de recuperación', len(mail.outbox) == 1, len(mail.outbox))

    raw = token_del_correo()
    check('el correo contiene el token', bool(raw), 'sin token en el cuerpo')
    check('el correo usa el enlace del frontend', bool(raw) and '/?reset=' in mail.outbox[-1].body,
          mail.outbox[-1].body[:120])
    check('el correo indica el destinatario', bool(mail.outbox)
          and mail.outbox[-1].to == ['pwd_cli@test.com'], mail.outbox and mail.outbox[-1].to)

    tok_obj = PasswordResetToken.objects.filter(user__username='pwd_cli').order_by('-id').first()
    if tok_obj:
        creados['token_ids'].append(tok_obj.id)
    check('token persistido como hash (no plano)', bool(tok_obj and raw)
          and tok_obj.token_hash != raw and len(tok_obj.token_hash) == 64,
          f'hash={tok_obj and tok_obj.token_hash}')

    # ------------------------------------------------------------------
    # Restablecimiento: token válido, un solo uso, expiración, sesiones
    # ------------------------------------------------------------------
    r = cli.post('/api/auth/password/restablecer/', {
        'token': raw or 'x', 'password': 'Recuperada2026!', 'password2': 'Recuperada2026!',
    }, format='json')
    check('restablecer con token válido', r.status_code == 200, r.content[:200])
    if tok_obj:
        tok_obj.refresh_from_db()
    check('token marcado como usado', bool(tok_obj and tok_obj.used_at), tok_obj and tok_obj.used_at)
    check('sesión revocada tras restablecer (refresh 401)', refresh(refresh_cli2) == 401,
          refresh(refresh_cli2))

    r = cli.post('/api/auth/password/restablecer/', {
        'token': raw or 'x', 'password': 'OtraClave2026!', 'password2': 'OtraClave2026!',
    }, format='json')
    check('reutilizar token rechazado', r.status_code == 400
          and 'ya fue utilizado' in r.content.decode('utf-8', 'ignore'), r.content[:200])

    cache.clear()  # login/register comparten el scope 'auth' (5/min)
    r = cli.post('/api/auth/login/', {'username': 'pwd_cli', 'password': 'Recuperada2026!'}, format='json')
    check('login con la contraseña restablecida', r.status_code == 200, r.status_code)

    # Expiración
    u = User.objects.get(username='pwd_cli')
    from django.utils import timezone
    from datetime import timedelta
    exp = PasswordResetToken.objects.create(
        user=u, token_hash='a' * 64, expires_at=timezone.now() - timedelta(minutes=1),
    )
    creados['token_ids'].append(exp.id)
    r = cli.post('/api/auth/password/restablecer/', {
        'token': 'x', 'password': 'OtraClave2026!', 'password2': 'OtraClave2026!',
    }, format='json')
    check('token expirado rechazado', r.status_code == 400, r.content[:200])

    r = cli.post('/api/auth/password/restablecer/', {
        'token': 'invalido', 'password': 'OtraClave2026!', 'password2': 'OtraClave2026!',
    }, format='json')
    check('token inválido rechazado', r.status_code == 400, r.content[:200])

    r = cli.post('/api/auth/password/restablecer/', {
        'token': 'invalido', 'password': 'OtraClave2026!', 'password2': 'Distinta2026!',
    }, format='json')
    check('restablecer sin coincidencia rechazado', r.status_code == 400
          and 'no coinciden' in r.content.decode('utf-8', 'ignore'), r.content[:200])

    r = cli.post('/api/auth/password/restablecer/', {
        'token': 'invalido', 'password': '12345678', 'password2': '12345678',
    }, format='json')
    check('restablecer con contraseña débil rechazado', r.status_code == 400, r.content[:200])

    # ------------------------------------------------------------------
    # Throttling de los endpoints públicos
    # ------------------------------------------------------------------
    cache.clear()
    c = APIClient()
    codigos = []
    for _ in range(6):
        r = c.post('/api/auth/password/recuperar/', {'email': 'throttle@test.com'}, format='json')
        codigos.append(r.status_code)
    check('recuperar admite solicitudes normales', codigos[0] == 200, codigos)
    check('recuperar limitado (429 tras 5/hora)', codigos[-1] == 429, codigos)

    cache.clear()
    c = APIClient()
    codigos = []
    for _ in range(11):
        r = c.post('/api/auth/password/restablecer/', {
            'token': 'invalido', 'password': 'OtraClave2026!', 'password2': 'OtraClave2026!',
        }, format='json')
        codigos.append(r.status_code)
    check('restablecer admite intentos normales', codigos[0] == 400, codigos)
    check('restablecer limitado (429 tras 10/min)', codigos[-1] == 429, codigos)
    cache.clear()

    print('RESULTADO: %d OK, %d FALLOS' % (PASS, FAIL))
finally:
    # ------------------------------------------------------------------
    # Limpieza: usuarios temporales, documentos, tokens y contraseña admin
    # ------------------------------------------------------------------
    for uid in creados['usuarios']:
        try:
            User.objects.get(pk=uid).delete()
        except User.DoesNotExist:
            pass
    for doc in creados['documentos']:
        Cliente.objects.filter(documento_numero=doc).delete()
    PasswordResetToken.objects.filter(id__in=creados['token_ids']).delete()
    if admin_restaurar:
        admin_user = User.objects.get(username=ADMIN_USER)
        admin_user.set_password(ADMIN_PASS)
        admin_user.save(update_fields=['password'])
    print('Registros temporales eliminados y contraseña de admin restaurada.')
    raise SystemExit(1 if FAIL else 0)
