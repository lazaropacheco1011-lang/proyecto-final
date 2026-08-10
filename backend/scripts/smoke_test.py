"""
Smoke test integral de la API de REFRIMASTE.
Ejecutar: python manage.py shell < scripts/smoke_test.py
"""
import json
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rest_framework.test import APIClient  # noqa: E402

PASS = 0
FAIL = 0
RESULTS = []


def check(nombre, condicion, detalle=''):
    global PASS, FAIL
    if condicion:
        PASS += 1
        print(f'  [OK]   {nombre}')
    else:
        FAIL += 1
        print(f'  [FAIL] {nombre} {detalle}')
    RESULTS.append((nombre, bool(condicion)))


def show(resp):
    try:
        return json.dumps(resp.json(), ensure_ascii=False)[:300]
    except Exception:
        return str(resp.content[:300])


print('=' * 70)
print('REFRIMASTE - Smoke test de la API')
print('=' * 70)

client = APIClient()

# ---------------------------------------------------------------------------
print('\n1. Autenticación')
# ---------------------------------------------------------------------------
r = client.post('/api/auth/login/', {
    'username': 'admin', 'password': 'Refrimaste2026!',
}, format='json')
check('login admin', r.status_code == 200, show(r))
tokens = r.json()
ACCESS = tokens.get('access', '')
REFRESH = tokens.get('refresh', '')
check('login devuelve access y refresh', bool(ACCESS and REFRESH))

client.credentials(HTTP_AUTHORIZATION=f'Bearer {ACCESS}')

r = client.get('/api/auth/me/')
check('GET /api/auth/me/', r.status_code == 200 and r.json()['user']['username'] == 'admin', show(r))

r = client.post('/api/auth/refresh/', {'refresh': REFRESH}, format='json')
check('POST /api/auth/refresh/', r.status_code == 200, show(r))
ACCESS = r.json().get('access', ACCESS)
REFRESH = r.json().get('refresh', REFRESH)
client.credentials(HTTP_AUTHORIZATION=f'Bearer {ACCESS}')

r = client.post('/api/auth/logout/', {'refresh': REFRESH}, format='json')
check('POST /api/auth/logout/', r.status_code == 200, show(r))

# Registro público
r = client.post('/api/auth/register/', {
    'username': 'nuevocliente',
    'email': 'nuevo@mail.com',
    'password': 'Password123!',
    'first_name': 'Nuevo',
    'last_name': 'Cliente',
    'role': 'cliente',
    'nombre': 'Nuevo',
    'apellidos': 'Cliente',
    'documento': '999888777',
}, format='json')
check('POST /api/auth/register/ (cliente)', r.status_code == 201, show(r))

# ---------------------------------------------------------------------------
print('\n2. Usuarios y roles')
# ---------------------------------------------------------------------------
r = client.get('/api/usuarios/')
check('GET /api/usuarios/ (admin)', r.status_code == 200, show(r))

r = client.get('/api/usuarios/roles/')
check('GET /api/usuarios/roles/', r.status_code == 200 and len(r.json()) == 5, show(r))

r = client.get('/api/tecnicos/')
check('GET /api/tecnicos/', r.status_code == 200 and len(r.json().get('results', r.json())) >= 2, show(r))

r = client.post('/api/usuarios/', {
    'username': 'tecnico3', 'email': 't3@mail.com', 'password': 'Password123!',
    'first_name': 'Luis', 'last_name': 'Pérez', 'role': 'tecnico',
}, format='json')
check('POST /api/usuarios/ (crear técnico)', r.status_code == 201, show(r))

# ---------------------------------------------------------------------------
print('\n3. Clientes y direcciones')
# ---------------------------------------------------------------------------
r = client.post('/api/clientes/', {
    'tipo': 'persona', 'nombre': 'Ana', 'apellidos': 'Martínez',
    'tipo_documento': 'cc', 'documento_numero': '555666777',
    'email': 'ana@mail.com', 'telefono': '8095556667',
    'direccion': 'Av. 27 de Febrero # 45', 'ciudad': 'Santiago de los Caballeros',
}, format='json')
check('POST /api/clientes/', r.status_code == 201, show(r))
cliente_id = r.json().get('id')

r = client.patch(f'/api/clientes/{cliente_id}/', {'telefono': '3201112222'}, format='json')
check('PATCH /api/clientes/{id}/', r.status_code == 200 and r.json()['telefono'] == '3201112222', show(r))

r = client.get('/api/clientes/', {'search': 'María'})
check('GET /api/clientes/?search=', r.status_code == 200, show(r))

