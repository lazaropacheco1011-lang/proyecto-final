"""Verificación puntual de B3 (PII en orden pública), B4 (token PayPal),
B5 (pagos/facturas staff), B6 (evidencias/firmas staff) y B7 (materiales staff)."""
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django

django.setup()

from rest_framework.test import APIClient
from apps.almacen.models import Producto
from apps.clientes.models import Cliente
from apps.materiales.models import Material
from apps.servicios.models import OrdenServicio

PASS = FAIL = 0


def check(nombre, condicion, detalle=''):
    global PASS, FAIL
    if condicion:
        PASS += 1
        print(f'  [OK]   {nombre}')
    else:
        FAIL += 1
        print(f'  [FAIL] {nombre} {detalle}')


# --- setup: cliente y admin ------------------------------------------------
uname = 'b1_user'
client = APIClient()
r = client.post('/api/auth/login/', {'username': uname, 'password': 'ClaveSegura2026!'}, format='json')
if r.status_code != 200:
    r = client.post('/api/auth/register/', {
        'username': uname, 'email': 'b1@example.com', 'password': 'ClaveSegura2026!',
        'first_name': 'B1', 'last_name': 'Test', 'role': 'cliente', 'documento': 'DOC-B1',
    }, format='json')
    if r.status_code != 201:
        r = client.post('/api/auth/login/', {'username': uname, 'password': 'ClaveSegura2026!'}, format='json')
client.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")

admin = APIClient()
ar = admin.post('/api/auth/login/', {'username': 'admin', 'password': 'Refrimaste2026!'}, format='json')
admin.credentials(HTTP_AUTHORIZATION=f"Bearer {ar.json()['access']}")
check('login admin', ar.status_code == 200, ar.content[:200])

# --- B3: la orden pública no expone PII -----------------------------------
producto = Producto.objects.filter(stock__gt=5, precio__isnull=False).order_by('?').first()
check('B3 hay producto de prueba', producto is not None, 'sin productos con stock')
if producto is not None:
    pub = APIClient()
    r = pub.post('/api/tienda/pagos/tarjeta/', {
        'nombre': 'B3 Publico', 'email': 'b3@example.com', 'telefono': '8095551234',
        'direccion': 'Calle Secreta', 'ciudad': 'Santo Domingo',
        'items': [{'producto_id': producto.pk, 'cantidad': 1}],
        'tarjeta': {'numero': '4242424242424242', 'exp_mes': '12', 'exp_anio': '2030', 'cvv': '123'},
    }, format='json')
    check('B3 checkout tarjeta responde', r.status_code == 201, r.content[:300])
    if r.status_code == 201:
        numero = r.json()['orden']
        g = pub.get(f'/api/tienda/ordenes/p/{numero}/')
        data = g.json() if g.status_code == 200 else {}
        check('B3 endpoint público responde', g.status_code == 200, g.content[:300])
        for campo in ('nombre_cliente', 'email', 'direccion_entrega', 'ciudad_entrega'):
            check(f'B3 orden pública sin {campo}', campo not in data, str(sorted(data.keys())))
        pagos = data.get('pagos', [])
        check('B3 pagos incluidos', isinstance(pagos, list) and len(pagos) == 1, str(pagos)[:200])
        if pagos:
            p = pagos[0]
            check('B3 pago sin ultimos_digitos', 'ultimos_digitos' not in p, str(sorted(p.keys())))
            check('B3 pago sin marca_tarjeta', 'marca_tarjeta' not in p, str(sorted(p.keys())))
            check('B3 pago sin referencia proveedor', 'referencia' not in p, str(sorted(p.keys())))
            check('B3 pago con metodo_display', 'Tarjeta' in p.get('metodo_display', ''), str(p)[:200])
            check('B3 pago con estado_display', bool(p.get('estado_display')), str(p)[:200])

# --- B4: token PayPal aleatorio y validación ------------------------------
if producto is not None:
    pub = APIClient()
    r = pub.post('/api/tienda/pagos/paypal/crear/', {
        'nombre': 'B4 PayPal', 'email': 'b4@example.com', 'telefono': '8095551234',
        'direccion': 'Calle 1', 'ciudad': 'Santo Domingo',
        'items': [{'producto_id': producto.pk, 'cantidad': 1}],
    }, format='json')
    check('B4 crear pago PayPal responde', r.status_code == 201, r.content[:300])
    if r.status_code == 201:
        numero = r.json()['orden']
        url = r.json().get('aprobacion_url', '')
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
        token = (qs.get('token') or [''])[0]
        check('B4 token presente y aleatorio', len(token) >= 32, url)
        rr = pub.post('/api/tienda/pagos/paypal/aprobar/', {'orden': numero, 'token': 'token-incorrecto'}, format='json')
        check('B4 token incorrecto rechazado', rr.status_code == 400, rr.content[:200])
        ok = pub.post('/api/tienda/pagos/paypal/aprobar/', {'orden': numero, 'token': token}, format='json')
        check('B4 token correcto aprueba', ok.status_code == 200 and ok.json().get('estado_pago') == 'aprobado',
              ok.content[:200])

