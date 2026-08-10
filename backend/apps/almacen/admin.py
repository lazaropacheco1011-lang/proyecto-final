from django.contrib import admin

from apps.almacen.models import Categoria, Producto


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'orden', 'icono')
    search_fields = ('nombre',)
    ordering = ('orden', 'nombre')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'categoria', 'precio', 'disponible', 'stock', 'destacado')
    list_filter = ('categoria', 'disponible', 'destacado')
    search_fields = ('nombre', 'descripcion', 'categoria__nombre')
    list_editable = ('disponible', 'stock', 'precio')
