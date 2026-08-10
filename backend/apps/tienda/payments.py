"""Gateway de pagos de la tienda.

Seguridad:
- Los datos de la tarjeta (número completo, CVV, fecha de expiración) se
  procesan en memoria y NUNCA se persisten.
- Solo se almacena la referencia del proveedor, los últimos 4 dígitos y la
  marca de la tarjeta.
- PayPal: la autorización/captura ocurre siempre en los servidores de PayPal.
"""
import json
import secrets
import time
import urllib.parse
import urllib.request

from django.conf import settings

# Tarjetas de prueba (modo sandbox) en formato tipo Stripe:
#   4242 4242 4242 4242  -> aprobada
#   4000 0000 0000 0002  -> rechazada (fondos insuficientes)
#   4000 0000 0000 0008  -> rechazada (no disponible)
CARD_APROBADA = '4242424242424242'
CARD_RECHAZADA_1 = '4000000000000002'
CARD_RECHAZADA_2 = '4000000000000008'


def _solo_digitos(value):
    return ''.join(ch for ch in str(value) if ch.isdigit())


def card_brand(number):
    """Marca de tarjeta según prefijo (solo lectura, no se persiste)."""
    n = _solo_digitos(number)
    if n.startswith('4'):
        return 'Visa'
    if n.startswith(('51', '52', '53', '54', '55')) or (len(n) >= 4 and 2221 <= int(n[:4]) <= 2720):
        return 'Mastercard'
    if n.startswith(('34', '37')):
        return 'American Express'
    if n.startswith('6'):
        return 'Discover'
    return 'Tarjeta'


def luhn_valid(number):
    """Validación Luhn del número de tarjeta."""
    n = _solo_digitos(number)
    if len(n) < 13 or len(n) > 19:
        return False
    suma = 0
    doblar = False
    for ch in reversed(n):
        d = int(ch)
        if doblar:
            d *= 2
            if d > 9:
                d -= 9
        suma += d
        doblar = not doblar
    return suma % 10 == 0


def validar_tarjeta(number, exp_month, exp_year, cvv):
    """Valida formato de la tarjeta. Retorna (ok, mensaje)."""
    n = _solo_digitos(number)
    if len(n) < 15 or len(n) > 19:
        return False, 'El número de tarjeta no es válido.'
    if not luhn_valid(n):
        return False, 'El número de tarjeta no es válido.'
    try:
        mes = int(exp_month)
        anio = int(exp_year)
    except (TypeError, ValueError):
        return False, 'La fecha de expiración no es válida.'
    if mes < 1 or mes > 12:
        return False, 'El mes de expiración no es válido.'
    if anio < 100:
        anio += 2000
    if anio < 1900:
        return False, 'El año de expiración no es válido.'
    ahora = time.localtime()
    exp = anio * 100 + mes
    actual = (ahora.tm_year % 100) * 100 + ahora.tm_mon if ahora.tm_year < 2000 else ahora.tm_year * 100 + ahora.tm_mon
    if exp < actual:
        return False, 'La tarjeta está vencida.'
    cv = _solo_digitos(cvv)
    if len(cv) < 3 or len(cv) > 4:
        return False, 'El código de seguridad (CVV) no es válido.'
    return True, ''


def authorize_card(number, exp_month, exp_year, cvv, amount, currency='DOP'):
    """Autoriza un cobro con tarjeta. Nunca guarda los datos del instrumento.

    En modo sandbox simula la respuesta de un proveedor (PSP): las tarjetas
    de prueba se aprueban/rechazan según el número. En modo producción este
    método debería delegar en el SDK del proveedor (Stripe/Adyen, etc.).
    """
    ok, msg = validar_tarjeta(number, exp_month, exp_year, cvv)
    if not ok:
        return {'aprobado': False, 'mensaje': msg, 'referencia': '', 'marca': card_brand(number), 'ultimos_digitos': _solo_digitos(number)[-4:], 'motivo': 'invalid'}

    marca = card_brand(number)
    ultimos = _solo_digitos(number)[-4:]

    if settings.PAYMENT_MODE == 'sandbox':
        if _solo_digitos(number) == CARD_APROBADA:
            return {
                'aprobado': True,
                'mensaje': 'Pago aprobado.',
                'referencia': 'SANDBOX-' + secrets.token_hex(8).upper(),
                'marca': marca,
                'ultimos_digitos': ultimos,
                'motivo': 'aprobado',
            }
        if _solo_digitos(number) == CARD_RECHAZADA_1:
            return {
                'aprobado': False,
                'mensaje': 'Fondos insuficientes.',
                'referencia': 'SANDBOX-' + secrets.token_hex(8).upper(),
                'marca': marca,
                'ultimos_digitos': ultimos,
                'motivo': 'declined_fondos',
            }
        if _solo_digitos(number) == CARD_RECHAZADA_2:
            return {
                'aprobado': False,
                'mensaje': 'La tarjeta no está disponible.',
                'referencia': 'SANDBOX-' + secrets.token_hex(8).upper(),
                'marca': marca,
                'ultimos_digitos': ultimos,
                'motivo': 'declined_no_disponible',
            }
        return {
            'aprobado': False,
            'mensaje': 'Tarjeta rechazada por el proveedor. Usa una tarjeta de prueba válida.',
            'referencia': 'SANDBOX-' + secrets.token_hex(8).upper(),
            'marca': marca,
            'ultimos_digitos': ultimos,
            'motivo': 'declined',
        }

    # Modo producción: aquí se integraría el SDK del proveedor de tarjetas.
    # El número y el CVV se envían directamente al proveedor (tokenización)
    # y nunca se guardan en la base de datos.
    return {
        'aprobado': False,
        'mensaje': 'Proveedor de tarjetas no configurado. Usa el modo sandbox.',
        'referencia': '',
        'marca': marca,
        'ultimos_digitos': ultimos,
        'motivo': 'not_configured',
    }


