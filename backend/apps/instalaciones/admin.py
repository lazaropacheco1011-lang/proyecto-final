from django.contrib import admin

from apps.instalaciones.models import Instalacion


@admin.register(Instalacion)
class InstalacionAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'cliente', 'equipo', 'tecnico', 'fecha_programada',
        'prioridad', 'estado', 'ciudad',
    ]
    list_filter = ['estado', 'prioridad', 'ciudad', 'fecha_programada']
    search_fields = [
        'cliente__nombre', 'cliente__apellidos', 'equipo__numero_serie',
        'direccion', 'ciudad',
    ]
    date_hierarchy = 'fecha_programada'