r = client.post('/api/direcciones/', {
    'cliente': cliente_id, 'etiqueta': 'Oficina', 'direccion': 'Av. Salvador Estrella Sadhalá', 'ciudad': 'Santiago de los Caballeros',
}, format='json')
check('POST /api/direcciones/', r.status_code == 201, show(r))

# ---------------------------------------------------------------------------
print('\n4. Equipos')
# ---------------------------------------------------------------------------
r = client.post('/api/tipos-equipo/', {'nombre': 'Chiller'}, format='json')
check('POST /api/tipos-equipo/', r.status_code == 201, show(r))
tipo_id = r.json().get('id')

r = client.post('/api/equipos/', {
    'cliente': cliente_id, 'tipo': tipo_id, 'marca': 'Daikin',
    'modelo': 'X-500', 'numero_serie': 'DK-500-001', 'capacidad': '5 HP',
    'refrigerante': 'R-410A', 'estado': 'disponible',
}, format='json')
check('POST /api/equipos/', r.status_code == 201, show(r))
equipo_id = r.json().get('id')

r = client.patch(f'/api/equipos/{equipo_id}/', {'estado': 'instalado'}, format='json')
check('PATCH /api/equipos/{id}/', r.status_code == 200, show(r))

r = client.get('/api/equipos/', {'refrigerante': 'R-410A'})
check('GET /api/equipos/?refrigerante=', r.status_code == 200, show(r))

# ---------------------------------------------------------------------------
print('\n5. Solicitudes e instalaciones')
# ---------------------------------------------------------------------------
r = client.post('/api/solicitudes/', {
    'cliente': cliente_id, 'tipo_equipo_solicitado': 'Chiller 5 HP',
    'descripcion': 'Instalación en bodega', 'prioridad': 'alta',
}, format='json')
check('POST /api/solicitudes/', r.status_code == 201, show(r))
solicitud_id = r.json().get('id')

tecnico = client.get('/api/tecnicos/').json().get('results', [])
tecnico_id = tecnico[0]['id'] if tecnico else None

r = client.post('/api/instalaciones/', {
    'cliente': cliente_id, 'equipo': equipo_id, 'tecnico': tecnico_id,
    'solicitud': solicitud_id, 'fecha_programada': '2026-08-10T09:00:00',
    'prioridad': 'alta', 'direccion': 'Av. 27 de Febrero # 45', 'ciudad': 'Santiago de los Caballeros',
    'estado': 'asignada',
}, format='json')
check('POST /api/instalaciones/', r.status_code == 201, show(r))
instalacion_id = r.json().get('id')

r = client.get('/api/instalaciones/agenda/')
check('GET /api/instalaciones/agenda/', r.status_code == 200, show(r))

r = client.get('/api/instalaciones/proximos/')
check('GET /api/instalaciones/proximos/', r.status_code == 200, show(r))

# RN-03: mismo técnico en el mismo horario
r = client.post('/api/instalaciones/', {
    'cliente': cliente_id, 'tecnico': tecnico_id,
    'fecha_programada': '2026-08-10T09:30:00',
    'prioridad': 'media', 'direccion': 'Otra dirección', 'estado': 'pendiente',
}, format='json')
check('RN-03 conflicto de horario rechazado', r.status_code == 400, show(r))

# ---------------------------------------------------------------------------
print('\n6. Órdenes de servicio')
# ---------------------------------------------------------------------------
r = client.post('/api/servicios/', {
    'cliente': cliente_id, 'equipo': equipo_id, 'tipo_servicio': 'reparacion',
    'fecha': '2026-08-02', 'problema_reportado': 'No enfría',
    'estado': 'pendiente',
}, format='json')
check('POST /api/servicios/', r.status_code == 201, show(r))
orden_id = r.json().get('id')

# RN-02: asignar sin técnico debe fallar
r = client.patch(f'/api/servicios/{orden_id}/', {'estado': 'asignada'}, format='json')
check('RN-02 asignar sin técnico rechazado', r.status_code == 400, show(r))

# Asignar técnico correctamente
r = client.patch(f'/api/servicios/{orden_id}/', {'estado': 'asignada', 'tecnico': tecnico_id}, format='json')
check('PATCH orden asignada con técnico', r.status_code == 200, show(r))

# RN-04: finalizar sin diagnóstico/trabajo debe fallar
r = client.patch(f'/api/servicios/{orden_id}/', {'estado': 'finalizada'}, format='json')
check('RN-04 finalizar sin datos rechazado', r.status_code == 400, show(r))

# Avanzar a en_proceso
r = client.patch(f'/api/servicios/{orden_id}/', {'estado': 'en_proceso'}, format='json')
check('PATCH orden en_proceso', r.status_code == 200, show(r))

