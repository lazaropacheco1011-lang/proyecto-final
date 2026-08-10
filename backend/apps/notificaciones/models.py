from django.conf import settings
from django.db import models


class Notificacion(models.Model):
    """Notificación para usuarios (RF-24)."""

    class Tipo(models.TextChoices):
        ASIGNACION = 'asignacion', 'Asignación'
        CAMBIO_ESTADO = 'cambio_estado', 'Cambio de estado'
        FINALIZACION = 'finalizacion', 'Finalización'
        MANTENIMIENTO = 'mantenimiento', 'Mantenimiento'
        SISTEMA = 'sistema', 'Sistema'

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notificaciones',
        verbose_name='usuario',
    )
    tipo = models.CharField('tipo', max_length=20, choices=Tipo.choices, default=Tipo.SISTEMA)
    titulo = models.CharField('título', max_length=200)
    mensaje = models.TextField('mensaje')
    leida = models.BooleanField('leída', default=False)
    fecha = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'Notificación'
        verbose_name_plural = 'Notificaciones'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.titulo} → {self.usuario}'
