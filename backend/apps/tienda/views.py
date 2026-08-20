"""Vistas de la tienda: checkout, pagos y gestión de órdenes."""
import secrets

from django.conf import settings
from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.permissions import ADMIN, ALMACEN, SUPERVISOR, has_role
from apps.tienda import payments
from apps.tienda.models import Orden, PagoTienda
from apps.tienda.serializers import OrdenPublicaSerializer, OrdenSerializer
from apps.tienda.services import (
    cambiar_estado_orden,
    crear_orden_desde_carrito,
    registrar_pago,
)


class TiendaStaffPermission(BasePermission):
    message = 'Se requiere rol de administrador, supervisor o almacén.'

    def has_permission(self, request, view):
        return has_role(request.user, ADMIN, SUPERVISOR, ALMACEN)


def _datos_cliente(payload):
    nombre = str(payload.get('nombre') or '').strip()
    email = str(payload.get('email') or '').strip()
    telefono = str(payload.get('telefono') or '').strip()
    direccion = str(payload.get('direccion') or '').strip()
    ciudad = str(payload.get('ciudad') or '').strip()
    documento = str(payload.get('documento') or '').strip()
    provincia = str(payload.get('provincia') or '').strip()
    sector = str(payload.get('sector') or '').strip()
    if not nombre:
        raise ValidationError('El nombre del cliente es obligatorio.')
    if not email or '@' not in email:
        raise ValidationError('Correo electrónico inválido.')
    if not telefono:
        raise ValidationError('El teléfono es obligatorio.')
    if not documento:
        raise ValidationError('El documento / RNC es obligatorio.')
    if not provincia:
        raise ValidationError('La provincia es obligatoria.')
    if not sector:
        raise ValidationError('El sector es obligatorio.')
    if not direccion:
        raise ValidationError('La dirección de entrega es obligatoria.')
    if not ciudad:
        raise ValidationError('La ciudad es obligatoria.')
    return {
        'nombre': nombre,
        'email': email,
        'telefono': telefono,
        'direccion': direccion,
        'ciudad': ciudad,
        'referencia': str(payload.get('referencia') or '').strip(),
        'notas': str(payload.get('notas') or '').strip(),
        'documento': documento,
        'provincia': provincia,
        'sector': sector,
    }


def _carrito(payload):
    items = payload.get('items')
    if not isinstance(items, list) or not items:
        raise ValidationError('El carrito no puede estar vacío.')
    carrito = []
    for linea in items:
        if not isinstance(linea, dict):
            raise ValidationError('Formato de item inválido.')
        try:
            pid = int(linea.get('producto_id'))
            cantidad = int(linea.get('cantidad') or 1)
        except (TypeError, ValueError):
            raise ValidationError('Formato de item inválido.')
        carrito.append({'producto_id': pid, 'cantidad': max(cantidad, 1)})
    return carrito


class TiendaConfigView(APIView):
    """Configuración pública de la tienda (moneda, envío, métodos)."""
    permission_classes = []

    def get(self, request):
        return Response({
            'moneda': settings.TIENDA_MONEDA,
            'costo_envio': settings.COSTO_ENVIO,
            'envio_gratis_desde': settings.ENVIO_GRATIS_MINIMO,
            'modo_pago': settings.PAYMENT_MODE,
            'metodos': [
                {'value': 'tarjeta', 'label': 'Tarjeta de crédito/débito'},
                {'value': 'paypal', 'label': 'PayPal'},
                {'value': 'billetera', 'label': 'Billetera / app'},
            ],
            'tarjetas_prueba': payments.CARD_APROBADA,
        })


