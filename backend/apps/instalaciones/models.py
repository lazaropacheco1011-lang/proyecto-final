from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from apps.accounts.models import Tecnico
from apps.clientes.models import Cliente
from apps.core.models import Evidencia, FirmaDigital
from apps.equipos.models import Equipo
from apps.materiales.models import Material
from apps.solicitudes.models import SolicitudInstalacion


class Instalacion(models.Model):
    """Instalación de equipo de refrigeración (RF-08, RF-12)."""

    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        ASIGNADA = 'asignada', 'Asignada'
        EN_PROCESO = 'en_proceso', 'En proceso'
        FINALIZADA = 'finalizada', 'Finalizada'
        CANCELADA = 'cancelada', 'Cancelada'
        REPROGRAMADA = 'reprogramada', 'Reprogramada'

    class Prioridad(models.TextChoices):
        BAJA = 'baja', 'Baja'
        MEDIA = 'media', 'Media'
        ALTA = 'alta', 'Alta'
        URGENTE = 'urgente', 'Urgente'

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.PROTECT,
        related_name='instalaciones',
        verbose_name='cliente',
    )  # RN-01
    equipo = models.ForeignKey(
        Equipo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instalaciones',
        verbose_name='equipo',
    )
    tecnico = models.ForeignKey(
        Tecnico,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instalaciones',
        verbose_name='técnico responsable',
    )  # RF-09
    solicitud = models.OneToOneField(
        SolicitudInstalacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='instalacion',
        verbose_name='solicitud',
    )
    fecha_programada = models.DateTimeField('fecha programada', null=True, blank=True)
    fecha_instalacion = models.DateTimeField('fecha de instalación', null=True, blank=True)
    prioridad = models.CharField(
        'prioridad', max_length=20, choices=Prioridad.choices, default=Prioridad.MEDIA
    )
    direccion = models.CharField('dirección', max_length=255)
    ciudad = models.CharField('ciudad', max_length=100, blank=True)
    latitud = models.DecimalField(
        'latitud', max_digits=10, decimal_places=7, null=True, blank=True
    )
    longitud = models.DecimalField(
        'longitud', max_digits=10, decimal_places=7, null=True, blank=True
    )
    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.PENDIENTE
    )
    observaciones = models.TextField('observaciones', blank=True)
    evidencias = GenericRelation(Evidencia, related_query_name='instalacion')
    firmas = GenericRelation(FirmaDigital, related_query_name='instalacion')
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Instalación'
        verbose_name_plural = 'Instalaciones'
        ordering = ['-fecha_programada', '-created_at']

    def __str__(self):
        return f'Instalación #{self.pk} - {self.cliente} ({self.get_estado_display()})'

    @property
    def tecnico_nombre(self):
        return str(self.tecnico) if self.tecnico else ''

    @property
    def equipo_nombre(self):
        return str(self.equipo) if self.equipo else ''


class InstalacionEstadoLog(models.Model):
    """Historial de cambios de estado de la instalación (RN-09, RNF-08)."""
    instalacion = models.ForeignKey(
        Instalacion,
        on_delete=models.CASCADE,
        related_name='historial',
        verbose_name='instalación',
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
        verbose_name = 'Cambio de estado de instalación'
        verbose_name_plural = 'Historial de estados de instalaciones'
        ordering = ['-fecha']

    def __str__(self):
        return f'Instalación {self.instalacion_id}: {self.estado_anterior} → {self.estado_nuevo}'


class MaterialInstalacion(models.Model):
    """Materiales/repuestos usados en una instalación (RF-15b).

    El inventario se descuenta automáticamente al finalizar la instalación
    (ver instalaciones.services.finalizar_instalacion).
    """
    instalacion = models.ForeignKey(
        Instalacion,
        on_delete=models.CASCADE,
        related_name='materiales_instalacion',
        verbose_name='instalación',
    )
    material = models.ForeignKey(
        Material,
        on_delete=models.PROTECT,
        related_name='usos_instalacion',
        verbose_name='material',
    )
    cantidad = models.DecimalField('cantidad', max_digits=10, decimal_places=2)
    precio_unitario = models.DecimalField('precio unitario', max_digits=10, decimal_places=2)
    subtotal = models.DecimalField('subtotal', max_digits=12, decimal_places=2, editable=False)
    created_at = models.DateTimeField('creado el', auto_now_add=True)

    class Meta:
        verbose_name = 'Material de instalación'
        verbose_name_plural = 'Materiales de instalación'
        ordering = ['id']

    def __str__(self):
        return f'{self.cantidad} x {self.material.nombre} en instalación #{self.instalacion_id}'

    def save(self, *args, **kwargs):
        self.subtotal = round(float(self.cantidad) * float(self.precio_unitario), 2)
        super().save(*args, **kwargs)
