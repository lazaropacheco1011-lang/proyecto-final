"""Modelos de la tienda: órdenes de compra, items y pagos (RF-tienda)."""
from django.conf import settings
from django.db import models

from apps.almacen.models import Producto
from apps.clientes.models import Cliente


class Orden(models.Model):
    """Orden de compra creada desde la tienda pública (checkout)."""

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        CONFIRMADO = 'confirmado', 'Confirmado'
        PREPARANDO = 'preparando', 'Preparando'
        ENVIADO = 'enviado', 'Enviado'
        ENTREGADO = 'entregado', 'Entregado'
        CANCELADO = 'cancelado', 'Cancelado'

    TRANSICIONES_VALIDAS = {
        Estado.PENDIENTE: {Estado.CONFIRMADO, Estado.CANCELADO},
        Estado.CONFIRMADO: {Estado.PREPARANDO, Estado.CANCELADO},
        Estado.PREPARANDO: {Estado.ENVIADO, Estado.CANCELADO},
        Estado.ENVIADO: {Estado.ENTREGADO, Estado.CANCELADO},
        Estado.ENTREGADO: set(),
        Estado.CANCELADO: set(),
    }

    numero = models.CharField('número de orden', max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ordenes_tienda',
        verbose_name='cliente registrado',
    )
    nombre_cliente = models.CharField('nombre del cliente', max_length=200)
    email = models.EmailField('correo electrónico')
    telefono = models.CharField('teléfono', max_length=30)
    direccion_entrega = models.CharField('dirección de entrega', max_length=255)
    ciudad_entrega = models.CharField('ciudad', max_length=100)
    referencia_entrega = models.CharField('referencia de entrega', max_length=255, blank=True)
    notas = models.TextField('notas', blank=True)

    subtotal = models.DecimalField('subtotal', max_digits=14, decimal_places=2, default=0)
    envio = models.DecimalField('envío', max_digits=14, decimal_places=2, default=0)
    descuento = models.DecimalField('descuento', max_digits=14, decimal_places=2, default=0)
    total = models.DecimalField('total', max_digits=14, decimal_places=2, default=0)
    moneda = models.CharField('moneda', max_length=3, default='DOP')

    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Orden de tienda'
        verbose_name_plural = 'Órdenes de tienda'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.numero} - {self.nombre_cliente} (${self.total:,.2f})'

    @property
    def cliente_display(self):
        if self.cliente_id:
            return self.cliente.nombre_completo
        return self.nombre_cliente

    @property
    def metodo_pago(self):
        pago = self.pagos.order_by('-id').first()
        return pago.get_metodo_display() if pago else '—'

    @property
    def estado_pago(self):
        pago = self.pagos.order_by('-id').first()
        return pago.get_estado_display() if pago else '—'

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generar_numero()
        super().save(*args, **kwargs)

    @staticmethod
    def _generar_numero():
        from django.db.models import Max
        ultimo = Orden.objects.aggregate(m=Max('id'))['m'] or 0
        return f'ORD-{ultimo + 1:04d}'


class OrdenItem(models.Model):
    """Línea de una orden: snapshot del producto, precio y cantidad."""
    orden = models.ForeignKey(
        Orden,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='orden',
    )
    producto = models.ForeignKey(
        Producto,
        on_delete=models.PROTECT,
        related_name='items_orden',
        verbose_name='producto',
    )
    nombre = models.CharField('nombre del producto', max_length=200)
    imagen = models.CharField('imagen', max_length=300, blank=True)
    precio_unitario = models.DecimalField('precio unitario', max_digits=14, decimal_places=2)
    cantidad = models.PositiveIntegerField('cantidad')
    subtotal = models.DecimalField('subtotal', max_digits=14, decimal_places=2)
    created_at = models.DateTimeField('creado el', auto_now_add=True)

    class Meta:
        verbose_name = 'Item de orden'
        verbose_name_plural = 'Items de orden'
        ordering = ['id']

    def __str__(self):
        return f'{self.cantidad} x {self.nombre} ({self.orden.numero})'


class PagoTienda(models.Model):
    """Pago asociado a una orden de tienda.

    Nunca se almacena el número completo de la tarjeta, el CVV ni datos
    sensibles del instrumento: solo se guardan los últimos 4 dígitos y una
    referencia del proveedor (token). El procesamiento ocurre siempre del
    lado del proveedor / gateway.
    """

    class Metodo(models.TextChoices):
        TARJETA = 'tarjeta', 'Tarjeta de crédito/débito'
        PAYPAL = 'paypal', 'PayPal'
        BILLETERA = 'billetera', 'Billetera / app'

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        APROBADO = 'aprobado', 'Aprobado'
        RECHAZADO = 'rechazado', 'Rechazado'
        REEMBOLSADO = 'reembolsado', 'Reembolsado'

    orden = models.ForeignKey(
        Orden,
        on_delete=models.CASCADE,
        related_name='pagos',
        verbose_name='orden',
    )
    metodo = models.CharField('método', max_length=20, choices=Metodo.choices)
    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    monto = models.DecimalField('monto', max_digits=14, decimal_places=2)
    moneda = models.CharField('moneda', max_length=3, default='DOP')
    referencia = models.CharField('referencia del proveedor', max_length=200, blank=True)
    ultimos_digitos = models.CharField('últimos 4 dígitos', max_length=4, blank=True)
    marca_tarjeta = models.CharField('marca de tarjeta', max_length=30, blank=True)
    detalle = models.JSONField('detalle', default=dict, blank=True)
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Pago de tienda'
        verbose_name_plural = 'Pagos de tienda'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.get_metodo_display()} ${self.monto:,.2f} - {self.get_estado_display()}'

    @property
    def metodo_display(self):
        return self.get_metodo_display()

    @property
    def estado_display(self):
        return self.get_estado_display()


class OrdenEstadoLog(models.Model):
    """Historial de cambios de estado de la orden de tienda."""
    orden = models.ForeignKey(
        Orden,
        on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='orden',
    )
    estado_anterior = models.CharField('estado anterior', max_length=20, blank=True)
    estado_nuevo = models.CharField('estado nuevo', max_length=20)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='usuario',
    )
    comentario = models.TextField('comentario', blank=True)
    fecha = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'Cambio de estado de orden'
        verbose_name_plural = 'Historial de estados de órdenes'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.orden.numero}: {self.estado_anterior or "—"} → {self.estado_nuevo}'