class CrearOrdenTarjetaView(APIView):
    """Checkout con tarjeta: valida, crea la orden y autoriza el cobro.

    La tarjeta solo se procesa en memoria (nunca se almacena).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data or {}
        datos = _datos_cliente(payload)
        carrito = _carrito(payload)
        tarjeta = payload.get('tarjeta') or {}

        numero = str(tarjeta.get('numero') or '')
        exp_mes = str(tarjeta.get('exp_mes') or '')
        exp_anio = str(tarjeta.get('exp_anio') or '')
        cvv = str(tarjeta.get('cvv') or '')

        ok, msg = payments.validar_tarjeta(numero, exp_mes, exp_anio, cvv)
        if not ok:
            return Response({'detail': msg, 'estado_pago': 'invalid'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                orden = crear_orden_desde_carrito(carrito, datos, request)
                resultado = payments.authorize_card(
                    numero, exp_mes, exp_anio, cvv, orden.total, orden.moneda,
                )
                estado_pago = PagoTienda.Estado.APROBADO if resultado['aprobado'] else PagoTienda.Estado.RECHAZADO
                registrar_pago(
                    orden,
                    metodo=PagoTienda.Metodo.TARJETA,
                    estado=estado_pago,
                    referencia=resultado['referencia'],
                    ultimos_digitos=resultado['ultimos_digitos'],
                    marca_tarjeta=resultado['marca'],
                    detalle={'motivo': resultado['motivo'], 'mensaje': resultado['mensaje']},
                )
                if resultado['aprobado'] and orden.estado == Orden.Estado.PENDIENTE:
                    orden.estado = Orden.Estado.CONFIRMADO
                    orden.save(update_fields=['estado', 'updated_at'])
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        payload_resp = {
            'orden': orden.numero,
            'estado_pago': estado_pago,
            'aprobado': resultado['aprobado'],
            'mensaje': resultado['mensaje'],
            'marca': resultado['marca'],
            'ultimos_digitos': resultado['ultimos_digitos'],
            'referencia': resultado['referencia'],
            'total': str(orden.total),
        }
        if resultado['aprobado']:
            return Response(payload_resp, status=status.HTTP_201_CREATED)
        return Response(payload_resp, status=status.HTTP_402_PAYMENT_REQUIRED)


class CrearOrdenPayPalView(APIView):
    """Crea la orden de tienda y la orden de pago en PayPal (sandbox o real)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data or {}
        datos = _datos_cliente(payload)
        carrito = _carrito(payload)
        try:
            with transaction.atomic():
                orden = crear_orden_desde_carrito(carrito, datos, request)
                base = request.build_absolute_uri('/checkout/paypal/aprobar/')
                token_aprobacion = secrets.token_urlsafe(32)
                aprobacion = f'{base}?orden={orden.numero}&token={token_aprobacion}'
                cancel_url = request.build_absolute_uri('/checkout/?cancelado=1')
                referencia, url_aprobacion, error = payments.crear_pago_paypal(
                    orden.total, orden.moneda,
                    f'Orden {orden.numero} - RefriMaster',
                    aprobacion, cancel_url,
                )
                if error:
                    raise ValueError(error)
                registrar_pago(
                    orden,
                    metodo=PagoTienda.Metodo.PAYPAL,
                    estado=PagoTienda.Estado.PENDIENTE,
                    referencia=referencia,
                    detalle={
                        'paypal_order_id': referencia,
                        'aprobacion_token': token_aprobacion,
                    },
                )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'orden': orden.numero,
            'aprobacion_url': url_aprobacion,
            'estado_pago': PagoTienda.Estado.PENDIENTE,
        }, status=status.HTTP_201_CREATED)


