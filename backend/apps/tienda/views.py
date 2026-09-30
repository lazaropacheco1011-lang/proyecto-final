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

from apps.core.permissions import ADMIN, ALMACEN, SUPERVISOR, CLIENTE, has_role, IsCliente
from apps.tienda import payments
from apps.tienda.models import Orden, PagoTienda
from apps.tienda.serializers import OrdenPublicaSerializer, OrdenSerializer
from apps.tienda.services import (
    cambiar_estado_orden,
    crear_orden_desde_carrito,
    enviar_correo_confirmacion_orden,
    liberar_stock_orden,
    rechazar_pago,
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
    referencia = str(payload.get('referencia') or '').strip()
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
    if not referencia:
        raise ValidationError('La referencia de dirección es obligatoria.')
    return {
        'nombre': nombre,
        'email': email,
        'telefono': telefono,
        'direccion': direccion,
        'ciudad': ciudad,
        'referencia': referencia,
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
        disponibles = payments.metodos_disponibles()
        etiquetas = {
            PagoTienda.Metodo.TARJETA: 'Tarjeta de crédito/débito',
            PagoTienda.Metodo.PAYPAL: 'PayPal',
            PagoTienda.Metodo.BILLETERA: 'Billetera / app',
        }
        data = {
            'moneda': settings.TIENDA_MONEDA,
            'costo_envio': settings.COSTO_ENVIO,
            'envio_gratis_desde': settings.ENVIO_GRATIS_MINIMO,
            'modo_pago': settings.PAYMENT_MODE,
            'pagos_disponibles': disponibles,
            # Solo se ofrecen los métodos que realmente pueden operarse ahora.
            'metodos': [
                {'value': metodo, 'label': etiquetas[metodo]}
                for metodo in (PagoTienda.Metodo.TARJETA, PagoTienda.Metodo.PAYPAL,
                               PagoTienda.Metodo.BILLETERA)
                if metodo in disponibles
            ],
        }
        # La tarjeta de prueba solo tiene sentido en modo sandbox; en producción
        # no debe anunciarse ningún número de prueba a los clientes.
        if settings.PAYMENT_MODE == 'sandbox':
            data['tarjetas_prueba'] = payments.CARD_APROBADA
        return Response(data)


def _metodo_bloqueado(metodo):
    """Respuesta 503 cuando el método no puede usarse en este entorno."""
    disponible, motivo = payments.metodo_disponible(metodo)
    if disponible:
        return None
    return Response(
        {'detail': motivo, 'estado_pago': 'no_disponible'},
        status=status.HTTP_503_SERVICE_UNAVAILABLE,
    )


class CrearOrdenTarjetaView(APIView):
    """Checkout con tarjeta: valida, crea la orden y autoriza el cobro.

    La tarjeta solo se procesa en memoria (nunca se almacena).
    """
    permission_classes = [IsAuthenticated, IsCliente]

    def post(self, request):
        bloqueado = _metodo_bloqueado(PagoTienda.Metodo.TARJETA)
        if bloqueado:
            return bloqueado
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
                if resultado['aprobado']:
                    registrar_pago(
                        orden,
                        metodo=PagoTienda.Metodo.TARJETA,
                        estado=PagoTienda.Estado.APROBADO,
                        referencia=resultado['referencia'],
                        ultimos_digitos=resultado['ultimos_digitos'],
                        marca_tarjeta=resultado['marca'],
                        detalle={'motivo': resultado['motivo'], 'mensaje': resultado['mensaje']},
                    )
                    if orden.estado == Orden.Estado.PENDIENTE:
                        orden.estado = Orden.Estado.CONFIRMADO
                        orden.save(update_fields=['estado', 'updated_at'])
                else:
                    # El cobro no se realizó: se registra el rechazo y se
                    # devuelve al inventario el stock que la orden tenía
                    # reservado, para no dejarlo retenido por un pago fallido.
                    orden, _pago = rechazar_pago(
                        orden, PagoTienda.Metodo.TARJETA,
                        motivo=resultado['mensaje'],
                        user=request.user,
                        referencia=resultado['referencia'],
                        ultimos_digitos=resultado['ultimos_digitos'],
                        marca_tarjeta=resultado['marca'],
                        detalle={'motivo': resultado['motivo'], 'mensaje': resultado['mensaje']},
                    )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        estado_pago = PagoTienda.Estado.APROBADO if resultado['aprobado'] else PagoTienda.Estado.RECHAZADO
        payload_resp = {
            'orden': orden.numero,
            'estado_orden': orden.estado,
            'estado_pago': estado_pago,
            'aprobado': resultado['aprobado'],
            'mensaje': resultado['mensaje'],
            'marca': resultado['marca'],
            'ultimos_digitos': resultado['ultimos_digitos'],
            'referencia': resultado['referencia'],
            'total': str(orden.total),
        }
        if resultado['aprobado']:
            enviar_correo_confirmacion_orden(orden)
            return Response(payload_resp, status=status.HTTP_201_CREATED)
        return Response(payload_resp, status=status.HTTP_402_PAYMENT_REQUIRED)


class CrearOrdenPayPalView(APIView):
    """Crea la orden de tienda y la orden de pago en PayPal (sandbox o real)."""
    permission_classes = [IsAuthenticated, IsCliente]

    def post(self, request):
        bloqueado = _metodo_bloqueado(PagoTienda.Metodo.PAYPAL)
        if bloqueado:
            return bloqueado
        payload = request.data or {}
        datos = _datos_cliente(payload)
        carrito = _carrito(payload)
        orden = None
        try:
            with transaction.atomic():
                orden = crear_orden_desde_carrito(carrito, datos, request)
                base = request.build_absolute_uri('/checkout/paypal/aprobar/')
                token_aprobacion = secrets.token_urlsafe(32)
                aprobacion = f'{base}?orden={orden.numero}&token={token_aprobacion}'
                # Al volver de PayPal se repiten orden y token para que el
                # cliente pueda liberar el stock reservado si cancela.
                cancel_url = (
                    f'{request.build_absolute_uri("/checkout/")}'
                    f'?cancelado=1&orden={orden.numero}&token={token_aprobacion}'
                )
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
            # Todo el bloque es atómico: si la orden de PayPal no se crea, la
            # reversión deshace a la vez la orden y el stock que tenía
            # reservado, así que no queda inventario retenido.
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'orden': orden.numero,
            'estado_orden': orden.estado,
            'aprobacion_url': url_aprobacion,
            'estado_pago': PagoTienda.Estado.PENDIENTE,
        }, status=status.HTTP_201_CREATED)