# RN-06: materiales descontan inventario
r = client.get('/api/materiales/', {'search': 'R-410A'})
check('GET /api/materiales/?search=', r.status_code == 200, show(r))
material = r.json().get('results', [{}])[0]
material_id = material.get('id')
stock_inicial = float(material.get('cantidad_disponible', 0))

r = client.post(f'/api/servicios/{orden_id}/materiales/', {
    'material': material_id, 'cantidad': 2, 'precio_unitario': 25000,
}, format='json')
check('POST /api/servicios/{id}/materiales/', r.status_code == 201, show(r))

r = client.get(f'/api/materiales/{material_id}/')
stock_nuevo = float(r.json().get('cantidad_disponible', 0)) if r.status_code == 200 else -999
check('RN-06 inventario descontado', stock_nuevo == stock_inicial - 2, show(r))

# RN-06: cantidad mayor al inventario debe fallar
r = client.post(f'/api/servicios/{orden_id}/materiales/', {
    'material': material_id, 'cantidad': 99999, 'precio_unitario': 1,
}, format='json')
check('RN-06 inventario insuficiente rechazado', r.status_code == 400, show(r))

# Finalizar correctamente (RN-04)
r = client.patch(f'/api/servicios/{orden_id}/', {
    'estado': 'finalizada', 'diagnostico': 'Compresor dañado',
    'trabajo_realizado': 'Reemplazo de compresor', 'observaciones': 'Servicio completado',
}, format='json')
check('PATCH orden finalizada (RN-04 cumplida)', r.status_code == 200, show(r))

# RN-07: cancelada no puede finalizarse
r2 = client.post('/api/servicios/', {
    'cliente': cliente_id, 'tipo_servicio': 'revision',
    'fecha': '2026-08-01', 'estado': 'pendiente',
}, format='json')
oid2 = r2.json().get('id')
client.patch(f'/api/servicios/{oid2}/', {'estado': 'cancelada'}, format='json')
r = client.patch(f'/api/servicios/{oid2}/', {'estado': 'finalizada'}, format='json')
check('RN-07 cancelada->finalizada rechazado', r.status_code == 400, show(r))

r = client.get(f'/api/servicios/{orden_id}/historial/')
check('GET /api/servicios/{id}/historial/ (RN-09)', r.status_code == 200 and len(r.json()) >= 4, show(r))

# ---------------------------------------------------------------------------
print('\n7. Mantenimientos')
# ---------------------------------------------------------------------------
r = client.post('/api/mantenimientos/', {
    'equipo': equipo_id, 'cliente': cliente_id, 'tecnico': tecnico_id,
    'tipo': 'preventivo', 'fecha': '2026-08-02', 'proxima_fecha': '2026-09-02',
    'descripcion': 'Limpieza de filtros', 'estado': 'pendiente',
}, format='json')
check('POST /api/mantenimientos/', r.status_code == 201, show(r))

r = client.get('/api/mantenimientos/proximos/')
check('GET /api/mantenimientos/proximos/', r.status_code == 200, show(r))

r = client.get('/api/mantenimientos/historial/')
check('GET /api/mantenimientos/historial/', r.status_code == 200, show(r))

# ---------------------------------------------------------------------------
print('\n8. Materiales e inventario')
# ---------------------------------------------------------------------------
r = client.post('/api/materiales/', {
    'nombre': 'Fusible 10A', 'codigo': 'FUS-10A', 'categoria': 'Eléctrico',
    'unidad_medida': 'unidad', 'cantidad_disponible': 100, 'stock_minimo': 20,
    'precio': 3000,
}, format='json')
check('POST /api/materiales/', r.status_code == 201, show(r))

r = client.post(f'/api/materiales/{material_id}/entrada/', {
    'cantidad': 10, 'motivo': 'Compra', 'tipo': 'entrada',
}, format='json')
check('POST /api/materiales/{id}/entrada/', r.status_code == 200, show(r))

r = client.get('/api/materiales/stock_bajo/')
check('GET /api/materiales/stock_bajo/', r.status_code == 200, show(r))

r = client.get('/api/movimientos/')
check('GET /api/movimientos/', r.status_code == 200, show(r))

# ---------------------------------------------------------------------------
print('\n9. Cotizaciones, pagos, facturas, evaluaciones, evidencias, notificaciones')
# ---------------------------------------------------------------------------
r = client.post('/api/cotizaciones/', {
    'cliente': cliente_id, 'tecnico': tecnico_id, 'solicitud': solicitud_id,
    'validez_dias': 30, 'descuento': 0, 'estado': 'pendiente',
    'detalles': [
        {'descripcion': 'Equipo', 'cantidad': 1, 'precio_unitario': 1000000},
        {'descripcion': 'Mano de obra', 'cantidad': 1, 'precio_unitario': 200000},
    ],
}, format='json')
check('POST /api/cotizaciones/', r.status_code == 201, show(r))
cot_id = r.json().get('id')
check('cotización recalcula total', float(r.json().get('total', 0)) == 1200000, show(r))

