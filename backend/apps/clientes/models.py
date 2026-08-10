from django.conf import settings
from django.db import models


class Cliente(models.Model):
    """Datos personales o empresariales del cliente (RF-04)."""

    TIPO_PERSONA = 'persona'
    TIPO_EMPRESA = 'empresa'
    TIPO_CHOICES = [
        (TIPO_PERSONA, 'Persona natural'),
        (TIPO_EMPRESA, 'Empresa'),
    ]

    TIPO_DOCUMENTO_CHOICES = [
        ('cc', 'Cédula'),
        ('pasaporte', 'Pasaporte'),
        ('rnc', 'RNC (empresa)'),
        ('nit', 'NIT'),
        ('otro', 'Otro'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='perfil_cliente',
        verbose_name='usuario',
    )
    tipo = models.CharField('tipo', max_length=20, choices=TIPO_CHOICES, default=TIPO_PERSONA)
    nombre = models.CharField('nombre', max_length=150)
    apellidos = models.CharField('apellidos', max_length=150, blank=True)
    tipo_documento = models.CharField(
        'tipo de documento', max_length=20, choices=TIPO_DOCUMENTO_CHOICES, default='cc'
    )
    documento_numero = models.CharField('número de documento', max_length=30, unique=True)
    email = models.EmailField('correo electrónico')
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    telefono_alternativo = models.CharField('teléfono alternativo', max_length=20, blank=True)
    direccion = models.CharField('dirección', max_length=255, blank=True)
    ciudad = models.CharField('ciudad', max_length=100, blank=True)
    notas = models.TextField('notas', blank=True)
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Cliente'
        verbose_name_plural = 'Clientes'
        ordering = ['nombre', 'apellidos']

    def __str__(self):
        full = f'{self.nombre} {self.apellidos}'.strip()
        return f'{full} ({self.documento_numero})'

    @property
    def nombre_completo(self):
        return f'{self.nombre} {self.apellidos}'.strip()


class DireccionInstalacion(models.Model):
    """Direcciones adicionales de instalación del cliente (RF-05)."""
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='direcciones',
        verbose_name='cliente',
    )
    etiqueta = models.CharField('etiqueta', max_length=100, default='Dirección principal')
    direccion = models.CharField('dirección', max_length=255)
    ciudad = models.CharField('ciudad', max_length=100, blank=True)
    referencia = models.CharField('referencia', max_length=255, blank=True)
    latitud = models.DecimalField('latitud', max_digits=10, decimal_places=7, null=True, blank=True)
    longitud = models.DecimalField('longitud', max_digits=10, decimal_places=7, null=True, blank=True)
    principal = models.BooleanField('principal', default=False)
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Dirección de instalación'
        verbose_name_plural = 'Direcciones de instalación'
        ordering = ['-principal', 'id']

    def __str__(self):
        return f'{self.etiqueta}: {self.direccion}, {self.ciudad}'

    def save(self, *args, **kwargs):
        if self.principal:
            self.cliente.direcciones.exclude(pk=self.pk).update(principal=False)
        super().save(*args, **kwargs)
