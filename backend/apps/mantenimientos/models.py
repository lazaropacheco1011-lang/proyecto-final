from django.db import models

from apps.accounts.models import Tecnico
from apps.clientes.models import Cliente
from apps.equipos.models import Equipo


class Mantenimiento(models.Model):
    """Mantenimiento preventivo o correctivo de un equipo."""

    class Tipo(models.TextChoices):
        PREVENTIVO = 'preventivo', 'Preventivo'
        CORRECTIVO = 'correctivo', 'Correctivo'

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        EN_PROCESO = 'en_proceso', 'En proceso'
        REALIZADO = 'realizado', 'Realizado'
        CANCELADO = 'cancelado', 'Cancelado'

    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.CASCADE,
        related_name='mantenimientos',
        verbose_name='equipo',
    )
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='mantenimientos',
        verbose_name='cliente',
    )
    tecnico = models.ForeignKey(
        Tecnico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='mantenimientos',
        verbose_name='técnico responsable',
    )
    tipo = models.CharField('tipo', max_length=20, choices=Tipo.choices, default=Tipo.PREVENTIVO)
    fecha = models.DateField('fecha')
    proxima_fecha = models.DateField('próxima fecha de mantenimiento', null=True, blank=True)
    descripcion = models.TextField('descripción', blank=True)
    trabajo_realizado = models.TextField('trabajo realizado', blank=True)
    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    costo = models.DecimalField('costo', max_digits=12, decimal_places=2, default=0)
    observaciones = models.TextField('observaciones', blank=True)
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Mantenimiento'
        verbose_name_plural = 'Mantenimientos'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.get_tipo_display()} de {self.equipo} ({self.get_estado_display()})'

    @property
    def proximo(self):
        return self.proxima_fecha or self.fecha

    @property
    def equipo_nombre(self):
        return str(self.equipo) if self.equipo else ''

    @property
    def tecnico_nombre(self):
        return str(self.tecnico) if self.tecnico else ''
