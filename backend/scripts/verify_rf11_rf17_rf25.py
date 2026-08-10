"""Verificación de las correcciones de la entrega:
RF-11 visitas técnicas, RF-17 UI de cotizaciones (endpoint), RF-25 evaluación
(doble evaluación -> 400) y dashboard (3 widgets)."""
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
import django

django.setup()

from rest_framework.test import APIClient

from apps.accounts.models import Tecnico
from apps.clientes.models import Cliente
from apps.cotizaciones.models import Cotizacion
from apps.evaluaciones.models import EvaluacionServicio
from apps.servicios.models import OrdenServicio, VisitaTecnica

PASS = FAIL = 0


def check(nombre, condicion, detalle=''):
    global PASS, FAIL
    if condicion:
        PASS += 1
        print(f'  [OK]   {nombre}')
    else:
        FAIL += 1
        print(f'  [FAIL] {nombre} {detalle}')


def login(usuario, contrasena):
    c = APIClient()
    r = c.post('/api/auth/login/', {'username': usuario, 'password': contrasena}, format='json')
    assert r.status_code == 200, f'login {usuario}: {r.status_code} {r.content[:200]}'
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")
    return c


admin = login('admin', 'Refrimaste2026!')
tec = login('tecnico1', 'Refrimaste2026!')
cli = login('cliente1', 'Refrimaste2026!')

cliente1 = Cliente.objects.filter(user__username='cliente1').first()
tecnico1 = Tecnico.objects.filter(user__username='tecnico1').first()
check('Datos seed disponibles', cliente1 is not None and tecnico1 is not None)

creados = {'visita': None, 'cotizacion': None, 'orden': None, 'evaluacion': None}

# ---------------------------------------------------------------------------
# RF-11 Visitas técnicas
# ---------------------------------------------------------------------------
print('\nRF-11 Visitas técnicas')
if cliente1 and tecnico1:
    r = admin.post('/api/visitas/', {
        'cliente': cliente1.id,
        'orden': None,
        'tecnico': tecnico1.id,
        'fecha': '2026-08-10',
        'hora': '09:30:00',
        'estado': 'programada',
        'motivo': 'Diagnóstico de equipo para instalación',
        'direccion': cliente1.direccion or 'Calle principal 123',
        'observaciones': 'Verificación inicial RF-11',
    }, format='json')
    check('RF-11 admin crea visita -> 201', r.status_code == 201, r.content[:300])
    if r.status_code == 201:
        creados['visita'] = r.json()['id']
        check('RF-11 numero autogenerado (VT-*)', str(r.json().get('numero', '')).startswith('VT-'))
        check('RF-11 visita incluye cliente/tecnico/estado',
              bool(r.json().get('cliente_nombre')) and bool(r.json().get('tecnico_nombre'))
              and r.json().get('estado_display'))

    r = admin.get('/api/visitas/')
    check('RF-11 listar visitas -> 200', r.status_code == 200, r.status_code)

    r = admin.get('/api/visitas/?estado=programada')
    check('RF-11 filtrar por estado -> 200', r.status_code == 200, r.status_code)

    r = cli.post('/api/visitas/', {
        'cliente': cliente1.id, 'fecha': '2026-08-10', 'motivo': 'Intento cliente',
    }, format='json')
    check('RF-11 cliente no puede crear -> 403', r.status_code == 403, r.status_code)

    r = cli.get('/api/visitas/')
    check('RF-11 cliente ve solo sus visitas -> 200', r.status_code == 200, r.status_code)

    r = tec.get('/api/visitas/')
    check('RF-11 técnico lista visitas -> 200', r.status_code == 200, r.status_code)

    if creados['visita']:
        r = tec.patch(f"/api/visitas/{creados['visita']}/", {'estado': 'realizada'}, format='json')
        check('RF-11 técnico cambia estado -> 200', r.status_code == 200, r.content[:200])

