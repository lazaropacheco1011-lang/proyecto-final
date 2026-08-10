"""Verificación puntual de B1 (escalada de rol en /me) y B2 (descuento de stock)."""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rest_framework.test import APIClient
from apps.almacen.models import Producto
from apps.tienda.models import Orden

PASS = FAIL = 0


def check(nombre, condicion, detalle=''):
    global PASS, FAIL
    if condicion:
        PASS += 1
        print(f'  [OK]   {nombre}')
    else:
        FAIL += 1
        print(f'  [FAIL] {nombre} {detalle}')


# --- B1: cliente intenta escalar rol vía /api/auth/me/ --------------------
client = APIClient()
uname = 'b1_user'
r = client.post('/api/auth/register/', {
    'username': uname, 'email': 'b1@example.com', 'password': 'ClaveSegura2026!',
    'first_name': 'B1', 'last_name': 'Test', 'role': 'cliente', 'documento': 'DOC-B1',
}, format='json')
if r.status_code != 201:
    r = client.post('/api/auth/login/', {'username': uname, 'password': 'ClaveSegura2026!'}, format='json')
    check('login cliente b1 (ya existía)', r.status_code == 200, r.content[:200])
else:
    check('registro cliente b1', True)
access = r.json().get('access', '')
client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')

r = client.patch('/api/auth/me/', {'role': 'administrador'}, format='json')
check('B1 PATCH /me role=administrador no cambia el rol', r.status_code in (400, 403, 405), r.content[:200])

r = client.get('/api/auth/me/')
check('B1 el rol no cambió', r.status_code == 200 and r.json()['user']['role'] == 'cliente', r.content[:200])

# --- B2: crear orden descuenta stock -------------------------------------
producto = Producto.objects.filter(stock__gt=5, precio__isnull=False).order_by('?').first()
if producto is None:
    check('B2 hay producto de prueba', False, 'sin productos con stock')
else:
    stock_before = producto.stock
    client_pub = APIClient()
    r = client_pub.post('/api/tienda/pagos/tarjeta/', {
        'nombre': 'Test Stock', 'email': 'stock@example.com', 'telefono': '8095551234',
        'direccion': 'Calle 1', 'ciudad': 'Santo Domingo',
        'items': [{'producto_id': producto.pk, 'cantidad': 2}],
        'tarjeta': {'numero': '4242424242424242', 'exp_mes': '12', 'exp_anio': '2030', 'cvv': '123'},
    }, format='json')
    check('B2 checkout tarjeta responde', r.status_code in (201, 402), r.content[:300])
    producto.refresh_from_db()
    check('B2 stock descontado 2 unidades', producto.stock == stock_before - 2,
          f'antes={stock_before} despues={producto.stock}')

    # cancelar la orden restaura el stock
    if r.status_code == 201 and r.json().get('orden'):
        numero = r.json()['orden']
        orden = Orden.objects.get(numero=numero)
        admin = APIClient()
        ar = admin.post('/api/auth/login/', {'username': 'admin', 'password': 'Refrimaste2026!'}, format='json')
        admin.credentials(HTTP_AUTHORIZATION=f"Bearer {ar.json()['access']}")
        cr = admin.patch(f'/api/tienda/ordenes/{orden.pk}/estado/', {'estado': 'cancelado'}, format='json')
        check('B2 cancelación de orden aceptada', cr.status_code == 200, cr.content[:200])
        producto.refresh_from_db()
        check('B2 stock restaurado tras cancelar', producto.stock == stock_before,
              f'antes={stock_before} despues={producto.stock}')

print(f'RESULTADO: {PASS} OK, {FAIL} FALLOS')
raise SystemExit(1 if FAIL else 0)