def _pago_paypal_por_token(numero, token):
    """Localiza el pago de PayPal validando su token de aprobación."""
    numero = str(numero or '').strip()
    token = str(token or '').strip()
    pago = PagoTienda.objects.filter(
        orden__numero=numero, metodo=PagoTienda.Metodo.PAYPAL,
    ).order_by('-id').first()
    if not pago:
        return None
    esperado = str((pago.detalle or {}).get('aprobacion_token') or '')
    if not token or not esperado or not secrets.compare_digest(token, esperado):
        return None
    return pago


class AprobarPayPalView(APIView):
    """Confirma/captura el pago de PayPal una vez aprobado por el cliente."""
    permission_classes = []

    def post(self, request):
        payload = request.data or {}
        numero = str(payload.get('orden') or '').strip()
        token = str(payload.get('token') or '').strip()
        pago = _pago_paypal_por_token(numero, token)
        if not pago:
            return Response({'detail': 'Pago no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if pago.estado == PagoTienda.Estado.APROBADO:
            return Response({'orden': numero, 'estado_pago': pago.estado})
        if pago.estado in (PagoTienda.Estado.RECHAZADO, PagoTienda.Estado.REEMBOLSADO):
            # El pago ya se procesó: no se vuelve a cobrar ni a tocar el stock.
            return Response({'orden': numero, 'estado_pago': pago.estado})

        ok, motivo = payments.capturar_pago_paypal(pago.referencia)
        orden = pago.orden
        if ok:
            with transaction.atomic():
                pago.estado = PagoTienda.Estado.APROBADO
                pago.detalle = {'capturado': True, 'motivo': motivo}
                pago.save(update_fields=['estado', 'detalle', 'updated_at'])
                if orden.estado == Orden.Estado.PENDIENTE:
                    orden.estado = Orden.Estado.CONFIRMADO
                    orden.save(update_fields=['estado', 'updated_at'])
            enviar_correo_confirmacion_orden(orden)
            return Response({'orden': numero, 'estado_orden': orden.estado, 'estado_pago': pago.estado})

        # La captura no se completó: no hay pago, así que el stock reservado se
        # devuelve. Si la orden ya estaba cancelada no se vuelve a descontar ni a
        # devolver nada.
        with transaction.atomic():
            if pago.estado == PagoTienda.Estado.PENDIENTE:
                pago.estado = PagoTienda.Estado.RECHAZADO
                pago.detalle = {'capturado': False, 'motivo': motivo}
                pago.save(update_fields=['estado', 'detalle', 'updated_at'])
                orden, _ = liberar_stock_orden(
                    orden, 'No se pudo capturar el pago de PayPal.',
                )
        return Response(
            {'detail': 'No se pudo capturar el pago en PayPal.'},
            status=status.HTTP_402_PAYMENT_REQUIRED,
        )


class CancelarPagoPayPalView(APIView):
    """Libera el stock reservado cuando el cliente abandona el pago de PayPal.

    Se valida con el mismo token de aprobación, sin exigir sesión: PayPal
    devuelve al cliente desde un flujo externo.
    """
    permission_classes = []

    def post(self, request):
        payload = request.data or {}
        numero = str(payload.get('orden') or '').strip()
        token = str(payload.get('token') or '').strip()
        pago = _pago_paypal_por_token(numero, token)
        if not pago:
            return Response({'detail': 'Pago no encontrado.'}, status=status.HTTP_404_NOT_FOUND)
        if pago.estado != PagoTienda.Estado.PENDIENTE:
            return Response({'orden': numero, 'estado_pago': pago.estado})

        with transaction.atomic():
            pago.estado = PagoTienda.Estado.RECHAZADO
            pago.detalle = {'capturado': False, 'motivo': 'cancelado'}
            pago.save(update_fields=['estado', 'detalle', 'updated_at'])
            orden, _ = liberar_stock_orden(
                pago.orden, 'Pago de PayPal cancelado por el cliente.',
            )
        return Response({'orden': numero, 'estado_orden': orden.estado, 'estado_pago': pago.estado})


class CrearOrdenBilleteraView(APIView):
    """Checkout con billetera/app. Registra la orden con pago pendiente.

    Este método queda preparado para integrar una billetera digital
    posteriormente; por ahora se registra el pedido y el pago queda pendiente.
    """
    permission_classes = [IsAuthenticated, IsCliente]

    def post(self, request):
        bloqueado = _metodo_bloqueado(PagoTienda.Metodo.BILLETERA)
        if bloqueado:
            return bloqueado
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

        # El pedido queda PENDIENTE: el stock permanece reservado a la espera
        # del pago, nunca se da por cobrado. Se libera si la orden se cancela.
        enviar_correo_confirmacion_orden(orden)
        return Response({
            'orden': orden.numero,
            'estado_orden': orden.estado,
            'estado_pago': PagoTienda.Estado.PENDIENTE,
            'mensaje': 'Pedido registrado. Coordinaremos el pago desde tu billetera.',
        }, status=status.HTTP_201_CREATED)


class OrdenPublicaDetailView(APIView):
    """Detalle de una orden para quien la posee.

    El número de orden es correlativo y predecible (ORD-0001, ORD-0002, ...),
    por lo que consultarlo sin autenticación permite a cualquiera ver los pedidos
    de otros clientes. Se exige sesión y que la orden pertenezca al usuario (o
    al personal autorizado, que ya tiene su propio recurso de gestión).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, numero):
        orden = (
            Orden.objects
            .filter(numero=numero)
            .prefetch_related('items', 'pagos')
            .first()
        )
        if not orden:
            return Response({'detail': 'Orden no encontrada.'}, status=status.HTTP_404_NOT_FOUND)
        if orden.usuario_id != request.user.pk and not has_role(
            request.user, ADMIN, SUPERVISOR, ALMACEN,
        ):
            # Misma respuesta que si no existiera, para no confirmar la
            # existencia de pedidos ajenos.
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
        """Reembolsa el último pago aprobado de la orden.

        El reembolso solo se marca localmente en sandbox. En producción se
        rechaza: sin integración de reembolso, marcar el pago como reembolsado
        dejaría constancia de una devolución que nunca ocurrió.
        """
        if not has_role(request.user, ADMIN, SUPERVISOR):
            raise PermissionDenied('Solo administradores o supervisores pueden reembolsar pagos.')
        orden = self.get_object()
        pago = orden.pagos.order_by('-id').first()
        if not pago:
            raise ValidationError('La orden no tiene pagos registrados.')
        if pago.estado != PagoTienda.Estado.APROBADO:
            raise ValidationError('Solo se pueden reembolsar pagos aprobados.')

        ok, mensaje = payments.reembolsar_pago(pago)
        if not ok:
            raise ValidationError(mensaje)

        with transaction.atomic():
            pago.estado = PagoTienda.Estado.REEMBOLSADO
            pago.detalle = {**(pago.detalle or {}), 'reembolsado': True}
            pago.save(update_fields=['estado', 'detalle', 'updated_at'])
        return Response({'orden': orden.numero, 'estado_pago': pago.estado})


class MisComprasViewSet(viewsets.ReadOnlyModelViewSet):
    """Historial de compras del cliente autenticado (solo sus propias órdenes).

    La autorización se aplica sobre el queryset filtrando por el usuario
    autenticado, por lo que un cliente nunca puede ver ni consultar las
    órdenes de otro cliente aunque modifique un ID en la URL o la petición.
    """
    serializer_class = OrdenPublicaSerializer
    permission_classes = [IsAuthenticated]

    def get_permissions(self):
        return [perm() for perm in (IsAuthenticated, IsCliente)]

    def get_queryset(self):
        return (
            Orden.objects
            .filter(usuario=self.request.user)
            .prefetch_related('items', 'pagos')
        )
