from django.db import models

from apps.clientes.models import Cliente


class TipoEquipo(models.Model):
    """Clasificación de equipos de refrigeración."""
    nombre = models.CharField('nombre', max_length=100, unique=True)
    descripcion = models.TextField('descripción', blank=True)

    class Meta:
        verbose_name = 'Tipo de equipo'
        verbose_name_plural = 'Tipos de equipo'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Equipo(models.Model):
    """Equipo de refrigeración instalado (RF-13, RF-14)."""

    class Estado(models.TextChoices):
        DISPONIBLE = 'disponible', 'Disponible'
        INSTALADO = 'instalado', 'Instalado'
        AVERIADO = 'averiado', 'Averiado'
        EN_REPARACION = 'en_reparacion', 'En reparación'
        RETIRADO = 'retirado', 'Retirado'

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='equipos',
        verbose_name='cliente propietario',
    )
    tipo = models.ForeignKey(
        TipoEquipo,
        on_delete=models.PROTECT,
        related_name='equipos',
        verbose_name='tipo de equipo',
    )
    marca = models.CharField('marca', max_length=100)
    modelo = models.CharField('modelo', max_length=100)
    numero_serie = models.CharField('número de serie', max_length=100, unique=True)
    capacidad = models.CharField('capacidad', max_length=50, blank=True,
                                 help_text='Ej: 12000 BTU, 1.5 HP, 10 m³')
    refrigerante = models.CharField('refrigerante', max_length=50, blank=True,
                                    help_text='Ej: R-410A, R-22, R-134a')
    estado = models.CharField(
        'estado', max_length=20, choices=Estado.choices, default=Estado.DISPONIBLE
    )
    fecha_instalacion = models.DateField('fecha de instalación', null=True, blank=True)
    garantia_meses = models.PositiveIntegerField(
        'garantía (meses)', null=True, blank=True,
        help_text='Meses de garantía desde la fecha de instalación del equipo.',
    )
    ubicacion = models.CharField('ubicación', max_length=150, blank=True,
                                 help_text='Ej: Sala principal, bodega 2')
    descripcion = models.TextField('descripción', blank=True)
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Equipo de refrigeración'
        verbose_name_plural = 'Equipos de refrigeración'
        ordering = ['marca', 'modelo']
        constraints = [
            models.UniqueConstraint(
                fields=['cliente', 'numero_serie'], name='uniq_equipo_serie_por_cliente'
            ),
        ]

    def __str__(self):
        return f'{self.marca} {self.modelo} - {self.numero_serie}'

    @property
    def tipo_nombre(self):
        return self.tipo.nombre if self.tipo else ''

    @property
    def garantia_hasta(self):
        """Fecha límite de garantía según la fecha de instalación."""
        from datetime import timedelta
        if not self.fecha_instalacion or not self.garantia_meses:
            return None
        mes = self.fecha_instalacion.month - 1 + self.garantia_meses
        anio = self.fecha_instalacion.year + mes // 12
        mes = mes % 12 + 1
        dia = min(self.fecha_instalacion.day, 28)
        return self.fecha_instalacion.replace(year=anio, month=mes, day=dia)

    @property
    def garantia_activa(self):
        from django.utils import timezone
        hasta = self.garantia_hasta
        return bool(hasta) and timezone.localdate() <= hasta
