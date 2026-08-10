from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.accounts.models import Tecnico
from apps.clientes.models import Cliente
from apps.core.models import Evidencia, FirmaDigital
from apps.equipos.models import Equipo
from apps.materiales.models import Material


class OrdenServicio(models.Model):
    """Orden de trabajo / servicio (RF-08, RF-09, RF-21)."""

    class TipoServicio(models.TextChoices):
        INSTALACION = 'instalacion', 'Instalación'
        REPARACION = 'reparacion', 'Reparación'
        MANTENIMIENTO_PREVENTIVO = 'mantenimiento_preventivo', 'Mantenimiento preventivo'
        MANTENIMIENTO_CORRECTIVO = 'mantenimiento_correctivo', 'Mantenimiento correctivo'
        DIAGNOSTICO = 'diagnostico', 'Diagnóstico'
        REVISION = 'revision', 'Revisión'

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        ASIGNADA = 'asignada', 'Asignada'
        EN_PROCESO = 'en_proceso', 'En proceso'
        REPROGRAMADA = 'reprogramada', 'Reprogramada'
        FINALIZADA = 'finalizada', 'Finalizada'
        CANCELADA = 'cancelada', 'Cancelada'

    TRANSICIONES_VALIDAS = {
        Estado.PENDIENTE: {Estado.ASIGNADA, Estado.CANCELADA},
        Estado.ASIGNADA: {Estado.EN_PROCESO, Estado.REPROGRAMADA, Estado.CANCELADA},
        Estado.EN_PROCESO: {Estado.FINALIZADA, Estado.CANCELADA},
        Estado.FINALIZADA: set(),
        Estado.CANCELADA: set(),
    }

    numero = models.CharField('número de orden', max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='ordenes',
        verbose_name='cliente',
    )
    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes',
        verbose_name='equipo',
    )
    tecnico = models.ForeignKey(
        Tecnico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ordenes',
        verbose_name='técnico asignado',
    )
    tipo_servicio = models.CharField(
        'tipo de servicio', max_length=40, choices=TipoServicio.choices,
        default=TipoServicio.REPARACION,
    )
    fecha = models.DateField('fecha')
    problema_reportado = models.TextField('problema reportado', blank=True)
    diagnostico = models.TextField('diagnóstico', blank=True)
    trabajo_realizado = models.TextField('trabajo realizado', blank=True)
    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    observaciones = models.TextField('observaciones técnicas', blank=True)
    fecha_asignacion = models.DateTimeField('fecha de asignación', null=True, blank=True)
    fecha_finalizacion = models.DateTimeField('fecha de finalización', null=True, blank=True)
    evidencias = GenericRelation(Evidencia, related_query_name='orden')
    firmas = GenericRelation(FirmaDigital, related_query_name='orden')
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Orden de servicio'
        verbose_name_plural = 'Órdenes de servicio'
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        return f'{self.numero} - {self.cliente} ({self.get_estado_display()})'

    def save(self, *args, **kwargs):
        if not self.numero:
            self.numero = self._generar_numero()
        super().save(*args, **kwargs)

    @staticmethod
    def _generar_numero():
        from django.db.models import Max
        ultimo = OrdenServicio.objects.aggregate(m=Max('id'))['m'] or 0
        return f'OS-{ultimo + 1:04d}'

    @property
    def equipo_nombre(self):
        return str(self.equipo) if self.equipo else ''

    @property
    def tecnico_nombre(self):
        return str(self.tecnico) if self.tecnico else ''


class MaterialUtilizado(models.Model):
    """Materiales/repuestos usados en una orden (RF-15)."""
    orden = models.ForeignKey(
        OrdenServicio,
        on_delete=models.CASCADE,
        related_name='materiales_utilizados',
        verbose_name='orden de servicio',
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='usos',
        verbose_name='material',
    )
    cantidad = models.DecimalField('cantidad', max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField('precio unitario', max_digits=10, decimal_places=2)
    subtotal = models.DecimalField('subtotal', max_digits=12, decimal_places=2, editable=False)
    created_at = models.DateTimeField('creado el', auto_now_add=True)

    class Meta:
        verbose_name = 'Material utilizado'
        verbose_name_plural = 'Materiales utilizados'
        ordering = ['id']

    def __str__(self):
        return f'{self.cantidad} x {self.material.nombre} en {self.orden.numero}'

    def save(self, *args, **kwargs):
        self.subtotal = round(float(self.cantidad) * float(self.precio_unitario), 2)
        super().save(*args, **kwargs)


class EstadoOrdenLog(models.Model):
    """Historial de cambios de estado de la orden (RN-09, RNF-08)."""
    orden = models.ForeignKey(
        OrdenServicio,
        on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='orden de servicio',
    )
    estado_anterior = models.CharField(
        'estado anterior', max_length=20, blank=True, null=True, default=''
    )
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
        verbose_name = 'Cambio de estado'
        verbose_name_plural = 'Historial de estados'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.orden.numero}: {self.estado_anterior} → {self.estado_nuevo}'


class VisitaTecnica(models.Model):
    """Visita técnica programada al domicilio del cliente (RF-11)."""

    class Estado(models.TextChoices):
        PROGRAMADA = 'programada', 'Programada'
        EN_CURSO = 'en_curso', 'En curso'
        REALIZADA = 'realizada', 'Realizada'
        CANCELADA = 'cancelada', 'Cancelada'

    numero = models.CharField('número de visita', max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='visitas',
        verbose_name='cliente',
    )
    orden = models.ForeignKey(
        OrdenServicio,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='visitas',
        verbose_name='orden de servicio',
    )
    tecnico = models.ForeignKey(
        Tecnico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='visitas',
        verbose_name='técnico asignado',
    )
    fecha = models.DateField('fecha de la visita')
    hora = models.TimeField('hora', null=True, blank=True)
    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.PROGRAMADA
    )
    motivo = models.TextField('motivo de la visita', blank=True)
    direccion = models.CharField('dirección de la visita', max_length=255, blank=True)
    observaciones = models.TextField('observaciones', blank=True)
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Visita técnica'
        verbose_name_plural = 'Visitas técnicas'
        ordering = ['-fecha', '-created_at']

    def __str__(self):
        return f'{self.numero} - {self.cliente} ({self.get_estado_display()})'

    def save(self, *args, **kwargs):
        if not self.numero:
            from django.db.models import Max
            ultimo = VisitaTecnica.objects.aggregate(m=Max('id'))['m'] or 0
            self.numero = f'VT-{ultimo + 1:04d}'
        super().save(*args, **kwargs)

    @property
    def tecnico_nombre(self):
        return str(self.tecnico) if self.tecnico else ''