# ---------------------------------------------------------------------------
# PayPal (real vía API REST usando urllib; sandbox simula el flujo)
# ---------------------------------------------------------------------------

def _paypal_http(method, url, data=None, token=None):
    """Petición HTTP hacia la API de PayPal (sin dependencias externas)."""
    headers = {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if token:
        headers['Authorization'] = 'Bearer ' + token
    body = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            raw = res.read().decode('utf-8')
            return res.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8')
        try:
            return e.code, json.loads(raw) if raw else {}
        except ValueError:
            return e.code, {}
    except Exception:
        return 0, {}


def _paypal_access_token():
    if not (settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET):
        return ''
    from base64 import b64encode
    cred = b64encode(
        f'{settings.PAYPAL_CLIENT_ID}:{settings.PAYPAL_CLIENT_SECRET}'.encode('utf-8')
    ).decode('utf-8')
    data = 'grant_type=client_credentials'.encode('utf-8')
    req = urllib.request.Request(
        settings.PAYPAL_API_BASE + '/v1/oauth2/token',
        data=data,
        method='POST',
        headers={
            'Authorization': 'Basic ' + cred,
            'Accept': 'application/json',
            'Content-Type': 'application/x-www-form-urlencoded',
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            body = json.loads(res.read().decode('utf-8'))
            return body.get('access_token', '')
    except Exception:
        return ''


def _paypal_approve_link(orden_resp):
    for link in orden_resp.get('links', []):
        if link.get('rel') == 'approve':
            return link.get('href', '')
    return ''


def crear_pago_paypal(monto, moneda, descripcion, aprobacion_url, cancel_url):
    """Crea una orden de pago en PayPal.

    Retorna (referencia, url_aprobacion, error). En modo sandbox retorna una
    URL de aprobación propia que simula el flujo de PayPal.
    """
    referencia = 'PP-' + secrets.token_hex(6).upper()

    if settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET:
        token = _paypal_access_token()
        if not token:
            return '', '', 'No se pudo autenticar con PayPal.'
        status, data = _paypal_http(
            'POST',
            settings.PAYPAL_API_BASE + '/v2/checkout/orders',
            data={
                'intent': 'CAPTURE',
                'purchase_units': [{
                    'reference_id': referencia,
                    'description': descripcion,
                    'amount': {'currency_code': moneda, 'value': f'{float(monto):.2f}'},
                }],
                'application_context': {
                    'brand_name': 'RefriMaster',
                    'user_action': 'PAY_NOW',
                    'return_url': aprobacion_url,
                    'cancel_url': cancel_url,
                },
            },
            token=token,
        )
        if status in (200, 201):
            link = _paypal_approve_link(data)
            return data.get('id', referencia), link or '', ''
        return '', '', 'PayPal rechazó la creación de la orden de pago.'

    # Sandbox: aprobación simulada a través de nuestra propia página.
    return referencia, aprobacion_url, ''


def capturar_pago_paypal(paypal_order_id):
    """Captura un pago de PayPal previamente aprobado. Retorna (ok, mensaje)."""
    if not (settings.PAYPAL_CLIENT_ID and settings.PAYPAL_CLIENT_SECRET):
        if settings.PAYMENT_MODE != 'sandbox':
            return False, 'Procesador de pagos no configurado.'
        return True, 'aprobado'
    token = _paypal_access_token()
    if not token:
        return False, 'No se pudo autenticar con PayPal.'
    status, data = _paypal_http(
        'POST',
        settings.PAYPAL_API_BASE + f'/v2/checkout/orders/{paypal_order_id}/capture',
        data={},
        token=token,
    )
    if status in (200, 201):
        return True, 'aprobado'
    return False, 'capture_failed'