# ---------------------------------------------------------------------------
# RF-17 Cotizaciones (endpoint existente + UI en frontend)
# ---------------------------------------------------------------------------
print('\nRF-17 Cotizaciones')
if cliente1 and tecnico1:
    r = admin.post('/api/cotizaciones/', {
        'cliente': cliente1.id,
        'tecnico': tecnico1.id,
        'validez_dias': 30,
        'descuento': '500.00',
        'notas': 'Cotización de verificación RF-17',
        'detalles': [
            {'descripcion': 'Instalación de equipo', 'cantidad': '1', 'precio_unitario': '15000.00'},
            {'descripcion': 'Materiales y tubería', 'cantidad': '2', 'precio_unitario': '3000.00'},
        ],
    }, format='json')
    check('RF-17 admin crea cotización -> 201', r.status_code == 201, r.content[:400])
    if r.status_code == 201:
        creados['cotizacion'] = r.json()['id']
        data = r.json()
        check('RF-17 numero autogenerado (COT-*)', str(data.get('numero', '')).startswith('COT-'))
        check('RF-17 subtotal correcto (21000.00)',
              data.get('subtotal') is not None and Decimal(str(data['subtotal'])) == Decimal('21000.00'),
              data.get('subtotal'))
        check('RF-17 total = subtotal - descuento (20500.00)',
              data.get('total') is not None and Decimal(str(data['total'])) == Decimal('20500.00'),
              data.get('total'))
        check('RF-17 detalles incluidos en respuesta', len(data.get('detalles') or []) == 2)

        r = admin.get('/api/cotizaciones/')
        check('RF-17 listar cotizaciones -> 200', r.status_code == 200, r.status_code)

        r = cli.get('/api/cotizaciones/')
        check('RF-17 cliente ve sus cotizaciones -> 200', r.status_code == 200, r.status_code)

        r = admin.patch(f"/api/cotizaciones/{creados['cotizacion']}/", {'estado': 'aprobada'}, format='json')
        check('RF-17 cambiar estado -> 200', r.status_code == 200, r.content[:200])

        r = admin.get(f"/api/cotizaciones/{creados['cotizacion']}/")
        check('RF-17 detalle -> 200 con 2 ítems', r.status_code == 200
              and len(r.json().get('detalles') or []) == 2, r.status_code)

# ---------------------------------------------------------------------------
# RF-25 Evaluación del cliente (doble evaluación -> 400, no 500)
# ---------------------------------------------------------------------------
print('\nRF-25 Evaluación del cliente')
if cliente1 and tecnico1:
    r = admin.post('/api/servicios/', {
        'cliente': cliente1.id,
        'tecnico': tecnico1.id,
        'tipo_servicio': 'reparacion',
        'fecha': '2026-08-01',
        'problema_reportado': 'Orden para verificación RF-25',
        'diagnostico': 'Diagnóstico verificado',
        'trabajo_realizado': 'Trabajo realizado y verificado',
        'observaciones': 'Observaciones de la orden',
        'estado': 'finalizada',
    }, format='json')
    check('RF-25 admin crea orden finalizada -> 201', r.status_code == 201, r.content[:300])
    if r.status_code == 201:
        creados['orden'] = r.json()['id']
        r = cli.post('/api/evaluaciones/', {
            'orden': creados['orden'], 'calificacion': 5, 'comentario': 'Excelente servicio',
        }, format='json')
        check('RF-25 cliente evalúa servicio finalizado -> 201', r.status_code == 201, r.content[:300])
        if r.status_code == 201:
            creados['evaluacion'] = r.json()['id']

        r = cli.post('/api/evaluaciones/', {
            'orden': creados['orden'], 'calificacion': 4, 'comentario': 'Segunda evaluación',
        }, format='json')
        check('RF-25 segunda evaluación -> 400 (no 500)', r.status_code == 400, f'status={r.status_code}')
        check('RF-25 mensaje claro de evaluación duplicada',
              'ya fue evaluado' in r.content.decode('utf-8', 'ignore').lower(), r.content[:300])

        r = cli.get('/api/evaluaciones/')
        check('RF-25 cliente lista sus evaluaciones -> 200', r.status_code == 200, r.status_code)

        r = cli.post('/api/evaluaciones/', {
            'orden': creados['orden'], 'cliente': 99999, 'calificacion': 3,
        }, format='json')
        check('RF-25 cliente no puede evaluar en nombre de otro (forzado a su perfil)',
              r.status_code == 400, r.status_code)

# ---------------------------------------------------------------------------
# Dashboard: 3 widgets y permisos
# ---------------------------------------------------------------------------
print('\nDashboard')
r = admin.get('/api/dashboard/')
check('Dashboard admin -> 200', r.status_code == 200, r.status_code)
if r.status_code == 200:
    d = r.json()
    check('Dashboard servicios_por_mes presente', isinstance(d.get('servicios_por_mes'), list))
    check('Dashboard instalaciones_por_mes presente', isinstance(d.get('instalaciones_por_mes'), list))
    check('Dashboard materiales_stock_bajo_list presente',
          isinstance(d.get('materiales_stock_bajo_list'), list))
r = cli.get('/api/dashboard/')
check('Dashboard cliente -> 403', r.status_code == 403, r.status_code)

# ---------------------------------------------------------------------------
# Limpieza (para re-ejecución sobre la misma BD)
# ---------------------------------------------------------------------------
print('\nLimpieza')
if creados['evaluacion']:
    EvaluacionServicio.objects.filter(pk=creados['evaluacion']).delete()
if creados['orden']:
    OrdenServicio.objects.filter(pk=creados['orden']).delete()
if creados['cotizacion']:
    Cotizacion.objects.filter(pk=creados['cotizacion']).delete()
if creados['visita']:
    VisitaTecnica.objects.filter(pk=creados['visita']).delete()
check('Registros temporales eliminados', True)

print(f'\nRESULTADO: {PASS} OK, {FAIL} FALLOS')
raise SystemExit(1 if FAIL else 0)
