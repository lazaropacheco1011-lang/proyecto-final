from django.db import models

from apps.clientes.models import Cliente


class SolicitudInstalacion(models.Model):
    """Solicitud de instalación de equipos (RF-06, RF-07)."""

    class Prioridad(models.TextChoices):
        BAJA = 'baja', 'Baja'
        MEDIA = 'media', 'Media'
        ALTA = 'alta', 'Alta'
        URGENTE = 'urgente', 'Urgente'

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        APROBADA = 'aprobada', 'Aprobada'
        REPROGRAMADA = 'reprogramada', 'Reprogramada'
        RECHAZADA = 'rechazada', 'Rechazada'
        COMPLETADA = 'completada', 'Completada'

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='solicitudes',
        verbose_name='cliente',
    )
    tipo_equipo_solicitado = models.CharField('tipo de equipo solicitado', max_length=150)
    descripcion = models.TextField('descripción del requerimiento', blank=True)
    prioridad = models.CharField(
        'prioridad', max_length=20, choices=Prioridad.choices, default=Prioridad.MEDIA
    )
    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    fecha_solicitud = models.DateTimeField('fecha de solicitud', auto_now_add=True)
    fecha_deseada = models.DateField('fecha deseada', null=True, blank=True)
    observaciones = models.TextField('observaciones', blank=True)

    class Meta:
        verbose_name = 'Solicitud de instalación'
        verbose_name_plural = 'Solicitudes de instalación'
        ordering = ['-fecha_solicitud']

    def __str__(self):
        return f'Solicitud #{self.pk} - {self.cliente} - {self.tipo_equipo_solicitado}'