# --- B5: solo staff puede crear pagos/facturas -----------------------------
rr = client.post('/api/pagos/', {'monto': 100, 'metodo': 'efectivo', 'estado': 'pagado'}, format='json')
check('B5 cliente no crea pagos', rr.status_code == 403, rr.content[:200])
rr = client.post('/api/facturas/', {'cliente': 1, 'total': 100}, format='json')
check('B5 cliente no crea facturas', rr.status_code == 403, rr.content[:200])
rr = admin.get('/api/pagos/')
check('B5 admin lista pagos', rr.status_code == 200, rr.content[:200])
rr = admin.get('/api/facturas/')
check('B5 admin lista facturas', rr.status_code == 200, rr.content[:200])

# --- B6: evidencias/firmas solo staff --------------------------------------
rr = client.get('/api/evidencias/')
check('B6 cliente sin evidencias', rr.status_code == 403, rr.content[:200])
rr = client.get('/api/firmas/')
check('B6 cliente sin firmas', rr.status_code == 403, rr.content[:200])
rr = admin.get('/api/evidencias/')
check('B6 admin lista evidencias', rr.status_code == 200, rr.content[:200])
rr = admin.get('/api/firmas/')
check('B6 admin lista firmas', rr.status_code == 200, rr.content[:200])

# --- B7: materiales solo staff ---------------------------------------------
from apps.accounts.models import User
u = User.objects.get(username=uname)
cliente = Cliente.objects.filter(user=u).first()
if cliente is None:
    cliente, created = Cliente.objects.get_or_create(
        documento_numero='DOC-B1-CLIENTE',
        defaults={
            'user': u, 'nombre': 'B1', 'apellidos': 'Test',
            'email': 'b1@example.com', 'telefono': '8095551234',
        },
    )
    check('B7 perfil cliente creado', created)
else:
    check('B7 perfil cliente reutilizado', True)
orden = OrdenServicio.objects.filter(cliente=cliente).first()
if orden is None:
    from django.utils import timezone
    orden = OrdenServicio.objects.create(cliente=cliente, fecha=timezone.localdate())
mat, mat_created = Material.objects.get_or_create(
    codigo='MAT-VERIF-B7',
    defaults={
        'nombre': 'Material verificación B7', 'cantidad_disponible': 100,
        'precio': 10, 'unidad_medida': 'unidad',
    },
)
if mat_created:
    check('B7 material de prueba creado', True)

rr = client.post(f'/api/servicios/{orden.pk}/materiales/', {'material': mat.pk, 'cantidad': 1}, format='json')
check('B7 cliente no agrega materiales por acción', rr.status_code == 403, rr.content[:200])
rr = client.post('/api/servicios-materiales/', {
    'orden': orden.pk, 'material': mat.pk, 'cantidad': 1, 'precio_unitario': 10,
}, format='json')
check('B7 cliente no crea material utilizado', rr.status_code == 403, rr.content[:200])
stock = mat.cantidad_disponible
rr = admin.post('/api/servicios-materiales/', {
    'orden': orden.pk, 'material': mat.pk, 'cantidad': 1, 'precio_unitario': 10,
}, format='json')
check('B7 admin sí crea material utilizado', rr.status_code == 201, rr.content[:300])
if rr.status_code == 201:
    mat.refresh_from_db()
    check('B7 stock descontado por admin', mat.cantidad_disponible == stock - 1,
          f'antes={stock} despues={mat.cantidad_disponible}')
    item_id = rr.json().get('id')
    if item_id:
        dr = admin.delete(f'/api/servicios-materiales/{item_id}/')
        check('B7 admin elimina ítem y repone stock', dr.status_code == 204, dr.content[:200])
        mat.refresh_from_db()
        check('B7 stock repuesto tras eliminar', mat.cantidad_disponible == stock,
              f'antes={stock} despues={mat.cantidad_disponible}')

print(f'RESULTADO: {PASS} OK, {FAIL} FALLOS')
raise SystemExit(1 if FAIL else 0)