class AprobarPayPalView(APIView):
    """Confirma/captura el pago de PayPal una vez aprobado por el cliente."""
    permission_classes = []

    def post(self, request):
        payload = request.data or {}
        numero = str(payload.get('orden') or '').strip()
        token = str(payload.get('token') or '').strip()
        pago = PagoTienda.objects.filter(
            orden__numero=numero, metodo=PagoTienda.Metodo.PAYPAL,
        ).order_by('-id').first()
        if not pago:
            return Response({'detail': 'Pago no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if pago.estado == PagoTienda.Estado.APROBADO:
            return Response({'orden': numero, 'estado_pago': pago.estado})
        esperado = str((pago.detalle or {}).get('aprobacion_token') or '')
        if not token or not esperado or not secrets.compare_digest(token, esperado):
            return Response({'detail': 'Token de aprobación inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        ok, motivo = payments.capturar_pago_paypal(pago.referencia)
        if ok:
            pago.estado = PagoTienda.Estado.APROBADO
            pago.detalle = {'capturado': True, 'motivo': motivo}
            pago.save(update_fields=['estado', 'detalle', 'updated_at'])
            orden = pago.orden
            if orden.estado == Orden.Estado.PENDIENTE:
                orden.estado = Orden.Estado.CONFIRMADO
                orden.save(update_fields=['estado', 'updated_at'])
            return Response({'orden': numero, 'estado_pago': pago.estado})
        return Response(
            {'detail': 'No se pudo capturar el pago en PayPal.'},
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )


class CrearOrdenBilleteraView(APIView):
    """Checkout con billetera/app. Registra la orden con pago pendiente.

    Este método queda preparado para integrar una billetera digital
    posteriormente; por ahora se registra el pedido y el pago queda pendiente.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        payload = request.data or {}
        datos = _datos_cliente(payload)
        carrito = _carrito(payload)
        try:
            with transaction.atomic():
                orden = crear_orden_desde_carrito(carrito, datos, request)
                registrar_pago(
                    orden,
                    metodo=PagoTienda.Metodo.BILLETERA,
                    estado=PagoTienda.Estado.PENDIENTE,
                    referencia='WALLET-PENDIENTE',
                    detalle={'pendiente_integracion': True},
                )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'orden': orden.numero,
            'estado_pago': PagoTienda.Estado.PENDIENTE,
            'mensaje': 'Pedido registrado. Coordinaremos el pago desde tu billetera.',
        }, status=status.HTTP_201_CREATED)


class OrdenPublicaDetailView(APIView):
    """Detalle público de una orden por número (confirmación)."""
    permission_classes = []

    def get(self, request, numero):
        try:
            orden = Orden.objects.prefetch_related('items', 'pagos').get(numero=numero)
        except Orden.DoesNotExist:
            return Response({'detail': 'Orden no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(OrdenPublicaSerializer(orden).data)


class OrdenViewSet(viewsets.ReadOnlyModelViewSet):
    """Órdenes de tienda (gestión interna del panel)."""
    queryset = Orden.objects.prefetch_related('items', 'pagos', 'historial')
    serializer_class = OrdenSerializer
    permission_classes = [TiendaStaffPermission]
    filterset_fields = ['estado']
    search_fields = ['numero', 'nombre_cliente', 'email', 'cliente__nombre']
    ordering_fields = ['created_at', 'total', 'estado']

    @action(detail=True, methods=['patch'])
    def estado(self, request, pk=None):
        orden = self.get_object()
        nuevo = str((request.data or {}).get('estado') or '').strip()
        comentario = str((request.data or {}).get('comentario') or '').strip()
        if nuevo not in dict(Orden.Estado.choices):
            raise ValidationError('Estado de orden inválido.')
        try:
            orden, cambio = cambiar_estado_orden(orden, nuevo, request.user, comentario)
        except ValueError as e:
            raise ValidationError(str(e))
        return Response({
            'orden': orden.numero,
            'estado': orden.estado,
            'estado_display': orden.get_estado_display(),
            'cambio': cambio,
        })

    @action(detail=True, methods=['post'])
    def reembolsar(self, request, pk=None):
        """Marca el último pago aprobado de la orden como reembolsado."""
        if not has_role(request.user, ADMIN, SUPERVISOR):
            raise PermissionDenied('Solo administradores o supervisores pueden reembolsar pagos.')
        orden = self.get_object()
        pago = orden.pagos.order_by('-id').first()
        if not pago:
            raise ValidationError('La orden no tiene pagos registrados.')
        if pago.estado != PagoTienda.Estado.APROBADO:
            raise ValidationError('Solo se pueden reembolsar pagos aprobados.')
        pago.estado = PagoTienda.Estado.REEMBOLSADO
        pago.save(update_fields=['estado', 'updated_at'])
        return Response({'orden': orden.numero, 'estado_pago': pago.estado})
