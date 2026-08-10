from django.db import models

from apps.clientes.models import Cliente
from apps.instalaciones.models import Instalacion
from apps.servicios.models import OrdenServicio


class EvaluacionServicio(models.Model):
    """Evaluación de satisfacción del cliente al finalizar el servicio (RF-25, RN-10)."""
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='evaluaciones',
        verbose_name='cliente',
    )
    orden = models.ForeignKey(
        OrdenServicio,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='evaluaciones',
        verbose_name='orden de servicio',
    )
    instalacion = models.ForeignKey(
        Instalacion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='evaluaciones',
        verbose_name='instalación',
    )
    calificacion = models.PositiveSmallIntegerField(
        'calificación', help_text='Valor entre 1 y 5'
    )
    comentario = models.TextField('comentario', blank=True)
    fecha = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'Evaluación del servicio'
        verbose_name_plural = 'Evaluaciones del servicio'
        ordering = ['-fecha']
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'orden'], name='uniq_evaluacion_orden',
                condition=models.Q(orden__isnull=False),
            ),
        ]

    def __str__(self):
        return f'Evaluación {self.calificacion}/5 de {self.cliente}'
