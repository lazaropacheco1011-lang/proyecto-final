from django.conf import settings
from django.db import models


class Material(models.Model):
    """Material o repuesto con control de inventario (RF-16)."""

    class UnidadMedida(models.TextChoices):
        UNIDAD = 'unidad', 'Unidad'
        METRO = 'metro', 'Metro'
        LITRO = 'litro', 'Litro'
        GALON = 'galon', 'Galón'
        KILOGRAMO = 'kilogramo', 'Kilogramo'
        LIBRA = 'libra', 'Libra'
        PAQUETE = 'paquete', 'Paquete'

    nombre = models.CharField('nombre', max_length=150)
    codigo = models.CharField('código', max_length=50, unique=True)
    descripcion = models.TextField('descripción', blank=True)
    categoria = models.CharField('categoría', max_length=100, blank=True)
    unidad_medida = models.CharField(
        'unidad de medida', max_length=20, choices=UnidadMedida.choices,
        default=UnidadMedida.UNIDAD,
    )
    cantidad_disponible = models.DecimalField(
        'cantidad disponible', max_digits=12, decimal_places=2, default=0
    )
    stock_minimo = models.DecimalField(
        'stock mínimo', max_digits=12, decimal_places=2, default=0
    )
    precio = models.DecimalField('precio', max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Material'
        verbose_name_plural = 'Materiales'
        ordering = ['nombre']

    def __str__(self):
        return f'{self.nombre} ({self.codigo})'

    @property
    def stock_bajo(self):
        return float(self.cantidad_disponible) <= float(self.stock_minimo)


class MovimientoInventario(models.Model):
    """Movimiento de entrada/salida/ajuste del inventario."""

    class Tipo(models.TextChoices):
        ENTRADA = 'entrada', 'Entrada'
        SALIDA = 'salida', 'Salida'
        AJUSTE = 'ajuste', 'Ajuste'

    material = models.ForeignKey(
        Material,
        on_delete=models.CASCADE,
        related_name='movimientos',
        verbose_name='material',
    )
    tipo = models.CharField('tipo', max_length=20, choices=Tipo.choices)
    cantidad = models.DecimalField('cantidad', max_digits=12, decimal_places=2)
    motivo = models.CharField('motivo', max_length=255, blank=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='usuario',
    )
    fecha = models.DateTimeField('fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'Movimiento de inventario'
        verbose_name_plural = 'Movimientos de inventario'
        ordering = ['-fecha']

    def __str__(self):
        return f'{self.get_tipo_display()} {self.cantidad} {self.material.nombre}'
