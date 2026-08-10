from django.contrib import admin

from apps.equipos.models import Equipo, TipoEquipo


@admin.register(TipoEquipo)
class TipoEquipoAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'descripcion']
    search_fields = ['nombre']


@admin.register(Equipo)
class EquipoAdmin(admin.ModelAdmin):
    list_display = [
        'marca', 'modelo', 'numero_serie', 'tipo', 'cliente', 'capacidad',
        'refrigerante', 'estado',
    ]
    list_filter = ['estado', 'tipo', 'refrigerante']
    search_fields = ['marca', 'modelo', 'numero_serie', 'cliente__nombre']
