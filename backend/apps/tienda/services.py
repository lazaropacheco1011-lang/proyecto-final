"""Servicios de la tienda: creación de órdenes, cálculo de totales y pagos."""
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import F

from apps.almacen.images import resolve_asset_url
from apps.almacen.models import Producto
from apps.clientes.models import Cliente
from apps.core.services import register_audit
from apps.tienda.models import Orden, OrdenEstadoLog, OrdenItem, PagoTienda


def calcular_envio(subtotal):
    """Costo de envío según el subtotal."""
    gratis_desde = Decimal(settings.ENVIO_GRATIS_MINIMO)
    if subtotal >= gratis_desde:
        return Decimal('0')
    return Decimal(settings.COSTO_ENVIO)


def _redondear(valor):
    return Decimal(valor).quantize(Decimal('0.01'))


def crear_orden_desde_carrito(carrito, datos_cliente, request=None):
    """Crea la orden y sus items a partir de un carrito validado.

    ``carrito`` es una lista de {producto_id, cantidad}.
    """
    items = []
    subtotal = Decimal('0')
    for linea in carrito:
        producto = Producto.objects.filter(
            pk=linea['producto_id'], disponible=True,
        ).select_related('categoria').first()
        if not producto:
            raise ValueError(f'El producto {linea["producto_id"]} no está disponible.')
        if producto.precio is None:
            raise ValueError(f'El producto "{producto.nombre}" no tiene precio.')
        cantidad = int(linea.get('cantidad') or 1)
        if cantidad < 1:
            raise ValueError('Las cantidades deben ser al menos 1.')
        # Descuenta stock de forma atómica: la condición stock__gte evita
        # vender más unidades de las disponibles aunque dos pedidos compitan.
        descontado = Producto.objects.filter(
            pk=producto.pk, stock__gte=cantidad,
        ).update(stock=F('stock') - cantidad)
        if not descontado:
            stock_actual = Producto.objects.filter(
                pk=producto.pk
            ).values_list('stock', flat=True).first() or 0
            raise ValueError(f'Solo hay {stock_actual} unidades de "{producto.nombre}".')
        precio = producto.precio
        line_total = _redondear(Decimal(precio) * cantidad)
        items.append({
            'producto': producto,
            'nombre': producto.nombre,
            'imagen': resolve_asset_url(producto.imagen or ''),
            'precio_unitario': Decimal(precio),
            'cantidad': cantidad,
            'subtotal': line_total,
        })
        subtotal += line_total

    if not items:
        raise ValueError('El carrito está vacío.')

    subtotal = _redondear(subtotal)
    envio = calcular_envio(subtotal)
    total = _redondear(subtotal + envio)

    cliente = _encontrar_cliente(datos_cliente.get('email'), request)

    orden = Orden.objects.create(
        cliente=cliente,
        nombre_cliente=str(datos_cliente.get('nombre') or '').strip(),
        email=(datos_cliente.get('email') or '').strip().lower(),
        telefono=str(datos_cliente.get('telefono') or '').strip(),
        direccion_entrega=str(datos_cliente.get('direccion') or '').strip(),
        ciudad_entrega=str(datos_cliente.get('ciudad') or '').strip(),
        referencia_entrega=str(datos_cliente.get('referencia') or '').strip(),
        notas=str(datos_cliente.get('notas') or '').strip(),
        documento=str(datos_cliente.get('documento') or '').strip(),
        provincia=str(datos_cliente.get('provincia') or '').strip(),
        sector=str(datos_cliente.get('sector') or '').strip(),
        usuario=(request.user if request and getattr(request, 'user', None) and request.user.is_authenticated else None),
        subtotal=subtotal,
        envio=envio,
        descuento=Decimal('0'),
        total=total,
        moneda=settings.TIENDA_MONEDA,
    )

    for linea in items:
        OrdenItem.objects.create(orden=orden, **{
            k: v for k, v in linea.items() if k != 'producto'
        } | {'producto': linea['producto']})

    if request and getattr(request, 'user', None) and request.user.is_authenticated:
        register_audit(
            request.user, 'crear', orden, model_name='tienda.orden',
            changes={'total': str(total), 'items': len(items)},
        )
    return orden


def _encontrar_cliente(email, request=None):
    if not email:
        return None
    email = str(email).strip().lower()
    cliente = Cliente.objects.filter(email__iexact=email).first()
    if cliente:
        return cliente
    user = getattr(request, 'user', None) if request else None
    if user and user.is_authenticated and hasattr(user, 'perfil_cliente'):
        return user.perfil_cliente
    return None


def registrar_pago(orden, metodo, estado, monto=None, **extra):
    """Registra un pago de tienda (sin datos sensibles del instrumento)."""
    return PagoTienda.objects.create(
        orden=orden,
        metodo=metodo,
        estado=estado,
        monto=monto if monto is not None else orden.total,
        moneda=orden.moneda,
        **extra,
    )


def cambiar_estado_orden(orden, nuevo_estado, user=None, comentario=''):
    """Cambia el estado de una orden validando transiciones y audita el cambio."""
    if nuevo_estado == orden.estado:
        return orden, False
    validos = Orden.TRANSICIONES_VALIDAS.get(orden.estado, set())
    if nuevo_estado not in validos:
        nombre_nuevo = dict(Orden.Estado.choices).get(nuevo_estado, nuevo_estado)
        raise ValueError(
            f'No se puede pasar de "{orden.get_estado_display()}" a "{nombre_nuevo}".'
        )
    anterior = orden.estado
    with transaction.atomic():
        if nuevo_estado == Orden.Estado.CANCELADO:
            for item in orden.items.all():
                Producto.objects.filter(pk=item.producto_id).update(
                    stock=F('stock') + item.cantidad
                )
        orden.estado = nuevo_estado
        orden.save(update_fields=['estado', 'updated_at'])
        OrdenEstadoLog.objects.create(
            orden=orden,
            estado_anterior=anterior,
            estado_nuevo=nuevo_estado,
            usuario=user if user and user.is_authenticated else None,
            comentario=comentario,
        )
    register_audit(
        user, 'cambiar_estado', orden, model_name='tienda.orden',
        changes={'estado_anterior': anterior, 'estado_nuevo': nuevo_estado, 'comentario': comentario},
    )
    return orden, True
