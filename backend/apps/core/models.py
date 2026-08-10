from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class TimeStampedModel(models.Model):
    """Agrega marcas de tiempo de creación y actualización."""
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    """Registro de auditoría de las acciones importantes (RNF-08, RN-09)."""
    class Action(models.TextChoices):
        CREATE = 'crear', 'Crear'
        UPDATE = 'actualizar', 'Actualizar'
        DELETE = 'eliminar', 'Eliminar'
        STATE_CHANGE = 'cambio_estado', 'Cambio de estado'
        LOGIN = 'iniciar_sesion', 'Iniciar sesión'
        LOGOUT = 'cerrar_sesion', 'Cerrar sesión'
        CHANGE_PASSWORD = 'cambiar_contraseña', 'Cambiar contraseña'
        RESET_PASSWORD = 'restablecer_contraseña', 'Restablecer contraseña'
        OTHER = 'otro', 'Otro'

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='usuario',
    )
    action = models.CharField('acción', max_length=30, choices=Action.choices)
    model_name = models.CharField('modelo', max_length=100)
    object_id = models.PositiveBigIntegerField('objeto', null=True, blank=True)
    object_repr = models.CharField('descripción del objeto', max_length=255, blank=True)
    changes = models.JSONField('cambios', default=dict, blank=True)
    ip_address = models.GenericIPAddressField('dirección IP', null=True, blank=True)
    created_at = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Registro de auditoría'
        verbose_name_plural = 'Registros de auditoría'

    def __str__(self):
        return f'{self.action} {self.model_name}#{self.object_id} por {self.user} @ {self.created_at:%Y-%m-%d %H:%M}'


class Evidencia(models.Model):
    """Evidencia fotográfica vinculable a cualquier registro (RF-20, RN-05)."""
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    imagen = models.ImageField('imagen', upload_to='evidencias/%Y/%m/')
    descripcion = models.CharField('descripción', max_length=255, blank=True)
    fase = models.CharField(
        'fase',
        max_length=20,
        choices=[('antes', 'Antes'), ('durante', 'Durante'), ('despues', 'Después')],
        default='despues',
    )
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='subido por',
    )
    created_at = models.DateTimeField('creado el', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Evidencia fotográfica'
        verbose_name_plural = 'Evidencias fotográficas'

    def __str__(self):
        return f'Evidencia {self.id} - {self.content_type} {self.object_id}'


class FirmaDigital(models.Model):
    """Firma digital del cliente vinculable a instalaciones y órdenes (RF-20b).

    Se guarda como imagen (canvas/captura) asociada al registro de trabajo y
    queda disponible en el historial del equipo como evidencia legal.
    """
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveBigIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    imagen = models.ImageField('firma', upload_to='firmas/%Y/%m/')
    nombre = models.CharField('quién firma', max_length=255, blank=True)
    documento = models.CharField('documento', max_length=30, blank=True)
    observaciones = models.TextField('observaciones', blank=True)
    subido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='registrada por',
    )
    created_at = models.DateTimeField('creado el', auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Firma digital'
        verbose_name_plural = 'Firmas digitales'

    def __str__(self):
        return f'Firma {self.id} - {self.content_type} {self.object_id}'