r = client.post('/api/pagos/', {
    'cliente': cliente_id, 'orden': orden_id, 'monto': 500000,
    'es_abono': False, 'metodo': 'efectivo', 'fecha': '2026-08-02', 'estado': 'pagado',
}, format='json')
check('POST /api/pagos/', r.status_code == 201, show(r))
pago_id = r.json().get('id')

r = client.post('/api/facturas/', {
    'cliente': cliente_id, 'orden': orden_id, 'iva': 95000, 'pagos': [pago_id],
}, format='json')
check('POST /api/facturas/', r.status_code == 201, show(r))

r = client.post('/api/evaluaciones/', {
    'cliente': cliente_id, 'orden': orden_id, 'calificacion': 5,
    'comentario': 'Muy buen servicio',
}, format='json')
check('POST /api/evaluaciones/ (RN-10)', r.status_code == 201, show(r))

# Evaluación de una orden no finalizada debe fallar (RN-10)
r = client.post('/api/evaluaciones/', {
    'cliente': cliente_id, 'orden': oid2, 'calificacion': 3,
}, format='json')
check('RN-10 evaluar orden no finalizada rechazado', r.status_code == 400, show(r))

r = client.get('/api/notificaciones/')
check('GET /api/notificaciones/', r.status_code == 200, show(r))

r = client.get('/api/notificaciones/no_leidas/')
check('GET /api/notificaciones/no_leidas/', r.status_code == 200, show(r))

# ---------------------------------------------------------------------------
print('\n10. Dashboard y reportes')
# ---------------------------------------------------------------------------
r = client.get('/api/dashboard/')
check('GET /api/dashboard/', r.status_code == 200, show(r))
if r.status_code == 200:
    data = r.json()
    check('dashboard: total_clientes > 0', data.get('total_clientes', 0) > 0)
    check('dashboard: total_tecnicos > 0', data.get('total_tecnicos', 0) > 0)
    check('dashboard: servicios_completados ok', data.get('servicios_completados', 0) >= 1)

r = client.get('/api/dashboard/servicios-por-tecnico/')
check('GET /api/dashboard/servicios-por-tecnico/', r.status_code == 200, show(r))

r = client.get('/api/dashboard/instalaciones-por-mes/')
check('GET /api/dashboard/instalaciones-por-mes/', r.status_code == 200, show(r))

r = client.get('/api/dashboard/materiales-stock-bajo/')
check('GET /api/dashboard/materiales-stock-bajo/', r.status_code == 200, show(r))

# ---------------------------------------------------------------------------
print('\n11. Permisos por rol')
# ---------------------------------------------------------------------------
c2 = APIClient()
r = c2.post('/api/auth/login/', {'username': 'cliente1', 'password': 'Refrimaste2026!'}, format='json')
check('login cliente1', r.status_code == 200, show(r))
c2.credentials(HTTP_AUTHORIZATION=f"Bearer {r.json()['access']}")

r = c2.get('/api/dashboard/')
check('cliente NO puede ver dashboard', r.status_code == 403, show(r))

r = c2.get('/api/clientes/')
check('cliente ve solo su cliente', r.status_code == 200 and r.json().get('count', 0) == 1, show(r))

r = c2.get(f'/api/clientes/{cliente_id}/')
check('cliente NO ve clientes de otros', r.status_code == 404, show(r))

r = c2.post('/api/usuarios/', {
    'username': 'hack', 'email': 'h@x.com', 'password': 'Password123!', 'role': 'admin',
}, format='json')
check('cliente NO puede crear usuarios', r.status_code in (403, 405), show(r))

r = c2.delete(f'/api/clientes/{cliente_id}/')
check('cliente NO puede eliminar (RN-08)', r.status_code == 403, show(r))

# ---------------------------------------------------------------------------
print('\n12. Documentación de la API')
# ---------------------------------------------------------------------------
r = client.get('/api/schema/')
check('GET /api/schema/', r.status_code == 200, show(r))

r = client.get('/api/docs/')
check('GET /api/docs/ (Swagger)', r.status_code == 200, show(r))

# ---------------------------------------------------------------------------
print('=' * 70)
print(f'RESULTADO: {PASS} OK, {FAIL} FALLOS')
print('=' * 70)
exit(1 if FAIL else 0)
