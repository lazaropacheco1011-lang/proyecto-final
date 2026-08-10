from decimal import Decimal

from django.db import models

from apps.accounts.models import Tecnico
from apps.clientes.models import Cliente
from apps.solicitudes.models import SolicitudInstalacion


class Cotizacion(models.Model):
    """Cotización de instalación (RF-17)."""

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        APROBADA = 'aprobada', 'Aprobada'
        RECHAZADA = 'rechazada', 'Rechazada'
        VENCIDA = 'vencida', 'Vencida'

    numero = models.CharField('número de cotización', max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='cotizaciones',
        verbose_name='cliente',
    )
    solicitud = models.ForeignKey(
        SolicitudInstalacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotizaciones',
        verbose_name='solicitud',
    )
    tecnico = models.ForeignKey(
        Tecnico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cotizaciones',
        verbose_name='técnico que cotiza',
    )
    fecha = models.DateField('fecha', auto_now_add=True)
    validez_dias = models.PositiveIntegerField('días de validez', default=30)
    subtotal = models.DecimalField('subtotal', max_digits=12, decimal_places=2, default=0)
    descuento = models.DecimalField('descuento', max_digits=12, decimal_places=2, default=0)
    total = models.DecimalField('total', max_digits=12, decimal_places=2, default=0)
    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    notas = models.TextField('notas', blank=True)
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Cotización'
        verbose_name_plural = 'Cotizaciones'
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        return f'{self.numero} - {self.cliente} (${self.total:,.2f})'

    def recalcular(self):
        subtotal = sum((d.total for d in self.detalles.all()), Decimal('0.00'))
        self.subtotal = subtotal
        self.total = subtotal - self.descuento
        self.save(update_fields=['subtotal', 'total', 'updated_at'])
        return self.total

    def save(self, *args, **kwargs):
        if not self.numero:
            from django.db.models import Max
            ultimo = Cotizacion.objects.aggregate(m=Max('id'))['m'] or 0
            self.numero = f'COT-{ultimo + 1:04d}'
        super().save(*args, **kwargs)

    @property
    def tecnico_nombre(self):
        return str(self.tecnico) if self.tecnico else ''


class CotizacionDetalle(models.Model):
    """Ítem de una cotización."""
    cotizacion = models.ForeignKey(
        Cotizacion,
        on_delete=models.CASCADE,
        related_name='detalles',
        verbose_name='cotización',
    )
    descripcion = models.CharField('descripción', max_length=255)
    cantidad = models.DecimalField('cantidad', max_digits=10, decimal_places=2, default=1)
    precio_unitario = models.DecimalField('precio unitario', max_digits=12, decimal_places=2)
    total = models.DecimalField('total', max_digits=12, decimal_places=2, editable=False)

    class Meta:
        verbose_name = 'Detalle de cotización'
        verbose_name_plural = 'Detalles de cotización'

    def __str__(self):
        return f'{self.descripcion} (${self.total:,.2f})'

    def save(self, *args, **kwargs):
        self.total = round(Decimal(self.cantidad) * Decimal(self.precio_unitario), 2)
        super().save(*args, **kwargs)
        self.cotizacion.recalcular()
