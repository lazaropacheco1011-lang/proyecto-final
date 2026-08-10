from django.contrib import admin

from apps.materiales.models import Material, MovimientoInventario


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = [
        'nombre', 'codigo', 'categoria', 'unidad_medida',
        'cantidad_disponible', 'stock_minimo', 'precio',
    ]
    list_filter = ['categoria', 'unidad_medida']
    search_fields = ['nombre', 'codigo', 'descripcion']


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = ['material', 'tipo', 'cantidad', 'motivo', 'usuario', 'fecha']
    list_filter = ['tipo', 'fecha']
    search_fields = ['material__nombre', 'motivo']
