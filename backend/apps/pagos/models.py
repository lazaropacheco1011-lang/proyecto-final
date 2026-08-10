from django.conf import settings
from django.db import models

from apps.clientes.models import Cliente
from apps.instalaciones.models import Instalacion
from apps.servicios.models import OrdenServicio


class Pago(models.Model):
    """Pago o abono realizado por el cliente (RF-18)."""

    class Metodo(models.TextChoices):
        EFECTIVO = 'efectivo', 'Efectivo'
        TARJETA = 'tarjeta', 'Tarjeta'
        TRANSFERENCIA = 'transferencia', 'Transferencia'
        CHEQUE = 'cheque', 'Cheque'

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        PAGADO = 'pagado', 'Pagado'
        FALLIDO = 'fallido', 'Fallido'

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='pagos',
        verbose_name='cliente',
    )
    orden = models.ForeignKey(
        OrdenServicio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos',
        verbose_name='orden de servicio',
    )
    instalacion = models.ForeignKey(
        Instalacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pagos',
        verbose_name='instalación',
    )
    monto = models.DecimalField('monto', max_digits=12, decimal_places=2)
    es_abono = models.BooleanField('es abono', default=False)
    metodo = models.CharField('método', max_length=20, choices=Metodo.choices, default=Metodo.EFECTIVO)
    fecha = models.DateField('fecha')
    referencia = models.CharField('referencia', max_length=100, blank=True)
    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.PAGADO
    )
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='registrado por',
    )
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Pago'
        verbose_name_plural = 'Pagos'
        ordering = ['-fecha']

    def __str__(self):
        return f'Pago ${self.monto:,.2f} - {self.cliente} ({self.fecha})'


class Factura(models.Model):
    """Factura o comprobante de servicio (RF-19)."""
    numero = models.CharField('número de factura', max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='facturas',
        verbose_name='cliente',
    )
    orden = models.ForeignKey(
        OrdenServicio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facturas',
        verbose_name='orden de servicio',
    )
    fecha = models.DateField('fecha', auto_now_add=True)
    subtotal = models.DecimalField('subtotal', max_digits=12, decimal_places=2, default=0)
    iva = models.DecimalField('IVA', max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField('total', max_digits=12, decimal_places=2, default=0)
    pagos = models.ManyToManyField(Pago, related_name='facturas', blank=True, verbose_name='pagos')
    notas = models.TextField('notas', blank=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='creado por',
    )
    created_at = models.DateTimeField('creado el', auto_now_add=True)

    class Meta:
        verbose_name = 'Factura'
        verbose_name_plural = 'Facturas'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.numero} - {self.cliente} (${self.total:,.2f})'

    def calcular_totales(self):
        self.subtotal = sum(p.monto for p in self.pagos.all()) or self.subtotal
        self.total = self.subtotal + self.iva
        self.save(update_fields=['subtotal', 'total'])

    def save(self, *args, **kwargs):
        if not self.numero:
            from django.db.models import Max
            ultimo = Factura.objects.aggregate(m=Max('id'))['m'] or 0
            self.numero = f'FAC-{ultimo + 1:04d}'
        super().save(*args, **kwargs)
