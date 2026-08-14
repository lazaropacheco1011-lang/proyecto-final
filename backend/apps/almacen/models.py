"""Modelos del Almacén: categorías y productos disponibles para clientes."""
from django.db import models


class Categoria(models.Model):
    """Categoría de productos de la vitrina pública del almacén."""

    nombre = models.CharField('nombre', max_length=100, unique=True)
    descripcion = models.CharField('descripción', max_length=255, blank=True)
    icono = models.CharField(
        'ícono', max_length=50, blank=True,
        help_text='Nombre del ícono de Material Symbols usado en la vitrina',
    )
    orden = models.PositiveIntegerField('orden', default=0)

    class Meta:
        verbose_name = 'Categoría de producto'
        verbose_name_plural = 'Categorías de productos'
        ordering = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    """Producto de refrigeración disponible para los clientes (RF-almacén)."""

    nombre = models.CharField('nombre', max_length=150)
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name='productos',
        verbose_name='categoría',
    )
    descripcion = models.TextField('descripción', blank=True)
    imagen = models.CharField(
        'imagen', max_length=300, blank=True,
        help_text='Ruta del asset (ej: /assets/img/productos/tuberia.svg)',
    )
    precio = models.DecimalField(
        'precio', max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Vacío = "Consultar precio"',
    )
    en_oferta = models.BooleanField('en oferta', default=False)
    precio_oferta = models.DecimalField(
        'precio de oferta', max_digits=12, decimal_places=2, null=True, blank=True,
        help_text='Precio promocional mostrado en la vitrina cuando el producto está en oferta.',
    )
    disponible = models.BooleanField('disponible', default=True)
    stock = models.PositiveIntegerField('stock', default=0)
    destacado = models.BooleanField('destacado', default=False)
    created_at = models.DateTimeField('creado el', auto_now_add=True)
    updated_at = models.DateTimeField('actualizado el', auto_now=True)

    class Meta:
        verbose_name = 'Producto'
        verbose_name_plural = 'Productos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    @property
    def agotado(self):
        return not self.disponible or self.stock <= 0
